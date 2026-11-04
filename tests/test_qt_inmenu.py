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


def evaluate(root, code):
    expression = QQmlExpression(QQmlEngine.contextForObject(root), root, code)
    result, _ = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return result


def long_menu(view, root):
    value = draft(root)
    value['entries'] = [{'id': f'x{i}', 'kind': 'command', 'title': f'Entry {i}'} for i in range(60)]
    value['entries'][47] = {'id': 'x47', 'kind': 'submenu', 'title': 'Long group', 'items': [
        {'id': f'y{i}', 'kind': 'command', 'title': f'Child {i}'} for i in range(40)]}
    value['selectedId'] = 'x45'
    value['views'] = {}
    root.setProperty('draft', view.engine().evaluate('(' + json.dumps(value) + ')'))
    QTest.qWait(20)
    evaluate(root, 'list.positionViewAtIndex(42, ListView.Beginning)')
    QTest.qWait(10)
    root.forceActiveFocus()


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
    start = first.mapToScene(QPointF(120, 18)).toPoint()
    end = last.mapToScene(QPointF(120, 32)).toPoint()
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


def test_repeated_bottom_moves_keep_anchor_selection_focus_and_delegate(quick):
    _, view, root = quick
    long_menu(view, root)
    rows = child(root, 'layoutRows')
    before = child(root, 'layoutRow-x45')
    anchor_y = child(root, 'layoutRow-x42').mapToScene(QPointF(0, 0)).y()
    for key in [Qt.Key_Down] * 3 + [Qt.Key_Up] * 3:
        QTest.keyClick(view, key, Qt.AltModifier)
        QTest.qWait(20)
        assert rows.property('contentY') > 1000
        assert draft(root)['selectedId'] == 'x45'
        assert root.property('activeFocus')
        moved = child(root, 'layoutRow-x45')
        assert moved == before  # The existing delegate is moved, not rebuilt.
        top = moved.mapToScene(QPointF(0, 0)).y()
        viewport_top = rows.mapToScene(QPointF(0, 0)).y()
        assert viewport_top <= top <= viewport_top + rows.height() - moved.height()
        assert abs(child(root, 'layoutRow-x42').mapToScene(QPointF(0, 0)).y() - anchor_y) <= 1


def test_parent_and_child_viewports_survive_navigation_and_reparenting(quick):
    _, view, root = quick
    long_menu(view, root)
    rows = child(root, 'layoutRows')
    parent_y = rows.property('contentY') - rows.property('originY')
    evaluate(root, "control.choose('x47'); control.enter('x47')")
    QTest.qWait(20)
    assert rows.property('contentY') == rows.property('originY')
    evaluate(root, "list.positionViewAtIndex(24, ListView.Beginning); control.choose('y28')")
    QTest.qWait(20)
    child_y = rows.property('contentY') - rows.property('originY')
    QTest.keyClick(view, Qt.Key_Left)
    QTest.qWait(20)
    assert draft(root)['selectedId'] == 'x47'
    assert abs(rows.property('contentY') - rows.property('originY') - parent_y) <= 1
    QTest.keyClick(view, Qt.Key_Right)
    QTest.qWait(20)
    assert draft(root)['selectedId'] == 'y28'
    assert abs(rows.property('contentY') - rows.property('originY') - child_y) <= 1
    QTest.keyClick(view, Qt.Key_Left, Qt.AltModifier)
    QTest.qWait(20)
    assert draft(root)['parentId'] == '' and draft(root)['selectedId'] == 'y28'
    assert rows.property('contentY') > 1000 and root.property('activeFocus')


def test_draft_viewport_survives_popup_component_recreation(quick):
    _, view, root = quick
    long_menu(view, root)
    before = child(root, 'layoutRows').property('contentY')
    value = draft(root)
    view.setSource(QUrl())
    view.setSource(QUrl.fromLocalFile(str(ROOT / 'plasmoid/contents/ui/LayoutEditor.qml')))
    replacement = view.rootObject()
    replacement.setProperty('draft', view.engine().evaluate('(' + json.dumps(value) + ')'))
    replacement.edited.connect(lambda value: replacement.setProperty('draft', value))
    QTest.qWait(30)
    assert abs(child(replacement, 'layoutRows').property('contentY') - before) <= 1
    assert draft(replacement)['selectedId'] == 'x45'


def test_row_click_threshold_opens_submenu_but_outside_drag_cancels(quick):
    _, view, root = quick
    before = draft(root)['entries']
    row = child(root, 'layoutRow-g')
    start = row.mapToScene(QPointF(120, 18)).toPoint()
    QTest.mousePress(view, Qt.LeftButton, pos=start)
    QTest.mouseMove(view, start + QPointF(1, 1).toPoint(), delay=20)
    assert not root.property('dragActive')
    QTest.mouseRelease(view, Qt.LeftButton, pos=start)
    QTest.qWait(20)
    assert draft(root)['parentId'] == 'g'
    QTest.keyClick(view, Qt.Key_Left)
    QTest.qWait(20)
    assert draft(root)['selectedId'] == 'g'
    assert draft(root)['entries'] == before
    QTest.mousePress(view, Qt.LeftButton, pos=start)
    end = QPointF(-20, -20).toPoint()
    QTest.mouseMove(view, start + (end - start) / 2, delay=20)
    QTest.mouseMove(view, end, delay=20)
    QTest.mouseRelease(view, Qt.LeftButton, pos=end)
    assert draft(root)['entries'] == before
    assert not root.property('dragActive')


def test_dragging_a_whole_submenu_preserves_children_without_opening(quick):
    _, view, root = quick
    group = child(root, 'layoutRow-g')
    last = child(root, 'layoutRow-b')
    start = group.mapToScene(QPointF(160, 18)).toPoint()
    end = last.mapToScene(QPointF(160, 32)).toPoint()
    QTest.mousePress(view, Qt.LeftButton, pos=start)
    QTest.qWait(40)
    QTest.mouseMove(view, start + (end - start) / 2, delay=20)
    QTest.mouseMove(view, end, delay=20)
    QTest.mouseRelease(view, Qt.LeftButton, pos=end)
    QTest.qWait(20)
    value = draft(root)
    assert value['parentId'] == ''
    assert [entry['id'] for entry in value['entries']] == ['a', 'b', 'g', 's']
    assert value['entries'][2]['items'][0]['id'] == 'c'


def point(root, name, x=120, y=18):
    item = child(root, name)
    assert item is not None, name
    return item.mapToScene(QPointF(x, y)).toPoint()


def begin_drag(view, start, end):
    QTest.mousePress(view, Qt.LeftButton, pos=start)
    QTest.mouseMove(view, start + (end - start) / 2, delay=20)
    QTest.mouseMove(view, end, delay=20)


def nested_menu(view, root):
    value = draft(root)
    value['entries'][1]['items'].append({'id': 'h', 'kind': 'submenu', 'title': 'Nested', 'items': [
        {'id': 'd', 'kind': 'command', 'title': 'Deep entry'}]})
    root.setProperty('draft', view.engine().evaluate('(' + json.dumps(value) + ')'))
    root.setProperty('submenuHoverDelay', 120)
    QTest.qWait(20)
    return value['entries']


def test_spring_navigation_moves_into_two_levels_without_losing_pointer(quick):
    _, view, root = quick
    nested_menu(view, root)
    end = point(root, 'layoutRow-g')
    begin_drag(view, point(root, 'layoutRow-a'), end)
    assert root.property('dropKind') == 'inside' and root.property('dropValid')
    QTest.qWait(40)
    assert draft(root)['parentId'] == ''  # Passing over a group does not immediately open it.
    QTest.qWait(100)
    assert draft(root)['parentId'] == 'g' and root.property('dragActive')
    QTest.mouseMove(view, point(root, 'layoutRow-h'), delay=10)
    QTest.qWait(140)
    assert draft(root)['parentId'] == 'h' and root.property('dragActive')
    end = point(root, 'layoutRow-d', y=32)
    QTest.mouseMove(view, end, delay=10)
    QTest.mouseRelease(view, Qt.LeftButton, pos=end)
    QTest.qWait(20)
    value = draft(root)
    assert [entry['id'] for entry in value['entries']] == ['g', 'b', 's']
    assert [entry['id'] for entry in value['entries'][0]['items'][1]['items']] == ['d', 'a']
    assert value['selectedId'] == 'a' and root.property('activeFocus')


def test_spring_parent_navigation_moves_out_through_multiple_levels(quick):
    _, view, root = quick
    nested_menu(view, root)
    evaluate(root, "control.enter('g'); control.enter('h')")
    QTest.qWait(20)
    end = point(root, 'layoutBack', x=18, y=12)
    begin_drag(view, point(root, 'layoutRow-d'), end)
    QTest.qWait(140)
    assert draft(root)['parentId'] == 'g' and root.property('dragActive')
    QTest.qWait(140)
    assert draft(root)['parentId'] == '' and root.property('dragActive')
    end = point(root, 'layoutRow-b', y=32)
    QTest.mouseMove(view, end, delay=10)
    QTest.mouseRelease(view, Qt.LeftButton, pos=end)
    QTest.qWait(20)
    value = draft(root)
    assert [entry['id'] for entry in value['entries']] == ['a', 'g', 'b', 'd', 's']
    assert value['entries'][1]['items'][1]['items'] == []


def test_self_drop_is_marked_invalid_and_does_not_open_or_change_the_group(quick):
    _, view, root = quick
    before = nested_menu(view, root)
    start = point(root, 'layoutRow-g', x=60)
    end = point(root, 'layoutRow-g', x=160)
    begin_drag(view, start, end)
    assert root.property('dragActive') and not root.property('dropValid')
    assert 'itself' in root.property('dropReason')
    QTest.qWait(260)
    assert draft(root)['parentId'] == ''
    QTest.mouseRelease(view, Qt.LeftButton, pos=end)
    assert draft(root)['entries'] == before


def test_brief_submenu_hover_is_canceled_when_pointer_leaves(quick):
    _, view, root = quick
    nested_menu(view, root)
    begin_drag(view, point(root, 'layoutRow-a'), point(root, 'layoutRow-g'))
    QTest.qWait(30)
    end = point(root, 'layoutRow-b', y=32)
    QTest.mouseMove(view, end, delay=10)
    QTest.qWait(160)
    assert draft(root)['parentId'] == '' and root.property('dragActive')
    QTest.mouseRelease(view, Qt.LeftButton, pos=end)
    assert [entry['id'] for entry in draft(root)['entries']] == ['g', 'b', 'a', 's']


def test_group_drop_into_closed_submenu_preserves_the_entire_subtree(quick):
    _, view, root = quick
    before = nested_menu(view, root)
    value = draft(root)
    value['entries'].insert(0, {'id': 'e', 'kind': 'submenu', 'title': 'Empty', 'items': []})
    root.setProperty('draft', view.engine().evaluate('(' + json.dumps(value) + ')'))
    QTest.qWait(20)
    end = point(root, 'layoutRow-e')
    begin_drag(view, point(root, 'layoutRow-g'), end)
    QTest.mouseRelease(view, Qt.LeftButton, pos=end)
    QTest.qWait(20)
    assert draft(root)['entries'][0]['items'] == [before[1]]
    assert draft(root)['parentId'] == 'e' and draft(root)['selectedId'] == 'g'


def test_full_parent_can_be_traversed_to_reach_another_submenu(quick):
    _, view, root = quick
    value = draft(root)
    value['entries'] = [{'id': 'e', 'kind': 'submenu', 'title': 'Destination', 'items': []},
                        value['entries'][1]] + [
        {'id': f'extra-{i}', 'kind': 'command', 'title': f'Entry {i}'} for i in range(198)]
    root.setProperty('draft', view.engine().evaluate('(' + json.dumps(value) + ')'))
    root.setProperty('submenuHoverDelay', 120)
    QTest.qWait(20)
    evaluate(root, "control.enter('g')")
    QTest.qWait(20)
    end = point(root, 'layoutBack', x=18, y=12)
    begin_drag(view, point(root, 'layoutRow-c'), end)
    assert not root.property('dropValid')  # Cannot add a 201st sibling.
    QTest.qWait(140)
    assert draft(root)['parentId'] == ''
    end = point(root, 'layoutRow-e')
    QTest.mouseMove(view, end, delay=10)
    QTest.mouseRelease(view, Qt.LeftButton, pos=end)
    QTest.qWait(20)
    assert len(draft(root)['entries']) == 200
    assert draft(root)['entries'][0]['items'][0]['id'] == 'c'


@pytest.mark.parametrize('interruption', ['escape', 'outside', 'popup'])
def test_interrupted_spring_navigation_preserves_layout_and_returns_to_source(quick, interruption):
    _, view, root = quick
    before = nested_menu(view, root)
    end = point(root, 'layoutRow-g')
    begin_drag(view, point(root, 'layoutRow-a'), end)
    QTest.qWait(140)
    assert draft(root)['parentId'] == 'g'
    if interruption == 'escape':
        QTest.keyClick(view, Qt.Key_Escape)
    elif interruption == 'popup':
        root.setVisible(False)
    else:
        end = QPointF(-20, -20).toPoint()
        QTest.mouseMove(view, end, delay=10)
    QTest.mouseRelease(view, Qt.LeftButton, pos=end)
    QTest.qWait(20)
    assert draft(root)['entries'] == before
    assert draft(root)['parentId'] == '' and not root.property('dragActive')


def test_dragging_at_bottom_keeps_stable_viewport_and_moved_item_visible(quick):
    _, view, root = quick
    long_menu(view, root)
    rows = child(root, 'layoutRows')
    anchor = point(root, 'layoutRow-x42').y()
    for destination, y in [('x46', 32), ('x44', 2)]:
        end = point(root, 'layoutRow-' + destination, y=y)
        begin_drag(view, point(root, 'layoutRow-x45'), end)
        QTest.mouseRelease(view, Qt.LeftButton, pos=end)
        QTest.qWait(20)
        assert abs(point(root, 'layoutRow-x42').y() - anchor) <= 1
        assert rows.property('contentY') > 1000 and draft(root)['selectedId'] == 'x45'
        assert root.property('activeFocus')


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
