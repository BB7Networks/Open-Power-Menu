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
def flyout(tmp_path, request):
    app = QApplication.instance() or QApplication([])
    old_font = app.font()
    size = getattr(getattr(request.node, 'callspec', None), 'params', {}).get('font_size')
    if size:
        font = app.font(); font.setPixelSize(size); app.setFont(font)
    modules = {
        'org/kde/kirigami': {
            'Icon': 'import QtQuick\nItem { property string source; property color color; property bool isMask: false }',
            'Separator': 'import QtQuick\nRectangle { implicitHeight: 1 }',
            'Theme': 'pragma Singleton\nimport QtQuick\nQtObject { property font defaultFont: Qt.application.font; property color textColor: "black"; property color backgroundColor: "white"; property color highlightColor: "blue" }',
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
    for name in ('SideFlyout.qml', 'MenuEntryContent.qml', 'IconContrast.js', 'LayoutDraft.js', 'AccessKeys.js', 'MenuMetrics.js', 'HoverOpen.qml'):
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
    app.setFont(old_font)


def test_aero_light_masks_mono_icons_without_tinting_apps(flyout):
    evaluate(flyout, """appearance='aero-light'; entries=[
        {kind:'command',title:'Logs',icon:'view-list-details'},
        {kind:'command',title:'Computer',icon:'computer'},
        {kind:'command',title:'Files',icon:'system-file-manager'},
        {kind:'command',title:'Power',icon:'battery'},
        {kind:'command',title:'Custom',icon:'file:///tmp/custom-icon.svg'}
    ];""")
    QTest.qWait(30)
    def icon_at(index):
        row = evaluate(flyout, f'flyoutRows.itemAt({index})')
        item = next(c for c in row.childItems() if c.metaObject().indexOfProperty('opensLeft') >= 0)
        return next(c for c in item.childItems() if c.objectName() == 'entryIcon')
    assert [icon_at(i).property('isMask') for i in range(5)] == [True,True,False,False,False]
    assert icon_at(0).property('color').name() == '#24394b'
    evaluate(flyout, "appearance='native';")
    QTest.qWait(20)
    assert not icon_at(0).property('isMask')
    evaluate(flyout, "appearance='aero';")
    QTest.qWait(20)
    assert not icon_at(1).property('isMask')
    evaluate(flyout, """appearance='aero-light'; entries=[
        {kind:'submenu',title:'Remote',icon:'network-server',
            items:[{kind:'command',title:'Lock',icon:'system-lock-screen'}]}
    ];""")
    QTest.qWait(20)
    assert icon_at(0).property('isMask')
    evaluate(flyout,'flyoutRows.itemAt(0).openChild();')
    child = evaluate(flyout, 'activeChild')
    assert child.property('appearance') == 'aero-light'
    row = evaluate(child, 'flyoutRows.itemAt(0)')
    item = next(c for c in row.childItems() if c.metaObject().indexOfProperty('opensLeft') >= 0)
    icon = next(c for c in item.childItems() if c.objectName() == 'entryIcon')
    assert icon.property('isMask')


def test_aero_light_toolbar_icons_use_dark_masks(main_popup):
    from PySide6.QtQuick import QQuickItem
    evaluate(main_popup, "menuAppearance='aero-light';")
    QTest.qWait(30)
    for name in ('aeroLightLockIcon', 'aeroLightRefreshIcon', 'aeroLightConfigureIcon'):
        icon = main_popup.findChild(QQuickItem, name)
        assert icon is not None, name
        assert icon.property('isMask') is True
        assert icon.property('visible') is True
        assert icon.property('color').name() == '#24394b'
    evaluate(main_popup, "menuAppearance='native';")
    QTest.qWait(20)
    for name in ('aeroLightLockIcon', 'aeroLightRefreshIcon', 'aeroLightConfigureIcon'):
        assert main_popup.findChild(QQuickItem, name).property('visible') is False


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


@pytest.mark.parametrize('appearance', ['native', 'aero', 'aero-light'])
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

@pytest.mark.parametrize('density', ['compact', 'standard', 'comfortable'])
def test_rendered_natural_height_and_work_area_clamp(flyout, density):
    evaluate(flyout, f'''menuDensity='{density}'; screenRect=Qt.rect(-1920,40,1920,1600);
        topPadding=11; bottomPadding=13;
        entries=Array.from({{length:30}}, (_,i)=>({{kind:i%7===0?'separator':'command',title:'Entry '+i}}));''')
    QTest.qWait(30)
    natural = evaluate(flyout, 'rowsHeight(entries)+topPadding+bottomPadding')
    assert flyout.height() == natural and natural > 540
    evaluate(flyout, 'screenRect=Qt.rect(-1280,-900,1280,500);')
    QTest.qWait(30)
    assert flyout.height() == 492
    assert evaluate(flyout, 'column.height > viewport.availableHeight')
    # The real ScrollView must make its final row reachable, not just clip it.
    evaluate(flyout, 'viewport.contentItem.contentY = column.height - viewport.availableHeight;')
    assert evaluate(flyout, 'flyoutRows.itemAt(29).y + flyoutRows.itemAt(29).height <= viewport.contentItem.contentY + viewport.availableHeight + 1')
    evaluate(flyout, 'screenRect=Qt.rect(0,0,1920,1600); entries=entries.slice(0,3);')
    QTest.qWait(30)
    assert flyout.height() == evaluate(flyout, 'rowsHeight(entries)+topPadding+bottomPadding')


def test_nested_open_menu_tracks_preferences_without_losing_selection(flyout):
    evaluate(flyout, 'flyoutRows.itemAt(0).openChild(); activeChild.focusFirst();')
    before = evaluate(flyout, 'activeChild.height')
    evaluate(flyout, "menuDensity='comfortable'; menuIconSize='large';")
    QTest.qWait(30)
    assert evaluate(flyout, 'activeChild.height') > before
    assert evaluate(flyout, 'activeChild.activeIndex') == 0
    evaluate(flyout, 'screenRect=Qt.rect(-900,32,900,100);')
    QTest.qWait(30)
    assert evaluate(flyout, 'activeChild.screenRect.y') == 32
    assert evaluate(flyout, 'activeChild.height <= 92')


@pytest.mark.parametrize('appearance', ['native', 'aero', 'aero-light'])
@pytest.mark.parametrize('icons', [True, False])
@pytest.mark.parametrize('font_size', [12, 24])
def test_rendered_hint_column_centers_and_empty_keys(flyout, appearance, icons, font_size, tmp_path):
    from PySide6.QtGui import QFont
    import json
    app = QApplication.instance()
    old_font = app.font()
    font = QFont(old_font); font.setPixelSize(font_size)
    app.setFont(font)
    try:
        evaluate(flyout, f'''appearance='{appearance}'; showMenuIcons={str(icons).lower()};
            screenRect=Qt.rect(0,0,1600,1600); menuDensity='comfortable';
            entries='IMWPOUEV '.split('').map(key=>({{kind:'command',title:'A very long menu entry that must elide before its key', access_hint:key.trim()}}));''')
        QTest.qWait(50)
        positions = []
        for i in range(9):
            row = evaluate(flyout, f'flyoutRows.itemAt({i})')
            content = next(c for c in row.childItems() if c.metaObject().indexOfProperty('opensLeft') >= 0)
            column = next(c for c in content.childItems() if c.objectName() == 'accessKeyColumn')
            label = next(c for c in content.childItems() if c.objectName() == 'entryLabel')
            hint = next(c for c in column.childItems() if c.objectName() == 'accessKeyHint')
            assert evaluate(hint, 'horizontalAlignment === Qt.AlignHCenter')
            assert hint.property('font').pixelSize() == font_size
            assert label.x() + label.width() <= column.x()
            positions.append({'key':hint.property('text'), 'x':column.x(), 'width':column.width(), 'center':column.x()+column.width()/2})
        assert len({round(p['center'], 3) for p in positions}) == 1
        assert len({round(p['width'], 3) for p in positions}) == 1
        output = Path(os.environ.get('OPM_RENDER_OUTPUT', str(tmp_path)))
        output.mkdir(parents=True, exist_ok=True)
        stem = f'hints-{appearance}-{icons}-{font_size}'
        (output/(stem+'.json')).write_text(json.dumps(positions, indent=2))
        assert flyout.grabWindow().save(str(output/(stem+'.png')))
        old_label_width = label.width()
        evaluate(flyout, 'entries=entries.map(entry=>Object.assign({}, entry, {access_hint:""}));')
        QTest.qWait(30)
        row = evaluate(flyout, 'flyoutRows.itemAt(0)')
        content = next(c for c in row.childItems() if c.metaObject().indexOfProperty('opensLeft') >= 0)
        column = next(c for c in content.childItems() if c.objectName() == 'accessKeyColumn')
        label = next(c for c in content.childItems() if c.objectName() == 'entryLabel')
        assert not column.isVisible()
        assert label.width() > old_label_width
    finally:
        app.setFont(old_font)

@pytest.fixture
def main_popup(flyout, tmp_path):
    """Render the shipped fullRepresentation with controlled applet state.

    Window/work-area transport is a fixture; all menu/layout/control bindings
    below it are the production QML, not a second implementation of sizing.
    """
    for name in ('LayoutEditor.qml','PointerDismissal.qml','BackendSetup.qml','LayoutController.js'):
        shutil.copyfile(UI/name, tmp_path/name)
    folder=tmp_path/'org/kde/plasma/components'
    (folder/'ToolButton.qml').write_text('import QtQuick.Controls as C\nC.ToolButton {}')
    with (folder/'qmldir').open('a') as f: f.write('\nToolButton 1.0 ToolButton.qml\n')
    folder=tmp_path/'org/kde/kirigami'
    (folder/'Units.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject { property int smallSpacing: 4 }')
    with (folder/'qmldir').open('a') as f:f.write('\nsingleton Units 1.0 Units.qml\n')
    p=folder/'Theme.qml';p.write_text(p.read_text().replace('property color textColor:', 'property color highlightedTextColor: "white"; property color textColor:'))
    item=(UI/'main.qml').read_text().split('fullRepresentation: ',1)[1].rsplit('\n}',1)[0]
    item=item.replace('id: popup','''id: popup
        objectName: "actualMainPopup"
        x: root.leftPadding; y: root.topPadding
        width: Layout.preferredWidth; height: Layout.preferredHeight''',1)
    source='''import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PC3
import "MenuMetrics.js" as Metrics
import "AccessKeys.js" as AccessKeys
import "LayoutDraft.js" as LayoutDraft
import "LayoutController.js" as LayoutController
Window {
 id: root
 visible: true
 property real topPadding: 10
 property real bottomPadding: 14
 property real leftPadding: 8
 property real rightPadding: 8
 width: popup.width+leftPadding+rightPadding
 height: popup.height+topPadding+bottomPadding
 property bool expanded: true
 property bool autoCloseOnPointerLeave: false
 property int autoCloseDelay: 500
 property int submenuHoverDelay: -1
 property bool backendMissing: false
 property bool showMenuIcons: true
 property bool launchPending: false
 property bool layoutBusy: false
 property bool layoutExpired: false
 property var layoutDraft: null
 readonly property bool layoutEditing: layoutDraft !== null
 property bool powerIsOpen: true
 property string commandError: ""
 property string layoutStatus: ""
 property string menuStatus: ""
 property string menuAppearance: "native"
 readonly property color menuTextColor: menuAppearance === "aero" ? "#eff3f8" : menuAppearance === "aero-light" ? "#24394b" : "black"
 readonly property color menuSurfaceColor: menuAppearance === "aero" ? "#27313d" : menuAppearance === "aero-light" ? "#eaf1f7" : "transparent"
 readonly property color menuAccentColor: "blue"
 property string menuDensity: "standard"
 property string menuHeightMode: "auto"
 property int menuCustomHeight: 600
 readonly property var menuHeightPreference: ({mode:menuHeightMode,height:menuCustomHeight})
 property string menuWidth: "auto"
 property string menuIconSize: "standard"
 property rect menuWorkArea: Qt.rect(-1920,40,1920,1600)
 property var visibleEntries: []
 function fetchMenu() {}
 function fetchIntegration() {}
 function launchItem() { throw new Error("No command execution in sizing fixture") }
 function openEditor() {}
'''+item+'\n}'
    path=tmp_path/'MainFixture.qml';path.write_text(source)
    engine=QQmlEngine();engine.addImportPath(str(tmp_path))
    component=QQmlComponent(engine,QUrl.fromLocalFile(str(path)))
    window=component.create()
    assert window,[str(e) for e in component.errors()]
    QTest.qWait(30)
    yield window
    window.setVisible(False);window.deleteLater();QApplication.instance().processEvents()
    engine.deleteLater();QApplication.instance().processEvents()


def test_rendered_main_natural_custom_and_clamping(main_popup):
    window=main_popup
    evaluate(window, "visibleEntries=Array.from({length:25},(_,i)=>({kind:'command',title:'Command '+i,key:'fixture'+i}));")
    QTest.qWait(40)
    assert window.height() > 590
    assert evaluate(window, 'menuScroll.availableHeight >= menuColumn.implicitHeight')
    evaluate(window, "menuDensity='comfortable'; menuIconSize='large';")
    QTest.qWait(40)
    assert evaluate(window, 'menuScroll.availableHeight >= menuColumn.implicitHeight')
    evaluate(window, "menuHeightMode='custom'; menuCustomHeight=370;")
    QTest.qWait(40)
    assert evaluate(window, 'popup.height') == 370
    evaluate(window, "menuWorkArea=Qt.rect(-1280,-1000,1280,300); menuDensity='compact';")
    QTest.qWait(40)
    assert window.height() <= 292
    assert window.property('menuCustomHeight') == 370
    evaluate(window, "menuWorkArea=Qt.rect(0,40,1920,1600);")
    QTest.qWait(40)
    assert evaluate(window, 'popup.height') == 370
    evaluate(window, "menuHeightMode='auto';")
    QTest.qWait(40)
    assert evaluate(window, 'menuScroll.availableHeight >= menuColumn.implicitHeight')
    evaluate(window, "menuWorkArea=Qt.rect(0,40,1920,400); popup.forceActiveFocus();")
    QTest.qWait(40)
    for _ in range(25):QTest.keyClick(window,Qt.Key_Down)
    assert evaluate(window, 'popup.activeIndex') == 24
    assert evaluate(window, 'normalRows.itemAt(24).y+normalRows.itemAt(24).height <= menuScroll.contentItem.contentY+menuScroll.availableHeight+1')


def test_long_status_cannot_starve_menu_scroll_area(main_popup):
    window=main_popup
    evaluate(window, "visibleEntries=Array.from({length:20},(_,i)=>({kind:'command',title:'Entry '+i})); menuWorkArea=Qt.rect(0,0,1000,500); menuStatus='A long error message. '.repeat(200);")
    QTest.qWait(40)
    assert evaluate(window, 'menuScroll.availableHeight > popup.entryHeight')
    assert evaluate(window, 'statusScroll.contentHeight > statusScroll.availableHeight')
    assert window.height() <= 492


def test_rendered_main_editing_height_and_narrow_work_area(main_popup):
    window=main_popup
    evaluate(window, "layoutDraft=LayoutDraft.start({token:'fixture',entries:Array.from({length:25},(_,i)=>({id:'id'+i,kind:'command',title:'Entry '+i}))});")
    QTest.qWait(50)
    assert evaluate(window, 'layoutEditor.height >= layoutEditor.implicitHeight')
    before=window.height()
    evaluate(window, "menuHeightMode='custom'; menuCustomHeight=120;")
    QTest.qWait(40)
    assert evaluate(window, 'layoutEditor.height >= layoutEditor.minimumUsableHeight')
    assert window.property('menuCustomHeight') == 120
    evaluate(window, "menuHeightMode='auto';")
    evaluate(window, "layoutDraft=LayoutDraft.start({token:'smaller',entries:[{id:'one',kind:'command',title:'Only entry'}]});")
    QTest.qWait(50)
    assert window.height() < before
    evaluate(window, "layoutDraft=null; menuWidth='wide'; menuWorkArea=Qt.rect(-300,32,300,900);")
    QTest.qWait(50)
    assert window.width() < 300


def test_font_change_updates_live_row_and_hint_metrics(flyout):
    # KDE's notifying Theme font changes on settings updates. Qt.application.font
    # is a CONSTANT QML property and cannot drive live metric bindings.
    evaluate(flyout, "screenRect=Qt.rect(0,0,1200,1600); entries=[{kind:'command',title:'Font test',access_hint:'W'}];")
    QTest.qWait(30)
    row=evaluate(flyout,'flyoutRows.itemAt(0)')
    content=next(c for c in row.childItems() if c.metaObject().indexOfProperty('showHints')>=0)
    column=next(c for c in content.childItems() if c.objectName()=='accessKeyColumn')
    width,height=column.width(),flyout.height()
    evaluate(flyout, "Kirigami.Theme.defaultFont = Qt.font({pixelSize:36});")
    QTest.qWait(40)
    assert column.width()>width
    assert flyout.height()>height
