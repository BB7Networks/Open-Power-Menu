"""Discover KDE's supported shortcut UI; never register or rewrite shortcuts."""
import os
import json
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


def installed_application():
    """Locate our visible desktop entry using XDG precedence, without executing it."""
    from .desktop_apps import read_desktop_application
    roots = [Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')]
    roots += [Path(part) for part in (os.environ.get('XDG_DATA_DIRS') or '/usr/local/share:/usr/share').split(':') if part]
    for root in roots:
        path = root / 'applications/org.openpowermenu.desktop'
        if path.exists():  # A hidden/broken user override masks system entries.
            return path if read_desktop_application(path) else None
    return None


def create_shortcut_dialog(parent=None):
    from PySide6.QtCore import QProcess, Qt
    from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QHBoxLayout,
                                  QLabel, QLineEdit, QPushButton, QPlainTextEdit, QVBoxLayout)

    class ShortcutDialog(QDialog):
        def __init__(self):
            super().__init__(parent)
            self.setWindowTitle('Open Power Menu — Set up Meta+X')
            self.resize(620, 540)
            self.process = QProcess(self)
            self.process.started.connect(self.test_started)
            self.process.readyReadStandardOutput.connect(self.read_test_output)
            self.process.readyReadStandardError.connect(self.read_test_output)
            self.process.errorOccurred.connect(self.test_error)
            self.process.finished.connect(self.test_finished)
            self.test_output = ''
            self.test_pending = ''
            self.saw_exposed = False
            self.saw_active = False
            layout = QVBoxLayout(self)
            explanation = QLabel(
                '<b>Open the standalone Power User Menu with Meta+X</b>'
                '<p>It uses your saved configuration and opens a separate menu, not the panel instance.</p>'
                '<ol><li>Test the installed menu below. Press Esc to dismiss it.</li>'
                '<li>Open KDE Shortcuts. Choose <b>Add New → Application… → Open Power Menu</b>.</li>'
                '<li>Assign <b>Meta+X</b> and select <b>Apply</b>.</li></ol>'
                '<p>If KDE reports a conflict, choose another shortcut or cancel. '
                'For a stale Command or Script assignment, remove only that old OPM assignment, Apply, '
                'then add the application entry and Apply again. Test Meta+X on your desktop.</p>'
                '<p>If the launch test works but the key does nothing, check the assignment in KDE. '
                'Starting this test does not verify the keyboard binding.</p>', self)
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
            application = installed_application()
            entry = QLabel('Application entry: ' + str(application) if application else
                           'Application entry not found. Run bash install.sh from the complete package to install or refresh it.', self)
            entry.setObjectName('shortcutApplication')
            entry.setTextFormat(Qt.PlainText)
            entry.setWordWrap(True)
            entry.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            layout.addWidget(entry)
            self.test_button = QPushButton('Test menu launch', self)
            self.test_button.setObjectName('testMenuLaunch')
            self.test_button.setEnabled(bool(command))
            self.test_button.clicked.connect(self.test_launch)
            layout.addWidget(self.test_button, 0, Qt.AlignLeft)
            open_settings = QPushButton('Open KDE Shortcuts', self)
            open_settings.setObjectName('openKdeShortcuts')
            open_settings.clicked.connect(self.open_settings)
            layout.addWidget(open_settings, 0, Qt.AlignLeft)
            self.status = QLabel('Finish assigning and applying the shortcut in KDE.' if command else
                                'Run bash install.sh from the complete package, then reopen this setup.', self)
            self.status.setObjectName('shortcutSetupStatus')
            self.status.setTextFormat(Qt.PlainText)
            self.status.setWordWrap(True)
            layout.addWidget(self.status)
            self.details = QPlainTextEdit(self)
            self.details.setObjectName('shortcutLaunchDetails')
            self.details.setReadOnly(True)
            self.details.setAccessibleName('Local launch diagnostic output')
            self.details.setMaximumHeight(110)
            self.details.hide()
            layout.addWidget(self.details)
            layout.addStretch(1)
            close = QDialogButtonBox(QDialogButtonBox.Close, self)
            close.rejected.connect(self.reject)
            layout.addWidget(close)

        def test_launch(self):
            if self.process.state() != QProcess.NotRunning:
                return
            command = installed_command()  # Resolve again in case the installation changed.
            if not command:
                self.status.setText('Installed menu executable not found. Run bash install.sh, then reopen setup.')
                return
            self.test_output = self.test_pending = ''
            self.saw_exposed = self.saw_active = False
            self.details.clear()
            self.details.show()
            self.test_button.setEnabled(False)
            self.status.setText('Starting the installed menu…')
            argv = shlex.split(command)
            self.process.start(argv[0], [*argv[1:], '--diagnose-launch'])

        def test_started(self):
            self.status.setText('Menu process started. Waiting for window diagnostics; this does not verify Meta+X. '
                                'If the menu appears, press Esc to return here.')

        def read_test_output(self):
            output = bytes(self.process.readAllStandardOutput()).decode('utf-8', 'replace')
            errors = bytes(self.process.readAllStandardError()).decode('utf-8', 'replace')
            self.test_output = (self.test_output + output + errors)[-8192:]
            self.details.setPlainText(self.test_output)
            self.test_pending = (self.test_pending + output)[-8192:]
            while '\n' in self.test_pending:
                line, self.test_pending = self.test_pending.split('\n', 1)
                if not line.startswith('OPM_LAUNCH '):
                    continue
                try:
                    state = json.loads(line[len('OPM_LAUNCH '):])
                    if not isinstance(state, dict):
                        continue
                    self.saw_exposed |= state.get('exposed') is True
                    self.saw_active |= state.get('active') is True
                except (ValueError, TypeError):
                    continue
            if self.saw_exposed:
                self.status.setText('Qt reports an exposed menu window' +
                                    (' with focus.' if self.saw_active else '; focus has not been reported.') +
                                    ' Confirm it is visible on your desktop, then press Esc. Meta+X must be tested separately.')

        def test_error(self, error):
            if error == QProcess.FailedToStart:
                self.test_button.setEnabled(True)
                self.status.setText('Could not start the installed menu: ' + self.process.errorString())

        def test_finished(self, code, exit_status):
            self.read_test_output()
            self.test_button.setEnabled(True)
            if code != 0 or exit_status != QProcess.NormalExit:
                self.status.setText(f'Menu launch failed (exit {code}). Read the local diagnostic output below; '
                                    'run the installed command with --check to check configuration and dependencies.')
            elif self.saw_exposed:
                self.status.setText('Menu closed. Qt reported an exposed window' +
                                    (' with focus.' if self.saw_active else '; focus was not reported.') +
                                    ' If you saw it, test Meta+X separately in your Plasma session.')
            else:
                self.status.setText('Process exited without reporting an exposed menu window. '
                                    'Review the output; reinstall if --diagnose-launch is unrecognized. '
                                    'Process startup alone does not confirm menu visibility or Meta+X.')

        def done(self, result):
            # Only our own test child is stopped when this dialog closes.
            if self.process.state() != QProcess.NotRunning:
                self.process.terminate()
                if not self.process.waitForFinished(250):
                    self.process.kill()
                    self.process.waitForFinished(250)
            super().done(result)

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
