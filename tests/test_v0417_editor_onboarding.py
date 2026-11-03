"""v0.4.17: discoverable built-ins, searchable app picker, safe command entry."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from openpowermenu.core import DEFAULT_CONFIG, load_config, save_config
from openpowermenu.desktop_apps import (
    DesktopApplication, application_command, application_menu_item,
    desktop_exec_argv, installed_applications, read_desktop_application,
)
from openpowermenu.editor_helpers import (
    built_in_candidates, editable_builtin_copy, preview_command,
)

ROOT = Path(__file__).resolve().parents[1]


def create_desktop(root: Path, relative: str, *, name: str = "Example", extra: str = "") -> Path:
    target = root / "applications" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "[Desktop Entry]\nType=Application\nName=" + name + "\nIcon=example\n"
        + "Exec=example --open %U\n" + extra, encoding="utf-8")
    return target


class AppCatalogTests(unittest.TestCase):
    def test_xdg_precedence_hides_system_entry_when_user_override_hidden(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            user, system = root / "user", root / "sys"
            create_desktop(system, "same.desktop", name="From system")
            create_desktop(user, "same.desktop", name="Hidden override", extra="Hidden=true\n")
            create_desktop(system, "visible.desktop", name="Visible app")
            with patch.dict(os.environ, {"XDG_DATA_HOME": str(user), "XDG_DATA_DIRS": str(system),
                                              "XDG_CURRENT_DESKTOP": "KDE"}):
                apps = installed_applications()
            self.assertEqual([app.name for app in apps], ["Visible app"])

    def test_filter_nonapps_desktop_visibility_and_tryexec(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            create_desktop(base, "okay.desktop", name="Okay", extra="OnlyShowIn=KDE;GNOME;\n")
            create_desktop(base, "not.desktop", name="Not allowed", extra="OnlyShowIn=GNOME;\n")
            create_desktop(base, "blocked.desktop", name="Blocked", extra="NotShowIn=KDE;\n")
            create_desktop(base, "skip.desktop", name="Skip", extra="NoDisplay=true\n")
            create_desktop(base, "missing.desktop", name="Missing", extra="TryExec=unlikely-command-xyz\n")
            create_desktop(base, "link.desktop", name="Link", extra="Type=Link\n")
            with patch.dict(os.environ, {"XDG_DATA_HOME": str(base), "XDG_DATA_DIRS": str(base),
                                              "XDG_CURRENT_DESKTOP": "KDE"}):
                apps = installed_applications()
            self.assertEqual([app.name for app in apps], ["Okay"])

    def test_locale_name_icon_desktop_source_and_terminal(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            path = create_desktop(base, "terminal.desktop", name="Base name",
                                  extra="Name[fr]=Nom francais\nTerminal=true\nComment=Description\n")
            with patch("openpowermenu.desktop_apps.locale.getlocale", return_value=("fr_FR", "UTF-8")):
                app = read_desktop_application(path)
            self.assertEqual(app.name, "Nom francais")
            self.assertEqual(app.icon, "example")
            self.assertTrue(app.terminal)
            self.assertEqual(app.comment, "Description")

    def test_native_kde_desktop_launcher_is_preferred(self):
        app = DesktopApplication("Example", "example", Path("/usr/share/applications/example.desktop"), "example %U")
        with patch("openpowermenu.desktop_apps.shutil.which", side_effect=lambda name: "/usr/bin/kioclient6" if name == "kioclient6" else None):
            item = application_menu_item(app)
        self.assertEqual(item["command"], ["kioclient6", "exec", "/usr/share/applications/example.desktop"])
        self.assertEqual(item["icon"], "example")
        self.assertEqual(item["label"], "Example")
        self.assertIn("desktop_file", item)

    def test_gio_fallback_and_direct_exec_last_resort(self):
        app = DesktopApplication("Docs", "system-file-manager", Path("/tmp/docs.desktop"), 'dolphin --new-window %U')
        with patch("openpowermenu.desktop_apps.shutil.which", side_effect=lambda name: "/usr/bin/gio" if name == "gio" else None):
            self.assertEqual(application_command(app), ["gio", "launch", "/tmp/docs.desktop"])
        with patch("openpowermenu.desktop_apps.shutil.which", return_value=None):
            self.assertEqual(application_command(app), ["dolphin", "--new-window"])

    def test_exec_fallback_quoted_args_field_codes_and_percent(self):
        path = Path("/tmp/file.desktop")
        self.assertEqual(desktop_exec_argv('tool "two words" %i %c %k %% %u', "Nice App", "nice-icon", path),
                         ["tool", "two words", "--icon", "nice-icon", "Nice App", "/tmp/file.desktop", "%"])
        with self.assertRaisesRegex(ValueError, "Unsupported field code"):
            desktop_exec_argv('tool %Z', "app", "icon", path)
        with self.assertRaisesRegex(ValueError, "Invalid desktop Exec"):
            desktop_exec_argv('tool "unfinished', "app", "icon", path)

    def test_terminal_or_dbus_only_requires_real_launcher(self):
        with patch("openpowermenu.desktop_apps.shutil.which", return_value=None):
            app = DesktopApplication("Terminal", "", Path("/tmp/t.desktop"), "tool", terminal=True)
            with self.assertRaisesRegex(ValueError, "terminal"):
                application_command(app)
            app = DesktopApplication("DBus", "", Path("/tmp/dbus.desktop"), "")
            with self.assertRaisesRegex(ValueError, "desktop activation"):
                application_command(app)

    def test_custom_app_entries_roundtrip_existing_schema_without_migration(self):
        app = DesktopApplication("Browser", "browser", Path("/usr/share/applications/browser.desktop"), "browser")
        with patch("openpowermenu.desktop_apps.shutil.which", return_value="/usr/bin/kioclient6"):
            entry = application_menu_item(app)
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "menu.json"
            original = deepcopy(DEFAULT_CONFIG)
            original["menu"].append(entry)
            save_config(original, path)
            self.assertEqual(load_config(path)["menu"][-1], entry)
            self.assertEqual(preview_command(entry), "kioclient6 exec /usr/share/applications/browser.desktop")


class EditorDiscoverabilityTests(unittest.TestCase):
    def test_builtin_commands_visible_and_copy_is_independent(self):
        with patch("openpowermenu.editor_helpers.which_executable", side_effect=lambda name: name == "konsole"):
            with patch("openpowermenu.core.which_executable", side_effect=lambda name: name == "konsole"):
                selected, options = built_in_candidates("terminal")
                editable = editable_builtin_copy("terminal", label="My terminal")
        self.assertEqual(selected, "konsole")
        self.assertIn("1. konsole  [installed]", options)
        self.assertTrue(any("kitty  [not available]" in option for option in options))
        self.assertEqual(editable["command"], ["konsole"])
        self.assertNotIn("action", editable)

    def test_editor_surface_has_search_and_argv_explanation(self):
        src = (ROOT / "openpowermenu/editor.py").read_text()
        self.assertIn('"Installed application...", self.add_application', src)
        self.assertIn("class InstalledApplicationDialog", src)
        self.assertIn("installed_applications()", src)
        self.assertIn("Search applications by name or description", src)
        self.assertIn("builtInResolvedCommand", src)
        self.assertIn("builtInFallbackCommands", src)
        self.assertIn('"Runs on this computer"', src)
        self.assertIn('"Customize this command..."', src)
        self.assertIn("are not interpreted", src)
        self.assertNotIn('"command": ["true"]', src)
        self.assertIn('tabs.addTab(general_scroll, "General")', src)
        self.assertIn('tabs.addTab(layout_tab, "Layout")', src)

    def test_compositor_and_launcher_files_identical_to_field_baseline(self):
        previous = Path("/mnt/data/OpenPowerMenu-RightClick-v0.4.16")
        if not (previous / "plasmoid/contents/ui/main.qml").exists():
            self.skipTest("Original field-tested source tree unavailable")
        for rel in (
            "plasmoid/contents/ui/main.qml",
            "plasmoid/contents/ui/LauncherVisibility.js",
            "plasmoid/contents/ui/SideFlyout.qml",
            "plasmoid/contents/ui/adapters/AppGridLauncher.js",
            "plasmoid/contents/ui/adapters/AppGridPanelBridge.qml",
            "plasmoid/contents/ui/adapters/LauncherAdapters.js",
            "openpowermenu/core.py",
        ):
            self.assertEqual((ROOT / rel).read_bytes(), (previous / rel).read_bytes(), rel)


if __name__ == '__main__':
    unittest.main()
