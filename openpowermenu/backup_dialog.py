"""Non-executing configuration history browser and explicit atomic restore."""
from html import escape
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                              QMessageBox, QPlainTextEdit, QPushButton,
                              QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from .recovery import (configuration_directory, configuration_summary, current_revision,
                       decode_configuration, list_backups, read_at, restore_backup,
                       backup_deletion_revision, delete_backup, is_protected_backup)


class BackupDialog(QDialog):
    def __init__(self, target, parent=None, before_restore=lambda: True):
        super().__init__(parent)
        self.target, self.before_restore = target, before_restore
        self.restored = False
        self.preview_revision = None
        self.deletion_revision = None
        self.setWindowTitle('Open Power Menu — Configuration backups')
        self.resize(780, 580)
        layout = QVBoxLayout(self)
        help_text = QLabel('Preview a backup before restoring. A separate recovery copy protects the current '
                           'file, even when automatic backups are off.')
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.files = QTreeWidget(self)
        self.files.setObjectName('configurationBackupList')
        self.files.setHeaderLabels(['Configuration', 'Saved (local time)', 'Bytes', 'Status'])
        self.files.setRootIsDecorated(False)
        self.files.setAccessibleName('Configuration history')
        self.files.setColumnWidth(0, 330)
        layout.addWidget(self.files, 1)
        self.preview = QPlainTextEdit(self)
        self.preview.setObjectName('backupPreview')
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName('Backup contents and differences')
        layout.addWidget(self.preview, 1)
        row = QHBoxLayout()
        refresh = QPushButton('Refresh', self)
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        self.restore_button = QPushButton('Restore selected backup…', self)
        self.restore_button.clicked.connect(self.restore_selected)
        row.addWidget(self.restore_button)
        self.delete_button = QPushButton('Delete selected backup…', self)
        self.delete_button.setObjectName('deleteBackupButton')
        self.delete_button.setToolTip('Permanently delete one selected configuration backup. This cannot be undone.')
        self.delete_button.clicked.connect(self.delete_selected)
        row.addWidget(self.delete_button)
        row.addStretch(1)
        close = QDialogButtonBox(QDialogButtonBox.Close, self)
        close.rejected.connect(self.reject)
        row.addWidget(close)
        layout.addLayout(row)
        self.files.currentItemChanged.connect(self.show_preview)
        self.refresh()

    def refresh(self, *, selected=None, fallback_index=0):
        if selected is None and self.files.currentItem():
            selected = self.files.currentItem().data(0, Qt.UserRole)
        self.files.clear()
        self.active = None
        self.restore_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.deletion_revision = None
        try:
            self.active_revision = current_revision(self.target)
            try:
                self.active = decode_configuration(self.active_revision.content)
                status = 'Active' if self.active_revision.content is not None else 'Defaults (no file yet)'
            except ValueError as exc:
                status = str(exc)
            active = QTreeWidgetItem(['Current configuration', '', str(len(self.active_revision.content or b'')), status])
            active.setData(0, Qt.UserRole, None)
            self.files.addTopLevelItem(active)
            for backup in list_backups(self.target):
                item = QTreeWidgetItem([backup.name, backup.local_time, str(backup.size),
                                        'Valid' if backup.config is not None else 'Invalid / unreadable'])
                item.setData(0, Qt.UserRole, backup.name)
                item.setToolTip(0, backup.name)
                item.setToolTip(3, backup.error)
                self.files.addTopLevelItem(item)
            selection = next((self.files.topLevelItem(index) for index in range(self.files.topLevelItemCount())
                              if self.files.topLevelItem(index).data(0, Qt.UserRole) == selected), None)
            self.files.setCurrentItem(selection or self.files.topLevelItem(min(fallback_index, self.files.topLevelItemCount() - 1)))
        except (ValueError, OSError) as exc:
            self.preview.setPlainText(str(exc))

    def show_preview(self, item, previous=None):
        self.restore_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.preview_revision = None
        self.deletion_revision = None
        if item is None:
            return
        name = item.data(0, Qt.UserRole)
        try:
            if name is None:
                self.preview.setPlainText(configuration_summary(self.active) if self.active else item.text(3))
                return
            try:
                self.deletion_revision = backup_deletion_revision(self.target, name)
                self.delete_button.setEnabled(True)
                item.setText(1, self.deletion_revision.local_time)
                item.setText(2, str(self.deletion_revision.size))
                self.delete_button.setToolTip('Protected recovery copy: deleting it removes this rollback point.'
                    if is_protected_backup(self.target, name) else 'Permanently delete this backup. This cannot be undone.')
            except (ValueError, OSError) as exc:
                self.delete_button.setToolTip(str(exc))
            with configuration_directory(self.target) as directory:
                self.preview_revision = read_at(directory, name)
            if self.preview_revision.content is None:
                raise FileNotFoundError('This backup no longer exists. Refresh the list.')
            config = decode_configuration(self.preview_revision.content)
            self.preview.setPlainText(configuration_summary(config, self.active))
            self.restore_button.setEnabled(True)
        except (ValueError, OSError) as exc:
            self.preview.setPlainText(str(exc))

    def delete_selected(self):
        item = self.files.currentItem()
        if not item or not item.data(0, Qt.UserRole) or self.deletion_revision is None:
            return
        name, revision = item.data(0, Qt.UserRole), self.deletion_revision
        index = self.files.indexOfTopLevelItem(item)
        protected = is_protected_backup(self.target, name)
        warning = ('\n\nThis is a protected pre-restore/pre-overwrite recovery copy. '
                   'Deleting it removes this rollback point.' if protected else '')
        message = (f'Delete this backup permanently?\n\n{name}\nSaved: {revision.local_time}\n'
                   f'Size: {revision.size:,} bytes{warning}\n\nThis cannot be undone. The active configuration stays intact.')
        # A manual backup name may contain '<' or '&'; display it literally.
        prompt = '<p>' + escape(message).replace('\n', '<br>') + '</p>'
        if QMessageBox.question(self, 'Delete configuration backup', prompt,
                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes:
            return
        try:
            delete_backup(self.target, name, revision, confirm_protected=protected)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, 'Could not delete backup', str(exc))
            self.delete_button.setEnabled(False)
            self.deletion_revision = None
            return
        self.refresh(selected=name, fallback_index=index)

    def restore_selected(self):
        item = self.files.currentItem()
        if not item or not item.data(0, Qt.UserRole) or self.preview_revision is None:
            return
        if not self.before_restore():
            return
        if QMessageBox.question(self, 'Restore configuration',
                'Replace the current configuration with this backup? A separate pre-restore recovery '
                'copy of the current file will be kept. The backup is validated before replacement.',
                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes:
            return
        try:
            restore_backup(self.target, item.data(0, Qt.UserRole), self.active_revision,
                           expected_source=self.preview_revision)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, 'Could not restore backup', str(exc))
            return
        self.restored = True
        self.accept()
