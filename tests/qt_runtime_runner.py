"""Isolated runner so each Qt test owns its app, session bus and temporary files."""
from copy import deepcopy
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QMenu, QSpinBox, QTabWidget, QTreeWidget
from openpowermenu.core import DEFAULT_CONFIG, load_config, save_config


def until(condition, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(.02)
    raise AssertionError('Timed out waiting for runtime condition')


def main(mode):
    # Adopt and reap this runner's orphaned workloads after killing their backend.
    assert ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) == 0  # Linux PR_SET_CHILD_SUBREAPER
    app = QApplication([])
    with tempfile.TemporaryDirectory(prefix='opm-runtime-') as temporary:
        temp = Path(temporary)
        os.environ.update(XDG_CONFIG_HOME=str(temp / 'config'), XDG_DATA_HOME=str(temp / 'data'),
                          XDG_DATA_DIRS=str(temp / 'system-data'), OPM_RUNTIME_MARKER='desktop-inherited')
        info = temp / 'child.json'
        heartbeat = temp / 'heartbeat'
        stop = temp / 'stop'
        worker = temp / 'worker.py'
        worker.write_text('''import json, os, pathlib, sys, time
base = pathlib.Path(sys.argv[1])
(base/'child.json').write_text(json.dumps({'pid':os.getpid(), 'ppid':os.getppid(),
 'sid':os.getsid(0), 'pgid':os.getpgrp(), 'marker':os.environ.get('OPM_RUNTIME_MARKER'),
 'cgroup':pathlib.Path('/proc/self/cgroup').read_text(),
 'fds':[os.readlink('/proc/self/fd/'+f) for f in os.listdir('/proc/self/fd') if os.path.exists('/proc/self/fd/'+f)]}))
if len(sys.argv) > 2 and sys.argv[2] == 'short': sys.exit(0)
for counter in range(500):
 if (base/'stop').exists(): break
 sum(range(100000))
 (base/'heartbeat').write_text(str(counter))
 time.sleep(.03)
''')
        config = deepcopy(DEFAULT_CONFIG)
        config['menu'] = [{'label': 'Safe workload', 'command': [sys.executable, str(worker), str(temp)]}]
        if mode == 'backend-reap':
            config['menu'][0]['command'].append('short')
        save_config(config)
        backend = None
        replacement = None
        original_backend_pid = None
        child_pid = None
        try:
            if mode.startswith('backend-'):
                code = 'from openpowermenu.service import run_service; raise SystemExit(run_service())'
                if mode == 'backend-idle':
                    code = '''from PySide6 import QtCore
original = QtCore.QTimer
class FastIdleTimer(original):
 def setInterval(self, value): super().setInterval(300 if value == 300000 else value)
QtCore.QTimer = FastIdleTimer
from openpowermenu.service import run_service
raise SystemExit(run_service())'''
                if mode == 'backend-upgrade':
                    # Exercise the actual installed-path/UID ownership guard.
                    installed = temp / 'data/open-power-menu'
                    installed.mkdir(parents=True)
                    (installed / 'run.py').write_text('import sys\nsys.path.insert(0, ' + repr(str(ROOT)) + ')\nfrom openpowermenu.cli import main\nraise SystemExit(main())\n')
                    command = [sys.executable, str(installed / 'run.py'), '--service']
                else:
                    command = [sys.executable, '-c', code]
                backend = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                original_backend_pid = backend.pid
                bus = QDBusConnection.sessionBus()
                until(lambda: bus.interface().isServiceRegistered('org.openpowermenu.Service').value())
                interface = QDBusInterface('org.openpowermenu.Service', '/OpenPowerMenu', 'org.openpowermenu.Service', bus)
                def call(method, *args):
                    reply = interface.call(method, *args)
                    assert reply.type() != QDBusMessage.ErrorMessage, reply.errorMessage()
                    return reply.arguments()[0]
                assert call('Ping') == 'Open Power Menu v0.4.17'
                assert json.loads(call('GetMenu'))[0]['title'] == 'Safe workload'
                assert call('Run', '0') is True
                until(info.exists)
                child_pid = json.loads(info.read_text())['pid']
                if mode == 'backend-accounting':
                    def usage(pid):
                        fields = Path(f'/proc/{pid}/stat').read_text().split()
                        return (int(fields[13]) + int(fields[14])) / os.sysconf('SC_CLK_TCK'), int(fields[23]) * os.sysconf('SC_PAGE_SIZE')
                    parent_start, _ = usage(backend.pid)
                    child_start, _ = usage(child_pid)
                    time.sleep(1)
                    parent_end, parent_rss = usage(backend.pid)
                    child_end, child_rss = usage(child_pid)
                    print(json.dumps({'backend_cpu_seconds': parent_end-parent_start,
                                      'child_cpu_seconds': child_end-child_start,
                                      'backend_rss_bytes': parent_rss, 'child_rss_bytes': child_rss}))
                if mode == 'backend-reap':
                    until(lambda: not Path(f'/proc/{child_pid}').exists())
                    assert backend.poll() is None
                    assert call('Run', 'invalid;command') is False
                    missing = deepcopy(config)
                    missing['menu'][0]['command'] = ['/definitely/missing-opm-tool']
                    save_config(missing)
                    assert call('Run', '0') is False
                    invalid_executable = temp / 'invalid-executable'
                    invalid_executable.write_text('not an executable format')
                    invalid_executable.chmod(0o755)
                    missing['menu'][0]['command'] = [str(invalid_executable)]
                    save_config(missing)
                    assert call('Run', '0') is False  # actual exec failure
                    configuration_file = temp / 'config/open-power-menu/menu.json'
                    configuration_file.write_text('{broken')
                    broken_menu = json.loads(call('GetMenu'))
                    assert broken_menu[0]['enabled'] is False
                    assert 'Invalid menu.json' in broken_menu[0]['title']
                    assert call('Run', '0') is False
                    assert configuration_file.read_text() == '{broken'
                elif mode == 'backend-upgrade':
                    from openpowermenu.service import stop_owned_service
                    assert stop_owned_service() == 0
                    backend.wait(timeout=5)
                    replacement = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    until(lambda: bus.interface().isServiceRegistered('org.openpowermenu.Service').value())
                    assert replacement.poll() is None
                    interface = QDBusInterface('org.openpowermenu.Service', '/OpenPowerMenu', 'org.openpowermenu.Service', bus)
                    assert call('Ping') == 'Open Power Menu v0.4.17'
                elif mode == 'backend-idle':
                    backend.wait(timeout=5)
                    assert backend.returncode == 0
                elif mode == 'backend-kill':
                    backend.kill()
                else:
                    backend.terminate()
                if mode != 'backend-reap':
                    # A child inheriting the backend's PIPE handles would hold
                    # communicate() open until it exited. Detached I/O avoids it.
                    backend.communicate(timeout=2)
            elif mode == 'standalone':
                from PySide6.QtCore import Qt
                from PySide6.QtTest import QTest
                from openpowermenu.gui import launch_menu
                def choose_action():
                    menu = app.activePopupWidget()
                    assert isinstance(menu, QMenu)
                    QTest.mouseClick(menu, Qt.LeftButton, pos=menu.actionGeometry(menu.actions()[0]).center())
                QTimer.singleShot(100, choose_action)
                assert launch_menu(config) == 0
                until(info.exists)
                child_pid = json.loads(info.read_text())['pid']
            elif mode == 'editor':
                editor_flow(app, temp, config)
                return
            details = json.loads(info.read_text())
            assert details['pid'] == details['sid'] == details['pgid']
            assert details['marker'] == 'desktop-inherited'
            assert details['fds'].count('/dev/null') >= 3
            if mode != 'backend-reap':
                until(heartbeat.exists)
                before = int(heartbeat.read_text() or '0')
                until(lambda: int(heartbeat.read_text() or '0') > before + 2)
                assert Path(f'/proc/{child_pid}').exists()
            if mode.startswith('backend-') and mode != 'backend-idle':
                assert details['ppid'] == original_backend_pid
            # setsid doesn't move a process into a new cgroup.
            assert details['cgroup'] == Path('/proc/self/cgroup').read_text()
        finally:
            if replacement is not None:
                replacement.terminate()
                replacement.communicate(timeout=5)
            if backend is not None:
                if backend.poll() is None:
                    backend.terminate()
                backend.communicate(timeout=5)
            stop.touch()
            if child_pid:
                try:
                    os.waitpid(child_pid, 0)
                except ChildProcessError:
                    pass  # already reaped by the live backend


def editor_flow(app, temp, config):
    from openpowermenu.editor import launch_editor
    from openpowermenu.desktop_apps import installed_applications
    directory = temp / 'data/applications'
    directory.mkdir(parents=True)
    desktop = directory / 'opm-example.desktop'
    script = temp / 'picked-app.py'
    launched = temp / 'picked-app.json'
    script.write_text('import json,pathlib,sys\npathlib.Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:]))\n')
    desktop.write_text('[Desktop Entry]\nType=Application\nName=OPM Example & Tools\nIcon=example-icon\n'
                       f'Exec={sys.executable} {script} {launched} %c %i %%\n')
    selected = installed_applications()
    assert len(selected) == 1
    errors = []
    def exercise():
        try:
            dialog = next(w for w in app.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible())
            tabs = dialog.findChild(QTabWidget)
            assert [tabs.tabText(i) for i in range(tabs.count())] == ['General', 'Layout']
            spin = dialog.findChild(QSpinBox, 'backupRetentionSpin')
            assert (spin.minimum(), spin.maximum(), spin.value()) == (0, 1000, 10)
            spin.setValue(2)
            # Exercise real installed-app discovery, picker search, entry editing
            # and MenuEditor.add_application with nested modal event loops.
            def choose():
                picker = app.activeModalWidget()
                picker.search.setText('example &')
                assert picker.app_list.count() == 1
                picker.accept()
                QTimer.singleShot(0, save_entry)
            def save_entry():
                entry = app.activeModalWidget()
                assert entry.name.text() == 'OPM Example & Tools'
                assert entry.icon.text() == 'example-icon'
                assert entry.argv.text()
                entry.accept()
            QTimer.singleShot(0, choose)
            dialog.add_application()
            tree = dialog.findChild(QTreeWidget)
            assert tree.topLevelItemCount() == 2
            dialog.accept()
        except BaseException as exc:
            errors.append(repr(exc))
            for widget in app.topLevelWidgets():
                if isinstance(widget, QDialog):
                    widget.reject()
            app.quit()
    QTimer.singleShot(0, exercise)
    assert launch_editor() == 0
    assert not errors, errors
    saved = load_config()
    assert saved['backup_retention'] == 2
    assert saved['menu'][1]['desktop_file'] == str(desktop)
    assert saved['menu'][1]['label'] == 'OPM Example & Tools'
    assert list((temp / 'config/open-power-menu').glob('menu.json.bak-*'))
    from openpowermenu.core import get_item_info
    from openpowermenu.launching import launch_detached, reap_children
    _, _, selected_command = get_item_info(saved['menu'][1])
    launch_detached(selected_command.argv)
    until(launched.exists)
    arguments = json.loads(launched.read_text())
    assert arguments[:3] == ['OPM Example & Tools', '--icon', 'example-icon'], arguments
    assert arguments[3:] == ['%'], arguments
    until(lambda: not reap_children())
    # Cancel must not save even an in-memory preference change.
    original = (temp / 'config/open-power-menu/menu.json').read_bytes()
    def cancel():
        dialog = app.activeModalWidget()
        dialog.backup_retention.setValue(0)
        dialog.reject()
    QTimer.singleShot(0, cancel)
    assert launch_editor() == 0
    assert (temp / 'config/open-power-menu/menu.json').read_bytes() == original


if __name__ == '__main__':
    main(sys.argv[1])
    print('PASS', sys.argv[1])
