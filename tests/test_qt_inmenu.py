"""Actual Qt Quick interaction with the in-popup editor, without a Plasma shell."""
import json
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
import pytest

pytest.importorskip('PySide6.QtQuick', reason='Qt Quick interactions run in the Qt CI job')
from PySide6.QtCore import QPointF, QUrl, Qt
from PySide6.QtGui import QColor
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]


def child(item, name):
    if item.objectName() == name:
        return item
    for candidate in item.childItems():
        found = child(candidate, name)
        if found is not None:
            return found
    return None


@pytest.fixture
def quick():
    app = QApplication.instance() or QApplication([])
    view = QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.setSource(QUrl.fromLocalFile(str(ROOT / 'plasmoid/contents/ui/LayoutEditor.qml')))
    assert view.status() == QQuickView.Ready, [str(error) for error in view.errors()]
    root = view.rootObject()
    entries = [{'id': 'a', 'kind': 'command', 'title': 'Alpha'},
               {'id': 'g', 'kind': 'submenu', 'title': 'Group', 'items': [
                   {'id': 'c', 'kind': 'command', 'title': 'Child'}]},
               {'id': 'b', 'kind': 'command', 'title': 'Beta'},
               {'id': 's', 'kind': 'separator', 'title': 'Separator'}]
    draft = {'token': 'test-session', 'entries': entries, 'original': '', 'parentId': '', 'selectedId': 'a'}
    root.setProperty('draft', view.engine().evaluate('(' + json.dumps(draft) + ')'))
    root.edited.connect(lambda value: root.setProperty('draft', value))
    view.resize(328, 430)
    view.show()
    QTest.qWait(30)
    root.forceActiveFocus()
    yield app, view, root
    view.close()
    view.deleteLater()
    app.processEvents()


def draft(root):
    return root.property('draft').toVariant()


def click(view, root, name):
    item = child(root, name)
    assert item is not None, name
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(view, Qt.LeftButton, pos=point)
    QTest.qWait(10)


def test_keyboard_reorder_navigation_and_explicit_reparent(quick):
    _, view, root = quick
    QTest.keyClick(view, Qt.Key_Down, Qt.AltModifier)
    assert [e['id'] for e in draft(root)['entries']] == ['g', 'a', 'b', 's']
    QTest.keyClick(view, Qt.Key_Up, Qt.AltModifier)
    assert [e['id'] for e in draft(root)['entries']] == ['a', 'g', 'b', 's']
    click(view, root, 'layoutMoveInto')
    assert draft(root)['parentId'] == 'g'
    assert [e['id'] for e in draft(root)['entries'][0]['items']] == ['c', 'a']
    click(view, root, 'layoutOut')
    assert draft(root)['parentId'] == '' and draft(root)['selectedId'] == 'a'
    click(view, root, 'layoutRow-g')
    assert draft(root)['parentId'] == 'g'
    root.forceActiveFocus()
    QTest.keyClick(view, Qt.Key_Left)
    assert draft(root)['parentId'] == ''
    QTest.keyClick(view, Qt.Key_Right)
    assert draft(root)['parentId'] == 'g'
    QTest.keyClick(view, Qt.Key_Escape)
    assert draft(root)['parentId'] == ''


def test_item_clicks_do_not_save_or_launch_and_save_cancel_are_explicit(quick):
    _, view, root = quick
    signals = []
    root.saveRequested.connect(lambda: signals.append('save'))
    root.cancelRequested.connect(lambda: signals.append('cancel'))
    click(view, root, 'layoutRow-b')
    assert draft(root)['selectedId'] == 'b' and signals == []
    QTest.keyClick(view, Qt.Key_Return)
    assert signals == []
    click(view, root, 'saveLayout')
    click(view, root, 'cancelLayout')
    assert signals == ['save', 'cancel']
    root.setProperty('busy', True)
    assert not child(root, 'saveLayout').property('enabled')
    assert not child(root, 'cancelLayout').property('enabled')
    root.setProperty('busy', False)
    root.setProperty('expired', True)
    assert not child(root, 'saveLayout').property('enabled')
    assert child(root, 'cancelLayout').property('enabled')


def test_mouse_drag_reorders_and_escape_cancels_a_drag(quick):
    _, view, root = quick
    first = child(root, 'layoutRow-a')
    last = child(root, 'layoutRow-b')
    assert first is not None and last is not None
    start = first.mapToScene(QPointF(12, 18)).toPoint()
    end = last.mapToScene(QPointF(12, 32)).toPoint()
    QTest.mousePress(view, Qt.LeftButton, pos=start)
    QTest.mouseMove(view, start + (end - start) / 2, delay=20)
    QTest.mouseMove(view, end, delay=20)
    assert root.property('dragActive')
    QTest.mouseRelease(view, Qt.LeftButton, pos=end)
    QTest.qWait(10)
    assert [e['id'] for e in draft(root)['entries']] == ['g', 'b', 'a', 's']
    before = draft(root)
    first = child(root, 'layoutRow-g')
    last = child(root, 'layoutRow-a')
    start = first.mapToScene(QPointF(12, 18)).toPoint()
    end = last.mapToScene(QPointF(12, 32)).toPoint()
    QTest.mousePress(view, Qt.LeftButton, pos=start)
    QTest.mouseMove(view, end, delay=20)
    QTest.mouseMove(view, end + (end - start) / 8, delay=20)
    assert root.property('dragActive')
    root.forceActiveFocus()
    QTest.keyClick(view, Qt.Key_Escape)
    QTest.mouseRelease(view, Qt.LeftButton, pos=end)
    assert draft(root)['entries'] == before['entries']
    assert not root.property('dragActive')


def test_controls_fit_small_popup_and_dismissal_retains_draft(quick):
    app, view, root = quick
    for width in (285, 328):
        view.resize(width, 430)
        app.processEvents()
        for name in ('layoutUp', 'layoutDown', 'layoutOut', 'layoutMoveInto', 'saveLayout', 'cancelLayout'):
            item = child(root, name)
            point = item.mapToScene(QPointF(0, 0))
            assert point.x() >= 0 and point.x() + item.width() <= width
    before = draft(root)
    root.setVisible(False)
    assert draft(root) == before and not root.property('dragActive')
    root.setVisible(True)
    assert draft(root) == before


def test_handle_click_and_outside_drop_leave_layout_unchanged(quick):
    _, view, root = quick
    before = draft(root)['entries']
    row = child(root, 'layoutRow-g')
    start = row.mapToScene(QPointF(12, 18)).toPoint()
    QTest.mouseClick(view, Qt.LeftButton, pos=start)
    assert draft(root)['parentId'] == ''
    assert draft(root)['selectedId'] == 'g'
    assert draft(root)['entries'] == before
    QTest.mousePress(view, Qt.LeftButton, pos=start)
    end = QPointF(-20, -20).toPoint()
    QTest.mouseMove(view, start + (end - start) / 2, delay=20)
    QTest.mouseMove(view, end, delay=20)
    QTest.mouseRelease(view, Qt.LeftButton, pos=end)
    assert draft(root)['entries'] == before
    assert not root.property('dragActive')


def test_drag_scroll_and_popup_interruption_keep_the_draft(quick):
    _, view, root = quick
    value = draft(root)
    value['entries'] += [{'id': f'extra-{i}', 'kind': 'command', 'title': f'Entry {i}'} for i in range(25)]
    root.setProperty('draft', view.engine().evaluate('(' + json.dumps(value) + ')'))
    QTest.qWait(10)
    row = child(root, 'layoutRow-a')
    rows = child(root, 'layoutRows')
    start = row.mapToScene(QPointF(12, 18)).toPoint()
    end = rows.mapToScene(QPointF(12, rows.height() - 8)).toPoint()
    QTest.mousePress(view, Qt.LeftButton, pos=start)
    QTest.mouseMove(view, start + (end - start) / 2, delay=20)
    QTest.mouseMove(view, end, delay=20)
    QTest.qWait(170)
    assert root.property('dragActive') and rows.property('contentY') > 0
    root.setVisible(False)
    QTest.mouseRelease(view, Qt.LeftButton, pos=end)
    assert not root.property('dragActive')
    assert draft(root)['entries'] == value['entries']


@pytest.mark.parametrize('background,foreground', [
    ('#eff0f1', '#232629'), ('#232629', '#eff0f1'), ('#27313d', '#eff3f8'),
])
def test_quick_controls_follow_light_dark_and_aero_palettes(quick, background, foreground):
    app, view, root = quick
    assignments = ';'.join(f'control.palette.{role}="{color}"' for role, color in {
        'base': background, 'window': background, 'button': background,
        'text': foreground, 'windowText': foreground, 'buttonText': foreground,
    }.items())
    expression = QQmlExpression(QQmlEngine.contextForObject(root), root, assignments)
    expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    view.setColor(QColor(background))
    app.processEvents()
    row = child(root, 'layoutRow-b')
    assert row.property('contentItem').property('color').name() == foreground
    assert child(root, 'saveLayout').property('contentItem').property('color').name() == foreground
    assert not view.grabWindow().isNull()

    def luminance(value):
        color = QColor(value)
        channels = [component / 12.92 if component <= .04045 else ((component + .055) / 1.055) ** 2.4
                    for component in (color.redF(), color.greenF(), color.blueF())]
        return sum(component * weight for component, weight in zip(channels, (.2126, .7152, .0722)))

    bright, dark = sorted((luminance(background), luminance(foreground)), reverse=True)
    assert (bright + .05) / (dark + .05) >= 4.5
