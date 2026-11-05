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
from PySide6.QtWidgets import QApplication, QAbstractItemView, QDialog, QLabel, QMessageBox, QPushButton

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
    def approve(parent, title, *args):
        return QMessageBox.Discard if title == 'Restore backup' else QMessageBox.Yes
    monkeypatch.setattr(QMessageBox, 'question', approve)
    def choose(dialog):
        dialog.files.setCurrentItem(dialog.files.topLevelItem(1))
        dialog.restore_selected()
    modal(app, choose, editor.manage_backups)
    assert menu(editor) == [] and not editor.is_dirty() and editor.undo_stack.count() == 0
    assert editor.revision == current_revision(editor.target)


def test_backups_never_discard_unsaved_editor_changes(editor, app, monkeypatch):
    source = editor.target.with_name('menu.json.bak-manual')
    source.write_text(json.dumps({**editor.saved_config, 'menu': []}))
    editor.add_entry({'action': 'terminal'}, edit=False)
    editor.appearance.setCurrentIndex(1)
    editor.backup_retention.setValue(3)
    before, content = editor.configuration(), editor.target.read_bytes()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Yes)
    def choose(dialog):
        dialog.files.setCurrentItem(dialog.files.topLevelItem(1))
        assert dialog.restore_button.isEnabled()
        dialog.restore_selected()
        assert not dialog.restored
    modal(app, choose, editor.manage_backups)
    assert editor.configuration() == before and editor.is_dirty()
    assert editor.target.read_bytes() == content and editor.undo_stack.count() == 1
    assert 'Save or discard' in editor.warnings[-1]


def test_three_tabs_instructions_and_responsive_history_controls(editor, app):
    assert [editor.tabs.tabText(i) for i in range(editor.tabs.count())] == ['General', 'Layout', 'Backups']
    assert editor.tabs.widget(2).isAncestorOf(editor.backup_retention)
    assert editor.findChild(QPushButton, 'manageBackupsButton').text() == 'Manage / Restore Backups…'
    assert 'widget-backups' in editor.snapshot_location.text()
    instructions = editor.findChild(QLabel, 'layoutInstructions')
    assert instructions.text().count('<li>') == 4
    assert 'Drag' in instructions.accessibleName()
    editor.resize(1200, 700)
    app.processEvents()
    history = editor.toolbar.history
    assert history.x() > editor.edit_buttons['Move down'].geometry().right()
    for width in (620, 950):
        editor.resize(width, 600)
        app.processEvents()
        for button in editor.toolbar.editing + [history]:
            assert button.x() >= 0 and button.geometry().right() < editor.toolbar.width()
            assert button.y() >= 0 and button.geometry().bottom() < editor.toolbar.height()


@pytest.mark.parametrize('protected', [False, True])
def test_backup_delete_confirmation_corrupt_preview_and_selection_refresh(editor, monkeypatch, app, protected):
    name = 'menu.json.pre-restore-test' if protected else 'menu.json.bak-manual'
    source = editor.target.with_name(name)
    source.write_text('{broken backup')
    another = editor.target.with_name('menu.json.bak-keep')
    another.write_bytes(editor.target.read_bytes())
    active = editor.target.read_bytes()
    dialog = BackupDialog(editor.target, editor)
    assert not dialog.delete_button.isEnabled()
    selected = next(dialog.files.topLevelItem(i) for i in range(dialog.files.topLevelItemCount())
                    if dialog.files.topLevelItem(i).data(0, Qt.UserRole) == name)
    dialog.files.setCurrentItem(selected)
    assert dialog.delete_button.isEnabled() and not dialog.restore_button.isEnabled()
    messages = []
    def cancel(parent, title, message, *buttons):
        messages.append(message)
        assert buttons[-1] == QMessageBox.Cancel
        return QMessageBox.Cancel
    monkeypatch.setattr(QMessageBox, 'question', cancel)
    dialog.delete_selected()
    assert source.exists() and 'cannot be undone' in messages[-1]
    assert name in messages[-1] and 'bytes' in messages[-1] and 'Saved:' in messages[-1]
    assert ('protected' in messages[-1]) == protected
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Yes)
    dialog.delete_selected()
    assert not source.exists() and another.exists() and editor.target.read_bytes() == active
    assert dialog.files.currentItem().data(0, Qt.UserRole) == another.name
    assert dialog.files.topLevelItemCount() == 2 and not dialog.restored
    dialog.deleteLater()


@pytest.mark.parametrize('change', ['changed', 'missing', 'denied'])
def test_backup_delete_conflicts_and_errors_keep_active_configuration(editor, monkeypatch, app, change):
    source = editor.target.with_name('menu.json.bak-test')
    source.write_bytes(editor.target.read_bytes())
    active = editor.target.read_bytes()
    dialog = BackupDialog(editor.target, editor)
    dialog.files.setCurrentItem(dialog.files.topLevelItem(1))
    def confirm(*args):
        if change == 'changed': source.write_bytes(b'changed during confirmation')
        elif change == 'missing': source.unlink()
        return QMessageBox.Yes
    monkeypatch.setattr(QMessageBox, 'question', confirm)
    if change == 'denied':
        monkeypatch.setattr('openpowermenu.backup_dialog.delete_backup', lambda *a, **kw: (_ for _ in ()).throw(PermissionError('denied')))
    dialog.delete_selected()
    assert editor.target.read_bytes() == active and not dialog.restored
    assert not dialog.delete_button.isEnabled() and editor.warnings
    if change != 'missing': assert source.exists()
    dialog.deleteLater()


def test_backup_delete_confirmation_displays_literal_manual_name(editor, monkeypatch):
    source = editor.target.with_name('menu.json.bak-<old>&saved')
    source.write_bytes(editor.target.read_bytes())
    dialog = BackupDialog(editor.target, editor)
    dialog.files.setCurrentItem(dialog.files.topLevelItem(1))
    prompts = []
    monkeypatch.setattr(QMessageBox, 'question', lambda parent, title, prompt, *args:
                        prompts.append(prompt) or QMessageBox.Cancel)
    dialog.delete_selected()
    assert 'menu.json.bak-&lt;old&gt;&amp;saved' in prompts[0]
    assert source.exists()
    dialog.deleteLater()


def test_backups_tab_refreshes_count_on_return_without_changing_unsaved_settings(editor, app, tmp_path, monkeypatch):
    from openpowermenu.widget_snapshots import recovery_path
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    editor.refresh_snapshots()
    assert 'No widget snapshots' in editor.snapshot_location.text()
    root = recovery_path(tmp_path / 'data')
    snapshot = root / 'org.openpowermenu.start-20260101-010101-000000000'
    snapshot.mkdir(parents=True)
    editor.backup_retention.setValue(5)
    before = editor.configuration()
    files_before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob('*'))
    editor.tabs.setCurrentIndex(2)
    assert editor.findChild(QPushButton, 'widgetSnapshotRefresh') is None
    assert '1 generated snapshots' in editor.snapshot_location.text()
    assert editor.configuration() == before and editor.is_dirty()
    assert editor.snapshot_location.textInteractionFlags() & Qt.TextSelectableByKeyboard
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob('*')) == files_before
    editor.tabs.setCurrentIndex(0)
    snapshot.rmdir()
    assert '1 generated snapshots' in editor.snapshot_location.text()  # No polling.
    editor.tabs.setCurrentIndex(2)
    assert 'No widget snapshots' in editor.snapshot_location.text()
    assert editor.configuration() == before and editor.is_dirty()


def test_emergency_restore_is_separate_selectable_and_copyable(editor, app):
    command = editor.findChild(QLabel, 'emergencyRestoreCommand')
    assert command.text() == 'open-power-menu --show-launcher-button'
    assert command.wordWrap() and command.textFormat() == Qt.PlainText
    assert command.textInteractionFlags() & Qt.TextSelectableByKeyboard
    editor.tabs.setCurrentIndex(0)
    editor.resize(620, 620)
    app.processEvents()
    assert command.height() >= command.heightForWidth(command.width())
    enlarged = command.font()
    enlarged.setPointSizeF(enlarged.pointSizeF() * 1.75)
    command.setFont(enlarged)
    QTest.qWait(30)
    assert command.height() >= command.heightForWidth(command.width())
    editor.findChild(QPushButton, 'copyEmergencyRestore').click()
    assert app.clipboard().text() == command.text()
    assert not editor.is_dirty()


def test_shortcut_setup_uses_kde_ui_without_claiming_or_changing_bindings(editor, app, monkeypatch, tmp_path):
    from PySide6.QtCore import QProcess
    from openpowermenu.shortcut_setup import create_shortcut_dialog
    shortcuts = tmp_path / 'kglobalshortcutsrc'
    shortcuts.write_text('Existing shortcut=Meta+X\n')
    before = editor.configuration()
    monkeypatch.setattr('openpowermenu.shortcut_setup.installed_command', lambda: "'/home/test user/.local/bin/open-power-menu'")
    monkeypatch.setattr('openpowermenu.shortcut_setup.settings_command', lambda: ['/usr/bin/kcmshell6', 'kcm_keys'])
    launches = []
    monkeypatch.setattr(QProcess, 'startDetached', lambda program, args: (launches.append([program, *args]) or True, 123))
    dialog = create_shortcut_dialog(editor)
    assert dialog.command.isReadOnly()
    dialog.findChild(QPushButton, 'copyShortcutCommand').click()
    assert app.clipboard().text() == dialog.command.text()
    dialog.findChild(QPushButton, 'openKdeShortcuts').click()
    assert launches == [['/usr/bin/kcmshell6', 'kcm_keys']]
    assert 'settings opened' in dialog.status.text() and 'applying' in dialog.status.text()
    explanation = ' '.join(label.text() for label in dialog.findChildren(QLabel))
    assert 'standalone' in explanation and 'conflict' in explanation and 'cancel' in explanation
    assert shortcuts.read_text() == 'Existing shortcut=Meta+X\n'
    assert editor.configuration() == before and not editor.is_dirty()
    dialog.deleteLater()


def test_shortcut_setup_missing_services_and_failed_launch_are_clear(editor, app, monkeypatch):
    from PySide6.QtCore import QProcess
    from openpowermenu.shortcut_setup import create_shortcut_dialog
    monkeypatch.setattr('openpowermenu.shortcut_setup.installed_command', lambda: None)
    monkeypatch.setattr('openpowermenu.shortcut_setup.settings_command', lambda: None)
    dialog = create_shortcut_dialog(editor)
    assert not dialog.findChild(QPushButton, 'copyShortcutCommand').isEnabled()
    assert 'bash install.sh' in dialog.status.text()
    dialog.open_settings()
    assert 'unavailable' in dialog.status.text()
    monkeypatch.setattr('openpowermenu.shortcut_setup.settings_command', lambda: ['systemsettings', 'kcm_keys'])
    monkeypatch.setattr(QProcess, 'startDetached', lambda *args: (False, 0))
    dialog.open_settings()
    assert 'Could not open' in dialog.status.text()
    dialog.deleteLater()


def test_general_does_not_require_shortcut_setup(editor, app):
    assert editor.findChild(QPushButton, 'setupMenuShortcut') is None
    assert not editor.is_dirty()


@pytest.mark.parametrize('result', ['missing', 'error', 'quiet', 'exposed'])
def test_shortcut_test_invokes_installed_process_and_distinguishes_outcomes(editor, app, tmp_path, monkeypatch, result):
    import shlex
    import sys
    from PySide6.QtCore import QProcess
    from openpowermenu.shortcut_setup import create_shortcut_dialog
    program = tmp_path / "installed menu ' $literal"
    argv_log = tmp_path / 'argv.json'
    body = {
        'error': "print('Missing Qt dependency', file=sys.stderr); sys.exit(2)",
        'quiet': 'sys.exit(0)',
        'exposed': "print('OPM_LAUNCH broken'); print('OPM_LAUNCH []'); "
                   "print('OPM_LAUNCH '+json.dumps(dict(exposed=True, active=True)), flush=True)",
    }.get(result, '')
    if result != 'missing':
        program.write_text(f'#!{sys.executable}\nimport json,sys\nfrom pathlib import Path\n'
                           f'Path({str(argv_log)!r}).write_text(json.dumps(sys.argv[1:]))\n' + body + '\n')
        program.chmod(0o755)
    monkeypatch.setattr('openpowermenu.shortcut_setup.installed_command', lambda: shlex.join([str(program)]))
    before = editor.configuration()
    dialog = create_shortcut_dialog(editor)
    dialog.test_button.click()
    for _ in range(100):
        QTest.qWait(10)
        if dialog.test_button.isEnabled() and dialog.process.state() == QProcess.NotRunning:
            break
    assert dialog.test_button.isEnabled()
    if result == 'missing':
        assert 'Could not start' in dialog.status.text()
    else:
        assert json.loads(argv_log.read_text()) == ['--diagnose-launch']
        if result == 'error':
            assert 'failed (exit 2)' in dialog.status.text()
            assert 'Missing Qt dependency' in dialog.details.toPlainText()
        elif result == 'quiet':
            assert 'without reporting an exposed' in dialog.status.text()
        else:
            assert 'exposed window with focus' in dialog.status.text()
            assert 'Meta+X separately' in dialog.status.text()
    assert editor.configuration() == before and not editor.is_dirty()
    dialog.reject()
    dialog.deleteLater()


@pytest.mark.parametrize('dismissal', ['escape', 'deactivate', 'action', 'submenu'])
def test_wayland_standalone_is_a_toplevel_with_menu_navigation(app, monkeypatch, dismissal):
    from PySide6.QtWidgets import QMenu
    from openpowermenu.gui import launch_menu
    config = deepcopy(DEFAULT_CONFIG)
    config['menu'] = [{'label': 'Safe test', 'command': ['echo', 'test']},
                      {'submenu': 'Group', 'items': [{'label': 'Child', 'command': ['echo', 'child']}]}]
    monkeypatch.setattr(QApplication, 'platformName', staticmethod(lambda: 'wayland'))
    launched, reports, errors = [], [], []
    monkeypatch.setattr('openpowermenu.gui.launch_detached', lambda argv: launched.append(argv))
    def inspect():
        menu = next(w for w in app.topLevelWidgets() if isinstance(w, QMenu) and w.isVisible() and w.objectName() == 'OpenPowerMenu')
        try:
            assert menu.windowType() == Qt.Window
            if dismissal == 'escape':
                QTest.keyClick(menu, Qt.Key_Escape)
            elif dismissal == 'deactivate':
                app.applicationStateChanged.emit(Qt.ApplicationActive)
                app.applicationStateChanged.emit(Qt.ApplicationInactive)
            elif dismissal == 'action':
                QTest.mouseClick(menu, Qt.LeftButton, pos=menu.actionGeometry(menu.actions()[0]).center())
            else:
                menu.setActiveAction(menu.actions()[1])
                QTest.keyClick(menu, Qt.Key_Right)
                QTest.qWait(30)
                submenu = menu.actions()[1].menu()
                assert submenu.isVisible() and menu.isVisible()
                QTest.keyClick(submenu, Qt.Key_Escape)
                assert menu.isVisible()
                QTest.keyClick(menu, Qt.Key_Escape)
        except BaseException as exc:
            errors.append(exc)
        finally:
            menu.close()
    QTimer.singleShot(100, inspect)
    assert launch_menu(config, diagnostic=lambda event, **state: reports.append((event, state))) == 0
    if errors: raise errors[0]
    assert launched == ([['echo', 'test']] if dismissal == 'action' else [])
    assert any(state['exposed'] for _, state in reports)
    assert reports[-1][0] == 'dismissed'


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
