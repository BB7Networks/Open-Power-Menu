"""Portable model, upgrade and UI integration tests (no GUI dependency)."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import os
import stat
import tempfile
import unittest
from unittest import mock

from openpowermenu.core import (
    COMMANDS, DEFAULT_CONFIG, config_path, load_config, save_config,
    validate_configuration, validate_menu_definition
)

ROOT = Path(__file__).resolve().parents[1]


class EditorModelTests(unittest.TestCase):
    def test_standard_defaults_do_not_include_private_network_locations(self):
        self.assertIn('network_locations', COMMANDS)  # available as opt-in action
        self.assertNotIn('network_locations', json.dumps(DEFAULT_CONFIG['menu']))
        self.assertIn('terminal', json.dumps(DEFAULT_CONFIG['menu']))
        self.assertIn('shutdown', json.dumps(DEFAULT_CONFIG['menu']))

    def test_old_user_menu_is_preserved_without_automatic_migration(self):
        legacy = deepcopy(DEFAULT_CONFIG)
        legacy['menu'].append({'submenu': 'Private', 'items': [{'action': 'network_locations'}]})
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'menu.json'
            p.write_text(json.dumps(legacy))
            loaded = load_config(p)
            self.assertEqual(loaded['menu'], legacy['menu'])
            self.assertTrue(any('network_locations' in str(x) for x in loaded['menu']))

    def test_round_trip_add_remove_move_and_submenus(self):
        cfg = deepcopy(DEFAULT_CONFIG)
        cfg['menu'] = [
            {'action': 'files'},
            {'submenu': 'Work', 'icon': 'network-server', 'items': [
                {'label': 'NAS', 'command': ['dolphin', 'smb://example.local/share']},
                {'separator': True},
                {'action': 'network_locations'}
            ]},
            {'action': 'terminal'}
        ]
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'menu.json'
            save_config(cfg, p)
            restored = load_config(p)
            self.assertEqual(restored['menu'], cfg['menu'])
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
            cfg['menu'].pop(0)
            save_config(cfg, p)
            self.assertEqual(load_config(p)['menu'], cfg['menu'])
            backups = list(p.parent.glob('menu.json.bak-*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(json.loads(backups[0].read_text())['menu'][0]['action'], 'files')

    def test_bad_command_never_overwrites_valid_user_config(self):
        cfg = deepcopy(DEFAULT_CONFIG)
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'menu.json'
            save_config(cfg, p)
            original = p.read_bytes()
            cfg['menu'] = [{'label': 'oops', 'command': 'sh -c unexpected'}]
            with self.assertRaises(ValueError):
                save_config(cfg, p)
            self.assertEqual(p.read_bytes(), original)

    def test_config_must_not_be_symlinked(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'menu.json'
            out = Path(t) / 'other.json'
            out.write_text('SAFE')
            p.symlink_to(out)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                save_config(deepcopy(DEFAULT_CONFIG), p)
            self.assertEqual(out.read_text(), 'SAFE')

    def test_nested_menu_limits(self):
        deep = {'action': 'files'}
        for _ in range(10):
            deep = {'submenu': 'nest', 'items': [deep]}
        with self.assertRaisesRegex(ValueError, 'eight levels'):
            validate_menu_definition([deep])

    def test_unknown_builtin_rejected_for_save(self):
        with self.assertRaisesRegex(ValueError, 'Unknown built-in'):
            validate_menu_definition([{'action': 'unlisted_program'}])


class EditorIntegrationTests(unittest.TestCase):
    def test_configure_refresh_are_icon_only_in_header(self):
        qml = (ROOT/'plasmoid/contents/ui/main.qml').read_text()
        self.assertIn('id: refreshButton', qml)
        self.assertIn('id: configureButton', qml)
        self.assertEqual(qml.count('display: QQC2.AbstractButton.IconOnly'), 2)
        self.assertIn('root.fetchMenu(); root.fetchIntegration();', qml)
        self.assertIn('onClicked: root.openEditor()', qml)
        # Both are before the scrollable menu, not footer buttons.
        self.assertLess(qml.index('id: refreshButton'), qml.index('QQC2.ScrollView {'))
        self.assertLess(qml.index('id: configureButton'), qml.index('QQC2.ScrollView {'))
        self.assertNotIn('text: "Configure"', qml)
        self.assertNotIn('text: "Refresh"', qml)

    def test_backend_editor_is_a_local_command_without_shell(self):
        service = (ROOT/'openpowermenu/service.py').read_text()
        self.assertIn('def Edit(self):', service)
        self.assertIn('"--edit"', service)
        self.assertIn('launch([sys.executable, str(script), "--edit"])', service)
        self.assertNotIn('shell=True', service)
        cli = (ROOT/'openpowermenu/cli.py').read_text()
        self.assertIn('"--edit"', cli)
        self.assertIn('launch_editor()', cli)

    def test_unchanged_working_flyouts_and_left_click(self):
        qml = (ROOT/'plasmoid/contents/ui/main.qml').read_text()
        side = (ROOT/'plasmoid/contents/ui/SideFlyout.qml').read_text()
        self.assertIn('activateLauncherMenu', qml)
        self.assertIn('Plasmoid.configuration.leftAction', qml)
        self.assertIn('flyout.positionAtRow(sourceRow', qml)
        self.assertIn('floating: true', side)
        self.assertIn('function positionAtRow(', side)

    def test_editor_can_add_all_four_types_and_save(self):
        source = (ROOT/'openpowermenu/editor.py').read_text()
        for label in ('Built-in command', 'Custom command', 'Submenu', 'Separator'):
            self.assertIn(label, source)
        for item in ('Move up', 'Move down', 'Remove', 'Restore default layout'):
            self.assertIn(item, source)
        self.assertIn('save_config(self.cfg)', source)
        self.assertIn('shlex.split', source)


if __name__ == '__main__':
    unittest.main()
