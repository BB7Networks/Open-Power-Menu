"""0.4.12: two-tab Configure contract and minimal, verified adapter cleanup.

Editor checks are source/AST checks: the CI environment lacks PySide6, and a
live Plasma/Wayland compositor is required for end-to-end GUI acceptance.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "openpowermenu/editor.py"
INTERACTION = ROOT / "plasmoid/contents/ui/adapters/AppGridLauncher.js"
PREVIOUS = Path("/mnt/data/OpenPowerMenu-RightClick-v0.4.11")


def editor_method(name: str) -> str:
    source = EDITOR.read_text()
    module = ast.parse(source)
    cls = next(n for n in ast.walk(module) if isinstance(n, ast.ClassDef) and n.name == "MenuEditor")
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(source, node)


class ConfigureTabsTests(unittest.TestCase):
    def test_two_tabs_are_explicitly_general_then_layout(self):
        src = editor_method("__init__")
        self.assertIn('tabs = QTabWidget(self)', src)
        self.assertIn('tabs.addTab(general_scroll, "General")', src)
        self.assertIn('tabs.addTab(layout_tab, "Layout")', src)
        self.assertLess(src.index('tabs.addTab(general_scroll, "General")'),
                        src.index('tabs.addTab(layout_tab, "Layout")'))
        self.assertIn('QScrollArea(tabs)', src)
        self.assertIn('setWidgetResizable(True)', src)
        self.assertEqual(src.count('tabs.addTab('), 2)

    def test_launchers_and_icons_are_general_not_layout(self):
        src = editor_method("__init__")
        general, layout = src.split('# LAYOUT:', 1)
        for feature in ('self.launcher_target', 'self.hide_launcher',
                        'self.icon_mode', 'self.button_icon', 'self.appearance'):
            self.assertIn(feature, general)
            self.assertNotIn(feature, layout)
        self.assertNotIn('self.launcher_target.setEnabled(', src)
        self.assertIn('list_panel_applets()', general)
        self.assertIn('open-power-menu --show-launcher-button', general)

    def test_layout_tab_contains_only_menu_builder(self):
        src = editor_method("__init__")
        layout = src.split('# LAYOUT:', 1)[1]
        for feature in ('QTreeWidget(layout_tab)', 'self.add_button',
                        'self.show_missing', 'self.restore_defaults',
                        '"Built-in command"', '"Custom command"',
                        '"Submenu"', '"Separator"'):
            self.assertIn(feature, layout)
        self.assertIn('Nothing is written until you select Save', layout)
        self.assertEqual(src.count('buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)'), 1)

    def test_layout_reset_does_not_reset_appearance_or_launcher(self):
        src = editor_method("restore_defaults")
        self.assertIn('self.fill(DEFAULT_CONFIG["menu"])', src)
        self.assertIn('self.show_missing.setChecked(DEFAULT_CONFIG["show_unavailable"])', src)
        for unsafe in ('self.appearance.setCurrentIndex', 'self.hide_launcher.setChecked',
                       'self.icon_mode.setCurrentIndex', 'save_config('):
            self.assertNotIn(unsafe, src)
        # Save still commits all fields together; Cancel has no write path.
        self.assertIn('save_config(self.cfg)', editor_method('accept'))

    def test_unmodified_visual_surfaces_match_known_good(self):
        # A source-only adapter refactor must not change visual menu layout,
        # backend/editor config, or the proven reversible status binding helper.
        if not PREVIOUS.is_dir():
            self.skipTest('v0.4.11 baseline unavailable outside release environment')
        for name in ('LauncherVisibility.js', 'SideFlyout.qml', 'configGeneral.qml'):
            rel = Path('plasmoid/contents/ui') / name
            self.assertEqual((ROOT / rel).read_bytes(), (PREVIOUS / rel).read_bytes(), name)
        self.assertIn('value: root.hiddenStatusForRevision(root.launcherMaskRevision)',
                      (ROOT/'plasmoid/contents/ui/main.qml').read_text())

    def test_local_appgrid_no_longer_probes_nonexistent_daemon(self):
        src = INTERACTION.read_text()
        local_start = src.index('if (hasLegacyWindow(item)) {')
        standalone_start = src.index('    // Newer standalone AppGrid:', local_start)
        local = src[local_start:standalone_start]
        self.assertNotIn('hideStandalone()', local)
        self.assertIn('hideOwnedAppGridWindow(item)', local)
        self.assertIn('mode:"appgrid-local-closed"', local)
        standalone = src[standalone_start:]
        self.assertIn('hideStandalone()', standalone)


if __name__ == '__main__':
    unittest.main()
