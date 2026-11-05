"""Actual shipped QML bindings/input with stub Plasma window/theme primitives.

Qt performs layout, model replacement, signals and keyboard delivery. The stub
cannot prove compositor placement; that remains a physical Plasma check.
"""
import os
from pathlib import Path
import shutil
import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
pytest.importorskip('PySide6.QtQuick')
from PySide6.QtCore import QUrl, Qt
from PySide6.QtQml import QQmlEngine, QQmlComponent, QQmlExpression
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

UI = Path(__file__).resolve().parents[1] / 'plasmoid/contents/ui'


def evaluate(obj, code):
    expression = QQmlExpression(QQmlEngine.contextForObject(obj), obj, code)
    value, _ = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return value


@pytest.fixture
def flyout(tmp_path):
    app = QApplication.instance() or QApplication([])
    modules = {
        'org/kde/kirigami': {
            'Icon': 'import QtQuick\nItem { property string source; property color color }',
            'Separator': 'import QtQuick\nRectangle { implicitHeight: 1 }',
            'Theme': 'pragma Singleton\nimport QtQuick\nQtObject { property color textColor: "black"; property color backgroundColor: "white"; property color highlightColor: "blue" }',
        },
        'org/kde/plasma/components': {'Label': 'import QtQuick.Controls as C\nC.Label {}'},
        'org/kde/plasma/core': {'PopupPlasmaWindow': '''import QtQuick
import QtQuick.Window
Window {
 x: 400; y: 400
 property int popupDirection: Qt.RightEdge
 property int effectivePopupDirection: popupDirection
 property bool floating: true
 property int margin: 0
 property bool animated: false
 property int leftPadding: 0
 property int rightPadding: 0
 property int topPadding: 0
 property int bottomPadding: 0
 property Item visualParent
 property Item mainItem
 onMainItemChanged: if (mainItem) mainItem.parent = contentItem
 Binding { target: mainItem; property: "width"; value: width }
 Binding { target: mainItem; property: "height"; value: height }
}'''}}
    for module, files in modules.items():
        folder = tmp_path / module
        folder.mkdir(parents=True)
        (folder / 'qmldir').write_text('\n'.join(('singleton ' if name == 'Theme' else '') + f'{name} 1.0 {name}.qml' for name in files))
        for name, content in files.items():
            (folder / (name + '.qml')).write_text(content)
    for name in ('SideFlyout.qml', 'MenuEntryContent.qml', 'LayoutDraft.js'):
        shutil.copyfile(UI / name, tmp_path / name)
    engine = QQmlEngine()
    engine.addImportPath(str(tmp_path))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(tmp_path / 'SideFlyout.qml')))
    window = component.create()
    assert window, [str(e) for e in component.errors()]
    evaluate(window, '''entries = [{kind:'submenu',title:'Group',items:[
        {kind:'command',title:'Child',key:'child'},
        {kind:'submenu',title:'Deep',items:[{kind:'command',title:'Leaf'}]}]},
        {kind:'command',title:'Other',key:'other'}]; visible = true;''')
    QTest.qWait(30)
    yield window
    window.setProperty('visible', False)
    window.deleteLater()
    app.processEvents()
    engine.deleteLater()
    app.processEvents()


def test_reset_on_model_hide_and_nested_reopen(flyout):
    evaluate(flyout, 'focusFirst();')
    assert flyout.property('activeIndex') == 0
    evaluate(flyout, "entries = [{kind:'command',title:'Lock'},{kind:'command',title:'Sign out'}];")
    assert flyout.property('activeIndex') == -1
    QTest.keyClick(flyout, Qt.Key_Down)
    assert flyout.property('activeIndex') == 0
    QTest.keyClick(flyout, Qt.Key_Down)
    assert flyout.property('activeIndex') == 1
    evaluate(flyout, 'visible=false; visible=true;')
    assert flyout.property('activeIndex') == -1


def test_nested_selection_icons_and_effective_direction(flyout):
    evaluate(flyout, 'flyoutRows.itemAt(0).openChild();')
    assert evaluate(flyout, 'activeChild.activeIndex') == -1
    evaluate(flyout, 'activeChild.focusFirst(); showMenuIcons=false;')
    assert evaluate(flyout, 'activeChild.showMenuIcons') is False
    evaluate(flyout, 'closeChild(); flyoutRows.itemAt(0).openChild();')
    assert evaluate(flyout, 'activeChild.activeIndex') == -1
    evaluate(flyout, 'showMenuIcons=true;')
    assert evaluate(flyout, 'activeChild.showMenuIcons') is True
    evaluate(flyout, 'popupDirection=Qt.RightEdge; effectivePopupDirection=Qt.LeftEdge;')
    QTest.qWait(1)
    assert evaluate(flyout, 'indicatorDirection === Qt.LeftEdge') is True
    evaluate(flyout, 'effectivePopupDirection=Qt.RightEdge;')
    QTest.qWait(1)
    assert evaluate(flyout, 'indicatorDirection === Qt.RightEdge') is True
    evaluate(flyout, 'effectivePopupDirection=Qt.TopEdge; popupDirection=Qt.LeftEdge;')
    QTest.qWait(1)
    assert evaluate(flyout, 'indicatorDirection === Qt.LeftEdge') is True


def test_actual_side_policy_screen_edges(flyout):
    for x, screen_x, screen_width, expected in [(10,0,1200,'Right'), (900,0,1200,'Left'),
            (-300,-1200,1200,'Left'), (20,0,500,'Right'), (400,0,800,'Left')]:
        code = f'chooseSide({{width:280,mapToGlobal:()=>({{x:{x},y:0}})}}, Qt.rect({screen_x},0,{screen_width},900)) === Qt.{expected}Edge'
        assert evaluate(flyout, code)


def test_direction_notification_before_value_update_and_reopen(flyout):
    # libplasma 6.3 emits before updating the value returned by its getter.
    evaluate(flyout, 'effectivePopupDirection=Qt.RightEdge;')
    QTest.qWait(1)
    evaluate(flyout, '''effectivePopupDirectionChanged();
        effectivePopupDirection=Qt.LeftEdge;''')
    # The signal handler must not cache the old RightEdge synchronously.
    QTest.qWait(1)
    assert evaluate(flyout, 'indicatorDirection === Qt.LeftEdge')
    evaluate(flyout, '''visible=false; popupDirection=Qt.RightEdge;
        effectivePopupDirection=Qt.RightEdge; visible=true;''')
    QTest.qWait(1)
    assert evaluate(flyout, 'indicatorDirection === Qt.RightEdge')


def test_row_alignment_and_icon_space(flyout):
    # Inspect the real shared row content at both levels of the flyout.
    evaluate(flyout, 'flyoutRows.itemAt(0).openChild();')
    item = evaluate(flyout, 'flyoutRows.itemAt(0)')
    content = next(c for c in item.childItems() if c.metaObject().indexOfProperty('opensLeft') >= 0)
    def label_x():
        return next(c for c in content.childItems() if c.objectName() == 'entryLabel').x()
    QTest.qWait(20)
    initial = label_x()
    content.setProperty('opensLeft', True)
    QTest.qWait(20)
    assert label_x() == initial
    evaluate(flyout, 'showMenuIcons=false;')
    QTest.qWait(20)
    assert label_x() == initial - 26
    evaluate(flyout, 'showMenuIcons=true;')
    QTest.qWait(20)
    assert label_x() == initial


def test_hover_and_nested_arrows_follow_open_child(flyout):
    from PySide6.QtCore import QPoint
    QTest.mouseMove(flyout, QPoint(100, 55))
    QTest.qWait(30)
    assert flyout.property('activeIndex') == 1
    evaluate(flyout, 'flyoutRows.itemAt(0).openChild();')
    item = evaluate(flyout, 'flyoutRows.itemAt(0)')
    content = next(c for c in item.childItems() if c.metaObject().indexOfProperty('opensLeft') >= 0)
    evaluate(flyout, 'activeChild.effectivePopupDirection=Qt.LeftEdge;')
    QTest.qWait(1)
    assert content.property('opensLeft') is True
    evaluate(flyout, 'activeChild.effectivePopupDirection=Qt.RightEdge;')
    QTest.qWait(1)
    assert content.property('opensLeft') is False
    child = evaluate(flyout, 'activeChild')
    evaluate(child, 'flyoutRows.itemAt(1).openChild();')
    evaluate(flyout, 'showMenuIcons=false;')
    assert evaluate(child, 'activeChild.showMenuIcons') is False
    evaluate(flyout, 'showMenuIcons=true;')
    assert evaluate(child, 'activeChild.showMenuIcons') is True
    evaluate(flyout, 'visible=false;')
    assert child.property('activeIndex') == -1
    assert evaluate(child, 'activeChild === null') is True
