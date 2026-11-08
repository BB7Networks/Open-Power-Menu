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
    for name in ('SideFlyout.qml', 'MenuEntryContent.qml', 'LayoutDraft.js', 'AccessKeys.js', 'MenuMetrics.js', 'HoverOpen.qml'):
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


def test_access_keys_nested_and_disabled(flyout):
    calls = []
    flyout.triggered.connect(lambda key, close: calls.append(key))
    evaluate(flyout, """entries = [
        {kind:'submenu',title:'Power',access_key:'U',access_hint:'U',items:[
            {kind:'command',title:'Unavailable',enabled:false,key:'disabled',access_key:'R'},
            {kind:'command',title:'Harmless',key:'nested',access_key:'U',access_hint:'U'}]},
        {kind:'command',title:'Root',key:'root',access_key:'R'}];""")
    QTest.keyClick(flyout, Qt.Key_U)
    QTest.qWait(30)
    child = evaluate(flyout, 'flyoutRows.itemAt(0).childPopup')
    assert child and child.property('visible')
    QTest.keyClick(child, Qt.Key_R)
    assert calls == []
    QTest.keyClick(child, Qt.Key_U)
    assert calls == ['nested']


def test_access_keys_ambiguous_and_no_metadata(flyout):
    calls = []
    flyout.triggered.connect(lambda key, close: calls.append(key))
    evaluate(flyout, "entries = [{kind:'command',title:'X',key:'one'}, {kind:'command',title:'X',key:'two'}];")
    QTest.keyClick(flyout, Qt.Key_X)
    assert calls == []
    evaluate(flyout, "entries = [{kind:'command',title:'One',key:'one',access_key:'X'}, {kind:'command',title:'Two',key:'two',access_key:'X'}];")
    QTest.keyClick(flyout, Qt.Key_X)
    assert calls == []


@pytest.mark.parametrize('delay', [-1, 0, 100, 300, 600])
def test_configured_hover_cancel_keyboard_and_nested(flyout, delay):
    from PySide6.QtCore import QPoint
    evaluate(flyout, f'submenuHoverDelay={delay};')
    QTest.mouseMove(flyout, QPoint(100, 55))
    QTest.mouseMove(flyout, QPoint(100, 15))
    if delay > 0:
        QTest.qWait(30)
        assert evaluate(flyout, 'activeChild === null')
    QTest.qWait(max(delay, 0) + 80)
    assert evaluate(flyout, 'activeChild !== null && activeChild.visible')
    assert evaluate(flyout, 'activeChild.submenuHoverDelay') == delay
    evaluate(flyout, 'closeChild();')
    QTest.mouseMove(flyout, QPoint(100, 55))
    QTest.mouseMove(flyout, QPoint(100, 15))
    QTest.mouseMove(flyout, QPoint(100, 55))
    QTest.qWait(max(delay, 0) + 80)
    assert evaluate(flyout, 'activeChild === null')
    evaluate(flyout, 'activeIndex=0; flyoutSurface.forceActiveFocus(); requestActivate();')
    QTest.qWait(10)
    QTest.keyClick(flyout, Qt.Key_Right)
    assert evaluate(flyout, 'activeChild !== null && activeChild.visible'), evaluate(flyout, '[activeIndex, keyboardMode, flyoutSurface.activeFocus, visible]')
    evaluate(flyout, 'visible=false;')
    QTest.qWait(max(delay, 0) + 80)
    assert evaluate(flyout, 'activeChild === null')


@pytest.mark.parametrize('appearance', ['native', 'aero'])
def test_appearance_metrics_and_screen_bound(flyout, appearance):
    evaluate(flyout, f'appearance="{appearance}";')
    heights=[]
    for density in ['compact', 'standard', 'comfortable']:
        evaluate(flyout, f'menuDensity="{density}";')
        heights.append(evaluate(flyout, 'flyoutRows.itemAt(0).height'))
    assert heights[0] < heights[1] < heights[2]
    widths=[]
    for width in ['narrow', 'auto', 'wide']:
        evaluate(flyout, f'menuWidth="{width}";')
        widths.append(flyout.width())
    assert widths[0] < widths[1] < widths[2]
    sizes=[]
    for size in ['small', 'standard', 'large']:
        evaluate(flyout, f'menuIconSize="{size}";')
        sizes.append(flyout.property('entryIconSize'))
    assert sizes[0] < sizes[1] < sizes[2]
    evaluate(flyout, 'screenRect=Qt.rect(0,0,200,500);')
    assert flyout.width() <= 200
    evaluate(flyout, 'flyoutRows.itemAt(0).openChild();')
    assert evaluate(flyout, 'activeChild.menuDensity') == 'comfortable'
    assert evaluate(flyout, 'activeChild.menuWidth') == 'wide'
    assert evaluate(flyout, 'activeChild.menuIconSize') == 'large'


def test_delayed_sibling_replacement_and_return_to_child(flyout):
    from PySide6.QtCore import QPoint, QEvent
    evaluate(flyout, '''submenuHoverDelay=300; entries=[
        {kind:'submenu',title:'First',items:[{kind:'command',title:'One',key:'one'}]},
        {kind:'submenu',title:'Second',items:[{kind:'command',title:'Two',key:'two'}]}];''')
    QTest.qWait(20)
    QTest.mouseMove(flyout, QPoint(100, 15))
    QTest.qWait(380)
    first = evaluate(flyout, 'activeChild')
    assert first and first.property('visible')
    QTest.mouseMove(flyout, QPoint(100, 55))
    QTest.qWait(50)
    assert first.property('visible')  # Existing child survives the pending delay.
    assert evaluate(flyout, 'activeChild === flyoutRows.itemAt(0).childPopup')
    # Crossing back into the existing child cancels the sibling's timer.
    # Offscreen stub windows overlap and don't synthesize cross-window Leave.
    QApplication.sendEvent(flyout, QEvent(QEvent.Leave))
    QTest.mouseMove(first, QPoint(100, 15))
    QTest.qWait(380)
    assert first.property('visible')
    assert evaluate(flyout, 'flyoutRows.itemAt(1).childPopup === null')
    QTest.mouseMove(flyout, QPoint(100, 55))
    QTest.qWait(380)
    assert evaluate(flyout, 'activeChild === flyoutRows.itemAt(1).childPopup && activeChild.visible')
    assert not first.property('visible')
    child = evaluate(flyout, 'activeChild')
    evaluate(child, 'focusFirst();')
    QTest.qWait(10)
    QTest.keyClick(child, Qt.Key_Left)
    assert not child.property('visible')
    assert flyout.property('activeIndex') == 1
