"""Differential model and private D-Bus tests; Python is test tooling only."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from openpowermenu.core import COMMANDS, DEFAULT_CONFIG, load_config
from openpowermenu.menu_api import public_menu_from_config

parser = argparse.ArgumentParser()
parser.add_argument('--binary', required=True)
parser.add_argument('--probe', required=True)
args, remainder = parser.parse_known_args()
BINARY = str(Path(args.binary).resolve())
PROBE = str(Path(args.probe).resolve())


def until(check, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(.02)
    raise AssertionError('Timed out waiting for native runtime')


class NativeContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='opm-native-contract-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'config/open-power-menu/menu.json'
        self.config.parent.mkdir(parents=True)
        self.tools = self.root / 'tools'
        self.tools.mkdir()
        self.env = {**os.environ, 'XDG_CONFIG_HOME': str(self.root / 'config'),
                    'XDG_DATA_HOME': str(self.root / 'data'), 'XDG_CACHE_HOME': str(self.root / 'cache'),
                    'XDG_CURRENT_DESKTOP': 'KDE', 'QT_QPA_PLATFORM': 'offscreen',
                    'PATH': str(self.tools) + os.pathsep + os.defpath,
                    'OPM_TEST_VALUE': 'expanded value', 'OPM_TEST_INHERITED': 'desktop-inherited'}
        for spec in COMMANDS.values():
            for command in spec['commands']:
                argv = command['argv'] if isinstance(command, dict) else command
                self.executable(argv[0], '#!/bin/sh\nexit 0\n')
        self.executable('kcmshell6', '#!/bin/sh\nprintf "kcm_printer_manager\\nkcm_powerdevilprofilesconfig\\n"\n')
        self.executable('qdbus6', '#!/bin/sh\nprintf "Show Desktop\\n"\n')

    def executable(self, name, contents):
        path = self.tools / name
        path.write_text(contents)
        path.chmod(0o755)
        return path

    def write(self, config):
        self.config.write_text(json.dumps(config, ensure_ascii=False))

    def run_native(self, *arguments, ok=True, env=None):
        result = subprocess.run([BINARY, *arguments], env=env or self.env,
                                capture_output=True, text=True, timeout=15)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def compare(self, config):
        self.write(config)
        with patch.dict(os.environ, self.env, clear=True):
            expected = public_menu_from_config(load_config(self.config))
        actual = json.loads(self.run_native('--widget-menu-json').stdout)
        self.assertEqual(actual, expected)
        self.assertNotIn('command', {key for item in actual for key in item})

    def test_defaults_and_no_python_path(self):
        env = {**self.env, 'PATH': str(self.root / 'empty-path')}
        self.assertEqual(json.loads(self.run_native('--default-config', env=env).stdout), DEFAULT_CONFIG)
        self.assertEqual(json.loads(self.run_native('--dump-config', env=env).stdout), DEFAULT_CONFIG)
        self.assertFalse(self.config.exists())

    def test_builtin_and_custom_differential(self):
        self.compare(DEFAULT_CONFIG)
        configurations = [
            {'menu': []},
            {'menu': [{'separator': True}, {'command': ['opm-missing']}, {'separator': True}]},
            {'menu': [{'label': '', 'command': ['true']}, {'label': None, 'command': ['true']}]},
            {'menu': [{'submenu': 'Nested Ω', 'icon': None, 'items': [{'action': 'files'}, {'separator': True}]}]},
            {'menu': [{'label': 'Candidates', 'commands': [['missing-program'], {'argv': ['true', 'a;b'], 'requires': ['true']}]}]},
            {'menu': [{'command': ['true'], 'desktops': ['GNOME']}, {'command': ['true'], 'requires': ['opm-no-tool']}]},
            {'show_unavailable': True, 'menu': [{'submenu': 'Missing', 'items': [{'command': ['opm-no-tool']}]}]},
            {'menu': [{'label': 'Picker', 'command': ['true', '$OPM_TEST_VALUE', '~', '{home}'], 'desktop_file': '/tmp/app.desktop'}]},
            {'menu': [{'label': 'Expanded', 'command': ['true', '$OPM_TEST_VALUE', '~', '{home}']}]},
        ]
        for config in configurations:
            with self.subTest(config=config):
                self.compare(config)

    def test_invalid_and_unsafe_reads(self):
        for config in [{'menu': [], 'show_menu_icons': 1}, {'menu': [], 'backup_retention': 1.0},
                       {'menu': [{'command': 'echo unsafe'}]}, {'menu': [{'action': 'unknown'}]}]:
            with self.subTest(config=config):
                self.write(config)
                before = self.config.read_bytes()
                self.run_native('--check', ok=False)
                self.assertEqual(self.config.read_bytes(), before)
        self.config.write_bytes(b'{"menu":[],"bad":"\xff"}')
        self.run_native('--check', ok=False)
        self.config.write_bytes(b' ' * (4 * 1024 * 1024 + 1))
        self.run_native('--check', ok=False)
        self.config.unlink()
        self.config.symlink_to(self.root / 'missing')
        self.run_native('--check', ok=False)
        self.config.unlink()
        os.mkfifo(self.config)
        self.run_native('--check', ok=False)

    def test_exact_capabilities_and_runtime_requirements(self):
        self.executable('qdbus6', '#!/bin/sh\nprintf "Show Desktop extra\\n"\n')
        self.executable('kcmshell6', '#!/bin/sh\nprintf "kcm_printer_manager_extra\\n"\n')
        (self.tools / 'system-config-printer').unlink()
        self.compare({'show_unavailable': True, 'menu': [{'action': 'show_desktop'}, {'action': 'printers'}]})
        menu = json.loads(self.run_native('--widget-menu-json').stdout)
        self.assertTrue(all(not item['enabled'] for item in menu))
        self.write({'menu': [{'command': ['true'], 'requires': None}]})
        self.run_native('--check', ok=False)

    @contextmanager
    def service(self):
        # Caller runs this suite under dbus-run-session; never use a desktop bus.
        self.assertIn('DBUS_SESSION_BUS_ADDRESS', self.env)
        log = self.root / 'backend.log'
        with log.open('wb') as output:
            child = subprocess.Popen([BINARY, '--service'], env=self.env, stdout=output, stderr=output)
            try:
                def ready():
                    if child.poll() is not None:
                        self.fail(log.read_text())
                    result = subprocess.run([BINARY, '--call', 'Ping'], env=self.env, capture_output=True, text=True, timeout=2)
                    return result.returncode == 0
                until(ready)
                yield child
            finally:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=5)

    def call(self, method, *parameters):
        return self.run_native('--call', method, '--', *parameters).stdout.strip()

    def test_dbus_protocol_and_invalid_config_fallback(self):
        self.write({'menu': [{'command': ['true']}], 'hide_original_launcher': True})
        with self.service():
            self.assertEqual(self.call('Ping'), 'Open Power Menu v2.0.0-dev')
            self.assertTrue(json.loads(self.call('GetIntegration'))['hide_original_launcher'])
            self.assertEqual(json.loads(self.call('GetMenu'))[0]['key'], '0')
            # No editor stub masquerades as successful functionality.
            self.assertEqual(self.call('Edit'), 'false')
            conflict = self.run_native('--service', ok=False)
            self.assertIn('existing owner', conflict.stderr)
            self.config.write_text('{broken')
            self.assertFalse(json.loads(self.call('GetMenu'))[0]['enabled'])
            self.assertFalse(json.loads(self.call('GetIntegration'))['hide_original_launcher'])
            self.assertEqual(self.call('Run', '0'), 'false')
            self.assertEqual(self.config.read_text(), '{broken')

    def test_dispatch_rereads_current_configuration(self):
        marker = self.root / 'must-not-launch'
        self.write({'menu': [{'command': [PROBE, str(marker), str(self.root / 'stop'), str(self.root / 'heartbeat')]}]})
        with self.service():
            self.assertTrue(json.loads(self.call('GetMenu'))[0]['enabled'])
            self.write({'menu': [{'command': ['missing-application']}]})
            self.assertEqual(self.call('Run', '0'), 'false')
            self.assertFalse(marker.exists())

    def test_dbus_layout_transaction_and_conflict(self):
        original = {'menu': [{'command': ['true'], 'unknown': {'access_key': 'z'}},
                             {'submenu': 'Hidden', 'items': [{'command': ['missing-app']}]}],
                    'future-setting': [1, 2, {'value': 'preserved'}]}
        self.write(original)
        def refs(items):
            return [dict(id=item['id'], **({'items': refs(item['items'])} if item['kind'] == 'submenu' else {})) for item in items]
        with self.service():
            begun = json.loads(self.call('BeginLayoutEdit'))
            self.assertTrue(begun['ok'])
            nodes = refs(begun['entries'])
            self.assertFalse(json.loads(self.call('SaveLayoutEdit', begun['token'], '[]'))['ok'])
            self.assertTrue(json.loads(self.call('KeepLayoutEdit', begun['token']))['ok'])
            reply = json.loads(self.call('SaveLayoutEdit', begun['token'], json.dumps(nodes[::-1])))
            self.assertEqual(reply, {'ok': True, 'changed': True})
            current = json.loads(self.config.read_text())
            self.assertEqual(current['menu'], original['menu'][::-1])
            self.assertEqual(current['future-setting'], original['future-setting'])
            self.assertEqual(len(list(self.config.parent.glob('menu.json.bak-*'))), 1)
            next_edit = json.loads(self.call('BeginLayoutEdit'))
            self.config.write_text(json.dumps(original))
            reply = json.loads(self.call('SaveLayoutEdit', next_edit['token'], json.dumps(refs(next_edit['entries']))))
            self.assertEqual(reply['code'], 'conflict')
            self.assertEqual(self.call('CancelLayoutEdit', next_edit['token']), 'true')
            self.assertEqual(self.call('CancelLayoutEdit', next_edit['token']), 'false')

    def test_detached_argv_and_service_exit(self):
        marker, stop, heartbeat = [self.root / name for name in ('child.json', 'stop', 'heartbeat')]
        injected = self.root / 'must-not-exist'
        literals = ['a;b', '$(touch ' + str(injected) + ')', '$OPM_TEST_VALUE', '~', 'space and Ω']
        self.write({'menu': [{'command': [PROBE, str(marker), str(stop), str(heartbeat), *literals], 'desktop_file': '/tmp/literal.desktop'}]})
        try:
            with self.service() as backend:
                for key in ('0;touch', '-1', '0.0', '99999'):
                    self.assertEqual(self.call('Run', key), 'false')
                self.assertEqual(self.call('Run', '0'), 'true')
                until(marker.exists)
                data = json.loads(marker.read_text())
                self.assertEqual(data['args'], literals)
                self.assertEqual(data['inherited'], 'desktop-inherited')
                # Qt double-forks: the session leader can be the intermediate
                # child. Isolation and survival matter, not PID == SID.
                self.assertNotEqual(data['sid'], os.getsid(backend.pid))
                self.assertNotEqual(data['pgid'], os.getpgid(backend.pid))
                self.assertEqual(data['sid'], data['pgid'])
                self.assertEqual(data['fds'], ['/dev/null'] * 3)
                until(heartbeat.exists)
                backend.kill(); backend.wait(timeout=5)
                before = int(heartbeat.read_text() or '0')
                until(lambda: int(heartbeat.read_text() or '0') > before + 2)
                self.assertFalse(injected.exists())
        finally:
            stop.touch()


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0], *remainder], verbosity=2)
