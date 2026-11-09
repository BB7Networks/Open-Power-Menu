"""Differential model and private D-Bus tests; Python is test tooling only."""
import argparse
from contextlib import contextmanager
import json
import os
import shutil
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
        def legacy_view(items):
            return [{k: legacy_view(v) if k == 'items' else v for k, v in item.items()
                     if k not in ('access_key', 'access_hint')} for item in items]
        self.assertEqual(legacy_view(actual), expected)
        self.assertNotIn('command', {key for item in actual for key in item})

    def test_defaults_and_no_python_path(self):
        env = {**self.env, 'PATH': str(self.root / 'empty-path')}
        native_defaults = json.loads(self.run_native('--default-config', env=env).stdout)
        self.assertEqual(json.loads(self.run_native('--dump-config', env=env).stdout), native_defaults)
        self.assertTrue(native_defaults['access_keys_enabled'])
        self.assertEqual(native_defaults['auto_close_delay_ms'], 1200)
        self.assertFalse(native_defaults['auto_close_on_pointer_leave'])
        def legacy_items(items):
            return [{k: legacy_items(v) if k == 'items' else v for k, v in item.items() if k != 'access_key'}
                    for item in items if item.get('action') not in ('sleep', 'hibernate')]
        for key, value in DEFAULT_CONFIG.items():
            self.assertEqual(legacy_items(native_defaults[key]) if key == 'menu' else native_defaults[key], value)
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

    def test_legacy_presentation_and_metadata_corpus(self):
        for value in [None, False, True, 0, -7, 9223372036854775807, -9223372036854775808, "Ω icons"]:
            with self.subTest(value=value):
                config = {'menu': [{'label': value, 'icon': value, 'command': ['true']}],
                          'extension': {'label': [1.25, {'future': True}], 'large': 9223372036854775807}}
                self.compare(config)
                before = self.config.read_bytes()
                dumped = json.loads(self.run_native('--dump-config').stdout)
                self.assertEqual(dumped['extension'], config['extension'])
                self.assertEqual(dumped['menu'][0]['label'], value)
                self.assertEqual(self.config.read_bytes(), before)
        for token in ['1.0', '1e3', '-0.0', '1.2345678901234567']:
            with self.subTest(decimal_presentation=token):
                source = ('{"menu":[{"submenu":"Group","items":[{"command":["true"],"label":' + token + '}]}]}').encode()
                self.config.write_bytes(source)
                self.run_native('--check', ok=False)
                self.assertEqual(self.config.read_bytes(), source)
        # Unsupported presentation structures are refused rather than silently
        # converted to an empty label/icon. Extension metadata stays unrestricted.
        for value in [[], {}, [1, 'label'], {'extension': 'icon'}]:
            for field in ['label', 'icon']:
                with self.subTest(field=field, value=value):
                    self.write({'menu': [{'command': ['true'], field: value}]})
                    before = self.config.read_bytes()
                    self.run_native('--check', ok=False)
                    self.assertEqual(self.config.read_bytes(), before)

    def test_incompatible_sources_preserve_active_and_backup_bytes(self):
        nested = {'command': ['true']}
        for _ in range(10):
            nested = {'submenu': 'Nested', 'items': [nested]}
        sources = [b'{"menu":[],"bad":"\\xff"}'.replace(b'\\xff', b'\xff'),
                   b'{"menu":[],"extension":9223372036854775808}',
                   b'{"menu":[],"extension":-9223372036854775809}',
                   json.dumps({'menu': [nested]}).encode(), b'{broken backup']
        backup = self.config.with_name('menu.json.bak-manual')
        backup.write_bytes(b'personal recovery bytes')
        for source in sources:
            with self.subTest(source=source[:80]):
                self.config.write_bytes(source)
                self.run_native('--dump-config', ok=False)
                self.assertEqual(self.config.read_bytes(), source)
                self.assertEqual(backup.read_bytes(), b'personal recovery bytes')

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
    def service(self, binary=BINARY):
        # Caller runs this suite under dbus-run-session; never use a desktop bus.
        self.assertIn('DBUS_SESSION_BUS_ADDRESS', self.env)
        log = self.root / 'backend.log'
        with log.open('wb') as output:
            child = subprocess.Popen([binary, '--service'], env=self.env, stdout=output, stderr=output)
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

    def test_pending_presentation_cannot_miss_fast_capability_completion(self):
        self.write({'show_unavailable': True, 'menu': [{'action': 'sleep'}]})
        with self.service():
            first = json.loads(self.call('GetMenu'))
            self.assertFalse(first[0]['enabled'])
            time.sleep(1.7)  # allow the private bus's absent services/deadline to settle
            self.assertEqual(self.call('PowerCapabilitiesPending'), 'true')
            refreshed = json.loads(self.call('GetMenu'))
            self.assertFalse(refreshed[0]['enabled'])
            self.assertEqual(self.call('PowerCapabilitiesPending'), 'false')

    def test_dbus_protocol_and_invalid_config_fallback(self):
        self.write({'menu': [{'command': ['true']}], 'hide_original_launcher': True})
        with self.service():
            self.assertEqual(self.call('Ping'), 'Open Power Menu v2.1.0-dev')
            self.assertTrue(json.loads(self.call('GetIntegration'))['hide_original_launcher'])
            self.assertRegex(json.loads(self.call('GetMenu'))[0]['key'], r'^[a-f0-9]{32}/0$')
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

    def test_presentation_selection_identity(self):
        def item(label, name):
            return {'label': label, 'command': ['/usr/bin/touch', str(self.root / name)]}
        def menu():
            return json.loads(self.call('GetMenu'))
        self.write({'menu': [item('Same', 'old')]})
        with self.service():
            key = menu()[0]['key']
            self.write({'menu': [item('Same', 'replacement')]})
            self.assertEqual(self.call('Run', key), 'false')
            self.assertFalse((self.root / 'old').exists())
            self.assertFalse((self.root / 'replacement').exists())
            self.write({'menu': [item('Alpha', 'alpha'), item('Beta', 'beta')]})
            client_a = menu()
            client_b = menu()
            self.assertNotEqual(client_a[0]['key'], client_b[0]['key'])
            self.assertEqual(self.call('Run', client_a[0]['key']), 'true')
            until((self.root / 'alpha').exists)
            self.assertEqual(self.call('Run', client_b[1]['key']), 'true')
            until((self.root / 'beta').exists)
            self.assertEqual(self.call('Run', client_b[1]['key']), 'false')
            for changed in ([item('Beta', 'wrong'), item('Alpha', 'wrong')], [item('Beta', 'wrong')], []):
                self.write({'menu': [item('Alpha', 'alpha'), item('Beta', 'beta')]})
                client_a = menu()
                self.write({'menu': changed})
                menu()  # a different client's refresh must never rebind A's token
                self.assertEqual(self.call('Run', client_a[0]['key']), 'false')
                self.assertFalse((self.root / 'wrong').exists())
            self.write({'menu': [item('Same', 'old')]})
            key = menu()[0]['key']
            # Identical bytes in a replaced inode still invalidate the presentation.
            temp = self.config.with_suffix('.new')
            temp.write_bytes(self.config.read_bytes()); temp.replace(self.config)
            self.assertEqual(self.call('Run', key), 'false')

    def test_presentation_availability_changes(self):
        tool = self.executable('changing-tool', '#!/bin/sh\nexit 0\n')
        self.write({'show_unavailable': True, 'menu': [{'command': ['changing-tool']}]})
        with self.service():
            shown = json.loads(self.call('GetMenu'))
            tool.unlink()
            self.assertEqual(self.call('Run', shown[0]['key']), 'false')
            unavailable = json.loads(self.call('GetMenu'))
            self.assertFalse(unavailable[0]['enabled'])
            self.executable('changing-tool', '#!/bin/sh\nexit 0\n')
            self.assertEqual(self.call('Run', unavailable[0]['key']), 'false')

    def test_changed_command_alternative_is_rejected(self):
        first = self.executable('first-alternative', '#!/bin/sh\nexit 0\n')
        self.executable('second-alternative', '#!/bin/sh\nexit 0\n')
        self.write({'menu': [{'label': 'Alternatives', 'commands': [['first-alternative'], ['second-alternative']]}]})
        with self.service():
            shown = json.loads(self.call('GetMenu'))
            first.unlink()
            self.assertEqual(self.call('Run', shown[0]['key']), 'false')
            fresh = json.loads(self.call('GetMenu'))
            self.assertEqual(self.call('Run', fresh[0]['key']), 'true')

    def test_native_editor_launch_uses_same_configuration(self):
        install = self.root / 'native install; literal'
        install.mkdir()
        backend = install / 'open-power-menu-native'
        shutil.copy2(BINARY, backend)
        shutil.copy2(PROBE, install / 'open-power-menu-editor')
        self.env['XDG_CONFIG_HOME'] = str(self.root / 'configuration; literal')
        config = Path(self.env['XDG_CONFIG_HOME']) / 'open-power-menu/menu.json'
        config.parent.mkdir(parents=True)
        config.write_text('{"menu":[]}')
        with self.service(str(backend)):
            self.assertEqual(self.call('Edit'), 'true')
            until(lambda: Path(str(config) + '.editor-probe').exists())

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
                self.assertEqual(self.call('Run', json.loads(self.call('GetMenu'))[0]['key']), 'true')
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
            if marker.exists():
                until(lambda: Path(str(stop) + '.ack').exists())


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0], *remainder], verbosity=2)
