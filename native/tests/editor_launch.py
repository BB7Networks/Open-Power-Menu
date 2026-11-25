"""Isolated session changes, stale D-Bus activation and editor startup failures.

No login, workstation bus, real settings, or installed Plasma files are touched.
Run --real-gui under an isolated X11/Wayland display for actual Qt first frames.
Python and the probe executable are test tooling only, never runtime dependencies.
"""
import argparse
import json
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
parser.add_argument('--real-gui', action='store_true')
args, remaining = parser.parse_known_args()
BUILD = args.build.resolve()
LIVE = dict(os.environ)


def until(check, timeout=6):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = check()
        if result:
            return result
        time.sleep(.02)
    raise AssertionError('Timed out waiting for isolated test process')


class EditorLaunch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='opm session test ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.children = []
        self.gui_pids = set()
        self.addCleanup(self.stop_all)
        self.env = {**LIVE, 'DISPLAY': ':59999', 'XAUTHORITY': '/missing/previous-login',
                    'WAYLAND_DISPLAY': 'previous-wayland', 'XDG_SESSION_TYPE': 'wayland',
                    'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
                    'QT_QUICK_CONTROLS_STYLE': 'Basic', 'OPM_TEST_PRIVATE_VALUE': 'keep-config-environment',
                    'XDG_ACTIVATION_TOKEN': 'expired-token', 'DESKTOP_STARTUP_ID': 'expired-id'}
        self.env.pop('OPM_SESSION_TRACE', None)
        for key, path in [('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'),
                          ('XDG_CACHE_HOME', 'cache'), ('XDG_RUNTIME_DIR', 'runtime')]:
            directory = self.root / path
            directory.mkdir(mode=0o700)
            self.env[key] = str(directory)
        self.bin = self.root / 'data/open-power-menu/bin'
        self.bin.mkdir(parents=True)
        for name in ['open-power-menu-native', 'native-editor-launch-probe']:
            shutil.copy2(BUILD / name, self.bin / name)
        shutil.copy2(self.bin / 'native-editor-launch-probe', self.bin / 'open-power-menu-editor')
        self.config = self.root / 'config/open-power-menu/menu.json'
        self.config.parent.mkdir()
        self.original = b'{"menu":[],"unknown":{"preserve":42}}\n'
        self.config.write_bytes(self.original)
        self.config.with_suffix('.json.bak-personal').write_bytes(b'personal recovery')
        service = self.root / 'data/dbus-1/services/org.openpowermenu.Service.service'
        service.parent.mkdir(parents=True)
        # Deliberately activate from a stale bus, not from the current shell.
        service.write_text('[D-BUS Service]\nName=org.openpowermenu.Service\nExec="' +
                           str(self.bin / 'open-power-menu-native') + '" --service --bus-name org.openpowermenu.Service\n')
        self.bus = self.start(['dbus-daemon', '--session', '--nofork', '--print-address=1'], stdout=subprocess.PIPE)
        self.assertTrue(select.select([self.bus.stdout], [], [], 5)[0])
        self.env['DBUS_SESSION_BUS_ADDRESS'] = self.bus.stdout.readline().decode().strip()
        self.owner = None

    def start(self, command, env=None, stdout=None):
        if Path(command[0]).name == 'open-power-menu-native':
            command = [*command, '--bus-name', 'org.openpowermenu.Service']
        log = (self.root / ('process-%d.log' % len(self.children))).open('wb')
        self.addCleanup(log.close)
        child = subprocess.Popen(list(map(str, command)), env=env or self.env,
                                 stdout=stdout or log, stderr=log)
        self.children.append(child)
        return child

    def stop_all(self):
        # Terminate only processes created in this disposable test profile.
        for result in self.root.glob('config/open-power-menu/*.environment.json'):
            value = json.loads(result.read_text())
            self.gui_pids.update([value['pid'], value['parent']])
        for pid in self.gui_pids:
            try:
                # Avoid a recycled PID: require an executable in our test tree.
                exe = Path('/proc/%d/exe' % pid).resolve()
                if self.bin in exe.parents:
                    os.kill(pid, signal.SIGTERM)
            except (FileNotFoundError, ProcessLookupError):
                pass
        backend = self.pid('org.openpowermenu.Service') if self.bus.poll() is None else None
        if backend:
            try:
                os.kill(backend, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for child in reversed(self.children):
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=5)
            if child.stdout:
                child.stdout.close()
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertEqual(self.config.with_suffix('.json.bak-personal').read_bytes(), b'personal recovery')

    def pid(self, service):
        p = subprocess.run(['busctl', '--user', 'call', 'org.freedesktop.DBus', '/org/freedesktop/DBus',
                            'org.freedesktop.DBus', 'GetConnectionUnixProcessID', 's', service],
                           env=self.env, capture_output=True, text=True, timeout=5)
        return int(p.stdout.split()[1]) if p.returncode == 0 else None

    def session(self, kind='x11', number=1, real=False):
        if self.owner:
            self.owner.terminate()
            self.owner.wait(timeout=5)
            until(lambda: self.pid('org.kde.plasmashell') is None)
        current = {**self.env, 'XDG_SESSION_TYPE': kind, 'XDG_SESSION_ID': str(number),
                   'OPM_TEST_SHELL_SECRET': 'do-not-copy'}
        for key in ['DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY', 'QT_QPA_PLATFORM']:
            current.pop(key, None)
        if real:
            for key in ['DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR']:
                if key in LIVE:
                    current[key] = LIVE[key]
        elif kind == 'x11':
            current.update(DISPLAY=':%d' % number, XAUTHORITY='/session-%d/authority' % number)
        else:
            current['WAYLAND_DISPLAY'] = 'wayland-%d' % number
        self.owner = self.start([self.bin / 'native-editor-launch-probe', '--session-owner'],
                                env=current, stdout=subprocess.PIPE)
        self.assertTrue(select.select([self.owner.stdout], [], [], 5)[0])
        self.assertEqual(self.owner.stdout.readline().strip(), b'SESSION_READY')
        return current

    def call(self, method='Edit', ok=True):
        p = subprocess.run([self.bin / 'open-power-menu-native', '--bus-name', 'org.openpowermenu.Service', '--call', method], env=self.env,
                           capture_output=True, text=True, timeout=27)
        self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
        return p

    def result(self):
        path = Path(str(self.config) + '.environment.json')
        until(path.exists)
        value = json.loads(path.read_text())
        self.gui_pids.update([value['pid'], value['parent']])
        return value

    def release(self):
        Path(str(self.config) + '.release').touch()
        for pid in self.gui_pids.copy():
            def exited():
                try:
                    return not Path('/proc/%d/exe' % pid).exists()
                except ProcessLookupError:
                    # Linux may return ESRCH if the process exits during the procfs
                    # lookup. Python 3.12 Path.exists() does not swallow this errno.
                    return True
            until(exited)
        Path(str(self.config) + '.release').unlink()
        Path(str(self.config) + '.environment.json').unlink()

    def assert_session(self, expected, direct_current=False):
        received = self.result()
        for key in ['DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY', 'XDG_SESSION_TYPE', 'XDG_SESSION_ID', 'XDG_RUNTIME_DIR']:
            self.assertEqual(received.get(key), expected.get(key), key)
        self.assertEqual(received['QT_QPA_PLATFORM'], 'xcb' if expected['XDG_SESSION_TYPE'] == 'x11' else 'wayland')
        self.assertEqual(received['OPM_TEST_PRIVATE_VALUE'], 'keep-config-environment')
        self.assertNotIn('OPM_TEST_SHELL_SECRET', received)
        for key in ['XDG_ACTIVATION_TOKEN', 'DESKTOP_STARTUP_ID']:
            if direct_current:
                self.assertEqual(received.get(key), expected.get(key))
            else:
                self.assertNotIn(key, received)
        self.assertEqual(received['config'], str(self.config))

    def test_repeated_sessions_with_surviving_backend(self):
        self.call('Ping')
        backend = self.pid('org.openpowermenu.Service')
        for number, kind in enumerate(['x11', 'x11', 'wayland', 'x11', 'wayland', 'x11'], 1):
            with self.subTest(login=number, session=kind):
                current = self.session(kind, number)
                self.assertEqual(self.call().stdout.strip(), 'true')
                self.assert_session(current)
                self.assertEqual(self.pid('org.openpowermenu.Service'), backend)
                self.release()

    def test_fresh_activation_from_stale_bus_environment(self):
        for number, kind in enumerate(['x11', 'wayland', 'x11'], 1):
            with self.subTest(session=kind):
                current = self.session(kind, number)
                self.assertIsNone(self.pid('org.openpowermenu.Service'))
                self.assertEqual(self.call().stdout.strip(), 'true')
                self.assert_session(current)
                self.release()
                os.kill(self.pid('org.openpowermenu.Service'), signal.SIGTERM)
                until(lambda: self.pid('org.openpowermenu.Service') is None)

    def test_direct_edit_uses_current_session(self):
        if not (BUILD / 'open-power-menu').exists():
            self.skipTest('Package dispatcher not built')
        for number, kind in enumerate(['x11', 'wayland', 'x11'], 1):
            current = self.session(kind, number)
            direct = self.start([BUILD / 'open-power-menu', '--edit', '--config', self.config])
            self.assert_session(current)
            self.release()
            self.assertEqual(direct.wait(timeout=5), 0)

    def test_direct_invocation_without_plasma(self):
        env = {**self.env, 'DISPLAY': ':17', 'XDG_SESSION_TYPE': 'x11'}
        env['XDG_ACTIVATION_TOKEN'] = 'fresh-direct-token'
        env['DESKTOP_STARTUP_ID'] = 'fresh-direct-id'
        env.pop('WAYLAND_DISPLAY')
        p = self.start([self.bin / 'open-power-menu-editor', '--config', self.config], env=env)
        self.assert_session(env, direct_current=True)
        self.release()
        self.assertEqual(p.wait(timeout=5), 0)

    def test_requester_environment_without_plasma(self):
        # The bus remains stale; only this client has the current environment.
        self.env.update(DISPLAY=':18', XDG_SESSION_TYPE='x11')
        self.env.pop('WAYLAND_DISPLAY')
        self.assertEqual(self.call().stdout.strip(), 'true')
        self.assert_session(self.env)
        self.release()

    def test_invalid_current_session_fails_instead_of_using_stale_backend(self):
        self.session('tty')
        self.assertIn('No usable graphical session', self.call(ok=False).stderr)
        self.assertFalse(Path(str(self.config) + '.environment.json').exists())

    def test_child_failure_is_not_launch_success(self):
        self.session()
        for mode in ['exit', 'crash', 'clean-exit']:
            with self.subTest(mode=mode):
                backend_env = {**self.env, 'OPM_EDITOR_TEST_MODE': mode}
                backend = self.start([self.bin / 'open-power-menu-native', '--service'], env=backend_env)
                until(lambda: self.pid('org.openpowermenu.Service') == backend.pid)
                p = self.call(ok=False)
                self.assertIn('before displaying its first frame', p.stderr)
                self.assertNotIn('true', p.stdout)
                self.result()
                self.release()
                backend.terminate(); backend.wait(timeout=5)
                until(lambda: self.pid('org.openpowermenu.Service') is None)

    def test_readiness_deadline_reports_failure(self):
        self.session()
        backend = self.start([self.bin / 'open-power-menu-native', '--service'],
                             env={**self.env, 'OPM_EDITOR_TEST_MODE': 'timeout'})
        until(lambda: self.pid('org.openpowermenu.Service') == backend.pid)
        self.assertIn('within 15 seconds', self.call(ok=False).stderr)
        self.result()
        self.release()

    def test_reply_waits_for_ready_and_rejects_wrong_process(self):
        self.session()
        backend = self.start([self.bin / 'open-power-menu-native', '--service'],
                             env={**self.env, 'OPM_EDITOR_TEST_MODE': 'hold'})
        until(lambda: self.pid('org.openpowermenu.Service') == backend.pid)
        call = self.start([self.bin / 'open-power-menu-native', '--call', 'Edit'], stdout=subprocess.PIPE)
        result = self.result()
        self.assertIsNone(call.poll())
        argv = Path('/proc/%d/cmdline' % result['parent']).read_bytes().decode().split('\0')
        token = argv[argv.index('--opm-request') + 1]
        subprocess.run(['busctl', '--user', 'call', 'org.openpowermenu.Service', '/OpenPowerMenu',
                        'org.openpowermenu.Service', 'EditorStarted', 'ss', token, ''],
                       env=self.env, check=True, capture_output=True)
        self.assertIsNone(call.poll(), 'Another process spoofed GUI readiness')
        Path(str(self.config) + '.ready').touch()
        self.assertEqual(call.communicate(timeout=5)[0].strip(), b'true')
        self.assertEqual(call.returncode, 0)

    def test_editor_survives_backend_exit(self):
        self.session()
        self.call()
        gui = self.result()
        os.kill(self.pid('org.openpowermenu.Service'), signal.SIGTERM)
        until(lambda: self.pid('org.openpowermenu.Service') is None)
        self.assertTrue(Path('/proc/%d/exe' % gui['pid']).exists())
        self.release()

    def test_missing_editor_gives_actionable_error(self):
        (self.bin / 'open-power-menu-editor').unlink()
        self.assertIn('Install the complete native build', self.call(ok=False).stderr)

    def test_diagnostics_are_opt_in_and_do_not_dump_environment(self):
        self.session()
        self.call()
        self.result()
        self.release()
        logs = lambda: '\n'.join(p.read_text() for p in self.root.glob('process-*.log'))
        self.assertNotIn('OPM Configure session:', logs())
        direct = self.start([self.bin / 'open-power-menu-editor', '--config', self.config],
                            env={**self.env, 'OPM_SESSION_TRACE': '1', 'QT_LOGGING_RULES': '*.info=false'})
        self.result()
        self.release()
        self.assertEqual(direct.wait(timeout=5), 0)
        self.assertIn('OPM Configure session: plasmashell', logs())
        self.assertIn('first frame ready', logs())
        self.assertRegex(logs(), r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z')
        for secret in ['do-not-copy', 'keep-config-environment', 'expired-token', 'expired-id']:
            self.assertNotIn(secret, logs())

    def test_real_qt_display_failure_is_reported(self):
        if not (BUILD / 'open-power-menu-editor').exists():
            self.skipTest('Qt Quick editor not built')
        shutil.copy2(BUILD / 'open-power-menu-editor', self.bin / 'open-power-menu-editor')
        self.session('x11', 59998)
        p = self.call(ok=False)
        self.assertIn('before displaying its first frame', p.stderr)
        self.assertNotIn('true', p.stdout)
        direct = subprocess.run([self.bin / 'open-power-menu-editor', '--config', self.config],
                                env={**self.env, 'QT_LOGGING_RULES': '*.critical=false'}, capture_output=True, text=True, timeout=20)
        self.assertNotEqual(direct.returncode, 0)
        self.assertIn('before displaying its first frame', direct.stderr)

    @unittest.skipUnless(args.real_gui, 'Use --real-gui inside an isolated graphical session')
    def test_real_editor_first_frame_via_dbus_and_dispatcher(self):
        shutil.copy2(BUILD / 'open-power-menu-editor', self.bin / 'open-power-menu-editor')
        self.env['OPM_SESSION_TRACE'] = '1'
        kind = 'wayland' if LIVE.get('WAYLAND_DISPLAY') else 'x11'
        self.session(kind, real=True)
        backend = self.start([self.bin / 'open-power-menu-native', '--service'])
        until(lambda: self.pid('org.openpowermenu.Service') == backend.pid)
        self.assertEqual(self.call().stdout.strip(), 'true')
        # Identify only this test's executable, never unrelated user editors.
        for pid in Path('/proc').iterdir():
            if pid.name.isdigit():
                try:
                    if (pid / 'exe').resolve() == self.bin / 'open-power-menu-editor':
                        self.gui_pids.add(int(pid.name))
                except (FileNotFoundError, PermissionError):
                    pass
        os.kill(backend.pid, signal.SIGTERM)
        backend.wait(timeout=5)
        for pid in self.gui_pids:
            self.assertTrue(Path('/proc/%d/exe' % pid).exists(), 'Editor died with backend')
            os.kill(pid, signal.SIGTERM)
        direct = self.start([BUILD / 'open-power-menu', '--edit', '--config', self.config, '--smoke-test'])
        self.assertEqual(direct.wait(timeout=20), 0)


if __name__ == '__main__':
    unittest.main(argv=['editor_launch.py', *remaining], verbosity=2)
