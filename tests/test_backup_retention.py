"""Backup retention is bounded, reversible and non-destructive."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openpowermenu.core import DEFAULT_CONFIG, load_config, save_config

ROOT = Path(__file__).resolve().parents[1]


class BackupRetentionTests(unittest.TestCase):
    def test_default_and_backward_compatible_old_config(self):
        self.assertEqual(DEFAULT_CONFIG['backup_retention'], 10)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'menu.json'
            target.write_text('{"menu": []}')
            self.assertEqual(load_config(target)['backup_retention'], 10)
            self.assertEqual(load_config(Path(tmp) / 'missing.json')['backup_retention'], 10)

    def test_limit_ten_and_previous_content_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'menu.json'
            for i in range(19):
                cfg = deepcopy(DEFAULT_CONFIG)
                cfg['sequence'] = i
                save_config(cfg, target)
            backups = sorted(target.parent.glob('menu.json.bak-*'))
            self.assertEqual(len(backups), 10)
            self.assertEqual(json.loads(backups[-1].read_text())['sequence'], 17)
            self.assertEqual(json.loads(target.read_text())['sequence'], 18)
            self.assertEqual(json.loads(backups[0].read_text())['sequence'], 8)

    def test_custom_limit_and_manual_backups_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'menu.json'
            manual = Path(tmp) / 'menu.json.bak-my-important-copy'
            manual.write_text('manual')
            for i in range(8):
                cfg = deepcopy(DEFAULT_CONFIG)
                cfg['backup_retention'] = 2
                cfg['sequence'] = i
                save_config(cfg, target)
            automatic = list(Path(tmp).glob('menu.json.bak-????????T????????????Z'))
            self.assertEqual(len(automatic), 2)
            self.assertEqual(manual.read_text(), 'manual')

    def test_zero_disables_new_backups_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'menu.json'
            cfg = deepcopy(DEFAULT_CONFIG)
            save_config(cfg, target)
            save_config(cfg, target)
            prior = {p.name: p.read_bytes() for p in Path(tmp).glob('menu.json.bak-*')}
            cfg['backup_retention'] = 0
            for _ in range(3):
                save_config(cfg, target)
            self.assertEqual({p.name: p.read_bytes() for p in Path(tmp).glob('menu.json.bak-*')}, prior)

    def test_invalid_limits_fail_without_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'menu.json'
            cfg = deepcopy(DEFAULT_CONFIG)
            save_config(cfg, target)
            before = target.read_bytes()
            for invalid in (True, False, -1, 1001, '10', 2.5, None):
                cfg['backup_retention'] = invalid
                with self.subTest(value=invalid), self.assertRaisesRegex(ValueError, 'backup_retention'):
                    save_config(cfg, target)
                    self.fail('should have rejected invalid value')
                self.assertEqual(target.read_bytes(), before)

    def test_failed_save_does_not_prune(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'menu.json'
            cfg = deepcopy(DEFAULT_CONFIG)
            save_config(cfg, target)
            cfg['backup_retention'] = 1
            # Old auto backups are pruned only after the new config is installed.
            historical = target.with_name('menu.json.bak-20250101T000000000000Z')
            historical.write_text('old')
            with patch('openpowermenu.core.os.replace', side_effect=OSError('failed')):
                with self.assertRaises(OSError):
                    save_config(cfg, target)
            self.assertTrue(historical.exists())
            self.assertEqual(json.loads(target.read_text())['backup_retention'], 10)

    def test_menu_normalization_unchanged_from_field_baseline(self):
        baseline = Path('/mnt/data/OpenPowerMenu-RightClick-v0.4.16/openpowermenu/core.py')
        if not baseline.exists():
            self.skipTest('Previous release source unavailable')
        # Action additions and per-candidate checks are intentional. Keep the
        # field-tested menu normalization and desktop filtering boundary intact.
        selected = {'desktop_is_available', 'normalized_menu'}

        def snapshot(path):
            tree = ast.parse(path.read_text())
            result = {}
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    name = node.target.id
                else:
                    continue
                if name in selected:
                    result[name] = ast.dump(node, include_attributes=False)
            return result
        self.assertEqual(snapshot(ROOT / 'openpowermenu/core.py'), snapshot(baseline))

    def test_editor_exposes_limit_under_general(self):
        editor = (ROOT / 'openpowermenu/editor.py').read_text()
        for needle in ('QSpinBox', 'backupRetentionSpin', 'Configuration backups',
                       "config['backup_retention'] = self.backup_retention.value()"):
            self.assertIn(needle, editor)


if __name__ == '__main__':
    unittest.main()
