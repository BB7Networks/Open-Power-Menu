"""Real offscreen widgets, modal dialogs, key events and Qt drop-event adapter.

Native Wayland drag cursor/placement and Plasma integration remain live checks.
"""
from copy import deepcopy
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest

pytest.importorskip('PySide6.QtWidgets', reason='Editor widgets run in the Qt CI job')
from PySide6.QtCore import QMimeData, QPointF, Qt, QTimer
from PySide6.QtGui import QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView, QDialog, QMessageBox

from openpowermenu.backup_dialog import BackupDialog
from openpowermenu.core import DEFAULT_CONFIG, save_config
from openpowermenu.editor import create_editor
from openpowermenu.recovery import current_revision, decode_configuration


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def editor(app, tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    monkeypatch.setenv('XDG_DATA_DIRS', str(tmp_path / 'system-data'))
    config = deepcopy(DEFAULT_CONFIG)
    config['menu'] = [
        {'submenu': 'Group', 'icon': 'folder', 'extra': {'keep': [1]}, 'items': [
            {'label': 'Nested', 'command': ['echo', 'a b'], 'custom': {'keep': True}},
            {'submenu': 'Inner', 'items': [{'action': 'files'}]}]},
        {'label': 'Outside', 'command': ['echo', 'outside']}, {'separator': True}]
    target = tmp_path / 'config/open-power-menu/menu.json'
    save_config(config, target)
    dialog = create_editor(target)
    dialog.warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda parent, title, text, *args: dialog.warnings.append(text))
    monkeypatch.setattr(QMessageBox, 'critical', lambda parent, title, text, *args: dialog.warnings.append(text))
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Cancel)
    dialog.show()
    dialog.tabs.setCurrentIndex(1)
    app.processEvents()
    yield dialog
    dialog._closing = True
    QDialog.reject(dialog)
    dialog.deleteLater()
    app.processEvents()


def menu(editor):
    return editor.configuration()['menu']


def modal(app, callback, operation):
    """Always close the nested loop, also on assertions inside its callback."""
    errors = []
    def exercise():
        dialog = app.activeModalWidget()
        try:
            callback(dialog)
        except BaseException as exc:
            errors.append(exc)
        finally:
            if dialog.isVisible():
                QDialog.reject(dialog)
    QTimer.singleShot(0, exercise)
    operation()
    if errors:
        raise errors[0]


def test_duplicate_nested_metadata_independence_and_undo_selection(editor):
    original = menu(editor)
    editor.tree.setCurrentItem(editor.item_for((0,)))
    editor.item_for((0, 1)).setExpanded(False)
    editor.duplicate_selected()
    assert menu(editor)[0] == menu(editor)[1] == original[0]
    assert editor.path_for(editor.tree.currentItem()) == (1,)
    copy_child = editor.item_for((1, 0))
    data = copy_child.data(0, Qt.UserRole)
    data['custom']['keep'] = False
    copy_child.setData(0, Qt.UserRole, data)
    assert menu(editor)[0]['items'][0]['custom']['keep'] is True
    editor.undo_stack.undo()
    assert menu(editor) == original and not editor.is_dirty()
    assert editor.path_for(editor.tree.currentItem()) == (0,)
    assert not editor.item_for((0, 1)).isExpanded()
    editor.undo_stack.redo()
    assert menu(editor)[1] == original[0]
    assert editor.undo_stack.count() == 1


def test_reorder_into_out_of_submenu_preserves_whole_subtree(editor):
    original = menu(editor)
    tree = editor.tree
    assert tree.drop_item(editor.item_for((1,)), editor.item_for((0,)), QAbstractItemView.OnItem)
    assert menu(editor)[0]['items'][-1] == original[1]
    assert tree.drop_item(editor.item_for((0, 1)), None, QAbstractItemView.OnViewport)
    assert menu(editor)[-1] == original[0]['items'][1]
    assert tree.drop_item(editor.item_for((2,)), editor.item_for((0,)), QAbstractItemView.AboveItem)
    assert menu(editor)[0] == original[0]['items'][1]
    assert editor.undo_stack.count() == 3
    for _ in range(3):
        editor.undo_stack.undo()
    assert menu(editor) == original
    for _ in range(3):
        editor.undo_stack.redo()
    assert menu(editor)[0] == original[0]['items'][1]


def test_qt_drop_event_uses_item_at_position_and_indicator(editor, app, monkeypatch):
    tree = editor.tree
    source, destination = editor.item_for((1,)), editor.item_for((0,))
    tree.setCurrentItem(source)
    app.processEvents()
    class InternalDrop(QDropEvent):
        def source(self):
            return tree
    event = InternalDrop(QPointF(tree.visualItemRect(destination).center()), Qt.MoveAction,
                         QMimeData(), Qt.LeftButton, Qt.NoModifier)
    monkeypatch.setattr(tree, 'dropIndicatorPosition', lambda: QAbstractItemView.OnItem)
    tree.dropEvent(event)
    assert event.isAccepted() and event.dropAction() == Qt.MoveAction
    assert menu(editor)[0]['items'][-1]['label'] == 'Outside'
    assert editor.undo_stack.count() == 1
    external = QDropEvent(QPointF(0, 0), Qt.MoveAction, QMimeData(), Qt.LeftButton, Qt.NoModifier)
    tree.dropEvent(external)
    assert not external.isAccepted() and editor.undo_stack.count() == 1


def test_cycles_noops_and_non_submenu_drop_create_no_history(editor):
    original = menu(editor)
    assert not editor.tree.drop_item(editor.item_for((0,)), editor.item_for((0,)), QAbstractItemView.OnItem)
    assert not editor.tree.drop_item(editor.item_for((0,)), editor.item_for((0, 1)), QAbstractItemView.OnItem)
    assert not editor.tree.drop_item(editor.item_for((0,)), editor.item_for((1,)), QAbstractItemView.OnItem)
    assert not editor.tree.drop_item(editor.item_for((1,)), editor.item_for((1,)), QAbstractItemView.AboveItem)
    assert menu(editor) == original and editor.undo_stack.count() == 0


@pytest.mark.parametrize('limit', ['depth', 'count', 'duplicate-count'])
def test_invalid_move_or_duplicate_rolls_back_entire_state(editor, limit):
    config = editor.configuration()
    if limit == 'depth':
        nested = {'action': 'files'}
        for _ in range(8):
            nested = {'submenu': 'Deep', 'items': [nested]}
        config['menu'] = [nested, {'submenu': 'Extra', 'items': [{'action': 'files'}]}]
        target_path = (0,) * 8
    else:
        config['menu'] = [{'submenu': 'Full', 'items': [{'action': 'files'} for _ in range(200)]},
                          {'action': 'terminal'}]
        target_path = (0,)
    editor.load_state(config, editor.revision)
    before = editor.capture_layout()
    if limit == 'duplicate-count':
        editor.tree.setCurrentItem(editor.item_for((0, 0)))
        editor.duplicate_selected()
    else:
        assert not editor.tree.drop_item(editor.item_for((1,)), editor.item_for(target_path), QAbstractItemView.OnItem)
    assert menu(editor) == before['menu'] and editor.undo_stack.count() == 0
    assert editor.warnings


def test_add_edit_remove_defaults_and_cancel_are_logical_undo_steps(editor, app, monkeypatch):
    original = menu(editor)
    editor.tree.setCurrentItem(editor.item_for((1,)))
    editor.add_entry({'separator': True, 'custom': 'kept'}, edit=False)
    editor.remove_selected()
    assert menu(editor) == original
    editor.undo_stack.undo()
    editor.undo_stack.undo()
    assert menu(editor) == original and not editor.is_dirty()
    editor.tree.setCurrentItem(editor.item_for((1,)))
    modal(app, lambda dialog: dialog.reject(), editor.edit_selected)
    assert editor.undo_stack.index() == 0
    modal(app, lambda dialog: dialog.accept(), editor.edit_selected)
    assert editor.undo_stack.index() == 0  # unchanged dialog is ineffective
    def change(dialog):
        dialog.name.setText('Renamed')
        dialog.argv.setText("echo 'spaces stay together'")
        dialog.accept()
    modal(app, change, editor.edit_selected)
    assert menu(editor)[1]['command'] == ['echo', 'spaces stay together']
    assert editor.undo_stack.index() == 1
    editor.undo_stack.undo()
    assert menu(editor) == original
    editor.backup_retention.setValue(3)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Yes)
    editor.restore_defaults()
    assert menu(editor) == DEFAULT_CONFIG['menu'] and editor.backup_retention.value() == 3
    editor.undo_stack.undo()
    assert menu(editor) == original and editor.backup_retention.value() == 3


def test_invalid_entry_dialog_stays_open_and_focuses_command(editor, app):
    editor.tree.setCurrentItem(editor.item_for((1,)))
    def invalid(dialog):
        dialog.argv.setText("echo 'unclosed")
        dialog.accept()
        assert dialog.isVisible()
        assert dialog.focusWidget() is dialog.argv
        assert 'quoting' in editor.warnings[-1]
    modal(app, invalid, editor.edit_selected)
    assert editor.undo_stack.count() == 0 and not editor.is_dirty()


def test_keyboard_shortcuts_and_button_states(editor, app):
    assert not any(button.isEnabled() for button in editor.edit_buttons.values())
    editor.tree.setCurrentItem(editor.item_for((1,)))
    editor.tree.setFocus()
    app.processEvents()
    QTest.keyClick(editor.tree, Qt.Key_D, Qt.ControlModifier)
    assert editor.tree.topLevelItemCount() == 4
    QTest.keyClick(editor.tree, Qt.Key_Z, Qt.ControlModifier)
    assert editor.tree.topLevelItemCount() == 3
    QTest.keyClick(editor.tree, Qt.Key_Y, Qt.ControlModifier)
    assert editor.tree.topLevelItemCount() == 4
    QTest.keyClick(editor.tree, Qt.Key_Delete)
    assert editor.tree.topLevelItemCount() == 3
    editor.tree.setCurrentItem(editor.item_for((1,)))
    QTest.keyClick(editor.tree, Qt.Key_Right, Qt.AltModifier)
    assert editor.path_for(editor.tree.currentItem()) == (0, 2)
    QTest.keyClick(editor.tree, Qt.Key_Left, Qt.AltModifier)
    assert editor.path_for(editor.tree.currentItem()) == (1,)
    editor.tree.setCurrentItem(editor.item_for((2,)))
    assert not editor.edit_buttons['Edit'].isEnabled()
    assert not editor.edit_buttons['Move down'].isEnabled()
    editor.move_selected(-1)
    assert menu(editor)[1]['separator']
    editor.undo_stack.undo()
    assert menu(editor)[2]['separator']


@pytest.mark.parametrize('close_method', ['reject', 'escape', 'window'])
def test_dirty_cancel_and_discard_cover_closing_paths(editor, close_method, monkeypatch, app):
    before = editor.target.read_bytes()
    editor.backup_retention.setValue(0)
    assert editor.is_dirty() and editor.isWindowModified()
    def close():
        if close_method == 'escape':
            QTest.keyClick(editor, Qt.Key_Escape)
        elif close_method == 'window':
            editor.close()
        else:
            editor.reject()
    close()
    assert editor.isVisible() and editor.target.read_bytes() == before
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Discard)
    close()
    assert not editor.isVisible() and editor.target.read_bytes() == before


def test_clean_close_does_not_prompt_and_dirty_save_writes_before_close(editor, monkeypatch):
    def unexpected(*args):
        pytest.fail('unchanged editor prompted')
    monkeypatch.setattr(QMessageBox, 'question', unexpected)
    editor.reject()
    assert not editor.isVisible()
    editor._closing = False
    editor.show()
    editor.backup_retention.setValue(0)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Save)
    editor.reject()
    assert not editor.isVisible()
    assert json.loads(editor.target.read_text())['backup_retention'] == 0


@pytest.mark.parametrize('choice', ['cancel', 'reload', 'overwrite'])
def test_external_conflict_options(editor, monkeypatch, choice):
    editor.backup_retention.setValue(0)
    external = {**editor.saved_config, 'menu': [{'action': 'terminal'}]}
    editor.target.write_text(json.dumps(external))
    before = editor.target.read_bytes()
    monkeypatch.setattr(editor, 'conflict_choice', lambda: choice)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Discard)
    editor.accept()
    if choice == 'overwrite':
        assert not editor.isVisible()
        assert json.loads(editor.target.read_text())['backup_retention'] == 0
        assert list(editor.target.parent.glob('menu.json.pre-overwrite-*'))[0].read_bytes() == before
    elif choice == 'reload':
        assert editor.isVisible() and not editor.is_dirty()
        assert menu(editor) == external['menu'] and editor.undo_stack.count() == 0
    else:
        assert editor.isVisible() and editor.is_dirty()
    if choice != 'overwrite':
        assert editor.target.read_bytes() == before


def test_failed_save_keeps_dirty_window_and_validation_selects_entry(editor, monkeypatch):
    before = editor.target.read_bytes()
    item = editor.item_for((0, 0))
    data = item.data(0, Qt.UserRole)
    data['command'] = 'invalid'
    item.setData(0, Qt.UserRole, data)
    assert not editor.accept()
    assert editor.path_for(editor.tree.currentItem()) == (0, 0)
    assert editor.isVisible() and 'Nested' in editor.warnings[-1]
    data['command'] = ['echo']
    item.setData(0, Qt.UserRole, data)
    def fail(*args, **kwargs):
        raise OSError('permission denied')
    monkeypatch.setattr('openpowermenu.editor.save_config', fail)
    assert not editor.accept()
    assert editor.isVisible() and editor.is_dirty() and editor.target.read_bytes() == before


def test_backup_dialog_preview_corrupt_missing_and_restore(editor, monkeypatch, app):
    source = editor.target.with_name('menu.json.bak-manual')
    restored = {**editor.saved_config, 'menu': [{'action': 'files'}], 'backup_retention': 0}
    source.write_text(json.dumps(restored))
    corrupt = editor.target.with_name('menu.json.bak-corrupt')
    corrupt.write_text('{broken')
    dialog = BackupDialog(editor.target, editor)
    dialog.show()
    app.processEvents()
    assert dialog.files.topLevelItem(0).text(3) == 'Active'
    def select(name):
        row = next(dialog.files.topLevelItem(i) for i in range(dialog.files.topLevelItemCount())
                   if dialog.files.topLevelItem(i).data(0, Qt.UserRole) == name)
        dialog.files.setCurrentItem(row)
    select(corrupt.name)
    assert not dialog.restore_button.isEnabled() and 'Invalid' in dialog.preview.toPlainText()
    select(source.name)
    assert dialog.restore_button.isEnabled() and '1 entries' in dialog.preview.toPlainText()
    before = editor.target.read_bytes()
    dialog.restore_selected()  # default cancel
    assert not dialog.restored and editor.target.read_bytes() == before
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Yes)
    source.unlink()
    dialog.restore_selected()
    assert not dialog.restored and editor.target.read_bytes() == before
    source.write_text(json.dumps(restored))
    dialog.refresh()
    select(source.name)
    dialog.restore_selected()
    assert dialog.restored and decode_configuration(editor.target.read_bytes()) == restored
    assert source.exists()
    assert list(editor.target.parent.glob('menu.json.pre-restore-*'))[0].read_bytes() == before
    dialog.deleteLater()


def test_backup_restore_refreshes_editor_only_after_success(editor, app, monkeypatch):
    source = editor.target.with_name('menu.json.bak-manual')
    restored = {**editor.saved_config, 'menu': [], 'backup_retention': 0}
    source.write_text(json.dumps(restored))
    editor.add_entry({'action': 'terminal'}, edit=False)
    def approve(parent, title, *args):
        return QMessageBox.Discard if title == 'Restore backup' else QMessageBox.Yes
    monkeypatch.setattr(QMessageBox, 'question', approve)
    def choose(dialog):
        dialog.files.setCurrentItem(dialog.files.topLevelItem(1))
        dialog.restore_selected()
    modal(app, choose, editor.manage_backups)
    assert menu(editor) == [] and not editor.is_dirty() and editor.undo_stack.count() == 0
    assert editor.revision == current_revision(editor.target)


def test_nested_edit_save_reopen_round_trip(editor):
    editor.tree.setCurrentItem(editor.item_for((0,)))
    editor.duplicate_selected()
    editor.tree.drop_item(editor.item_for((2,)), editor.item_for((1, 1)), QAbstractItemView.OnItem)
    expected = editor.configuration()
    assert editor.accept()
    reopened = create_editor(editor.target)
    try:
        assert reopened.configuration() == expected
        assert not reopened.is_dirty()
        assert menu(reopened)[1]['items'][1]['items'][-1]['command'] == ['echo', 'outside']
        assert menu(reopened)[0]['extra'] == {'keep': [1]}
    finally:
        reopened.reject()
        reopened.deleteLater()
