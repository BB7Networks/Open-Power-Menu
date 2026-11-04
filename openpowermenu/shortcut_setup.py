"""Discover KDE's supported shortcut UI; never register or rewrite shortcuts."""
import os
from pathlib import Path
import shlex
import shutil


def installed_command():
    preferred = Path(os.environ.get('XDG_BIN_HOME') or Path.home() / '.local/bin') / 'open-power-menu'
    if preferred.is_file() and os.access(preferred, os.X_OK):
        return shlex.join([str(preferred.absolute())])
    available = shutil.which('open-power-menu')
    return shlex.join([str(Path(available).absolute())]) if available else None


def settings_command():
    for program in ('kcmshell6', 'systemsettings'):
        executable = shutil.which(program)
        if executable:
            return [executable, 'kcm_keys']
    return None


def create_shortcut_dialog(parent=None):
    from PySide6.QtCore import QProcess, Qt
    from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QHBoxLayout,
                                  QLabel, QLineEdit, QPushButton, QVBoxLayout)

    class ShortcutDialog(QDialog):
        def __init__(self):
            super().__init__(parent)
            self.setWindowTitle('Open Power Menu — Set up Meta+X')
            self.resize(570, 350)
            layout = QVBoxLayout(self)
            explanation = QLabel(
                '<b>Open the standalone Power User Menu with Meta+X</b>'
                '<p>It uses your saved menu configuration.</p>'
                '<ol><li>Open KDE Shortcuts.</li>'
                '<li>Choose <b>Add New → Command or Script…</b> and paste the command below.</li>'
                '<li>Assign <b>Meta+X</b> and select <b>Apply</b>.</li></ol>'
                '<p>If KDE reports a conflict, choose another shortcut or cancel. '
                'You can change or remove the assignment in KDE Shortcuts.</p>', self)
            explanation.setTextFormat(Qt.RichText)
            explanation.setWordWrap(True)
            layout.addWidget(explanation)
            row = QHBoxLayout()
            command = installed_command()
            self.command = QLineEdit(command or '', self)
            self.command.setObjectName('shortcutCommand')
            self.command.setAccessibleName('Installed standalone menu command')
            self.command.setReadOnly(True)
            self.command.setPlaceholderText('Install Open Power Menu first')
            row.addWidget(self.command, 1)
            copy = QPushButton('Copy command', self)
            copy.setObjectName('copyShortcutCommand')
            copy.setEnabled(bool(command))
            copy.clicked.connect(lambda: QApplication.clipboard().setText(self.command.text()))
            row.addWidget(copy)
            layout.addLayout(row)
            open_settings = QPushButton('Open KDE Shortcuts', self)
            open_settings.setObjectName('openKdeShortcuts')
            open_settings.clicked.connect(self.open_settings)
            layout.addWidget(open_settings, 0, Qt.AlignLeft)
            self.status = QLabel('Finish assigning and applying the shortcut in KDE.' if command else
                                'Run bash install.sh from the complete package, then reopen this setup.', self)
            self.status.setObjectName('shortcutSetupStatus')
            self.status.setWordWrap(True)
            layout.addWidget(self.status)
            layout.addStretch(1)
            close = QDialogButtonBox(QDialogButtonBox.Close, self)
            close.rejected.connect(self.reject)
            layout.addWidget(close)

        def open_settings(self):
            argv = settings_command()
            if not argv:
                self.status.setText('KDE Shortcuts is unavailable in this session. On your Plasma 6 desktop, '
                                    'open System Settings → Keyboard → Shortcuts.')
                return
            try:
                started, _pid = QProcess.startDetached(argv[0], argv[1:])
            except (OSError, RuntimeError):
                started = False
            self.status.setText('KDE shortcut settings opened. Finish assigning and applying the shortcut there.'
                                if started else 'Could not open KDE Shortcuts. Open System Settings → Keyboard → Shortcuts on your desktop.')

    return ShortcutDialog()
