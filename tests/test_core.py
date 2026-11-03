import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from openpowermenu.core import (
    COMMANDS, DEFAULT_CONFIG, config_path, describe_menu, desktop_is_available,
    expand_part, get_item_info, load_config, normalized_menu, resolve_action,
    which_executable,
)


class MenuCoreTests(unittest.TestCase):
    def test_menu_shape_contains_expected_actions(self):
        ids = {item["action"] for item in DEFAULT_CONFIG["menu"] if "action" in item}
        self.assertTrue({"applications", "power", "logs", "system", "network", "disks", "terminal", "monitor", "files", "settings", "run"}.issubset(ids))

    def test_default_no_automatic_privilege_escalation(self):
        for action in COMMANDS.values():
            for item in action.get("commands", []):
                cmd = item["argv"] if isinstance(item, dict) else item
                self.assertNotIn(cmd[0], ("sudo", "su", "pkexec", "doas"))
                self.assertNotIn("sh", cmd[:1])
                self.assertNotIn("-c", cmd[:1])

    def test_krunner_restricted_to_kde(self):
        with mock.patch("shutil.which", side_effect=lambda cmd: "/usr/bin/" + cmd if cmd in ("qdbus6", "rofi") else None):
            with mock.patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "GNOME"}):
                cmd = resolve_action("run")
                self.assertEqual(cmd.argv, ("rofi", "-show", "run"))
            with mock.patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "KDE"}):
                cmd = resolve_action("run")
                self.assertEqual(cmd.argv[0], "qdbus6")

    def test_kde_power_commands_are_confirmation_prompts(self):
        for name in ("logout", "reboot", "shutdown"):
            self.assertIn("org.kde.LogoutPrompt", COMMANDS[name]["commands"][0])
            self.assertTrue(COMMANDS[name]["commands"][0][-1].startswith("prompt"))

    def test_custom_command_is_argv_not_shell(self):
        with mock.patch("shutil.which", side_effect=lambda name: "/usr/bin/" + name):
            _, _, cmd = get_item_info({"label": "My tool", "command": ["echo", "hello world"]})
        self.assertEqual(cmd.argv, ("echo", "hello world"))

    def test_custom_command_rejects_shell_string(self):
        with self.assertRaisesRegex(ValueError, "argv list"):
            get_item_info({"label": "bad", "command": "rm -rf ~/"})

    def test_command_fallback_to_second_candidate(self):
        def fake_which(name):
            return "/usr/bin/" + name if name == "gnome-software" else None
        with mock.patch("shutil.which", side_effect=fake_which):
            cmd = resolve_action("applications")
        self.assertEqual(cmd.argv, ("gnome-software",))

    def test_builtin_missing(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertIsNone(resolve_action("vms"))

    def test_desktop_filter(self):
        with mock.patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "KDE"}):
            self.assertTrue(desktop_is_available(["KDE", "PLASMA"]))
            self.assertFalse(desktop_is_available(["GNOME"]))
        with mock.patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "GNOME:KDE"}):
            self.assertTrue(desktop_is_available(["KDE"]))

    def test_no_desktop_filter(self):
        self.assertTrue(desktop_is_available(None))

    def test_path_requirement(self):
        with mock.patch("shutil.which", return_value="/usr/bin/dolphin"):
            with mock.patch("pathlib.Path.exists", return_value=False):
                self.assertIsNone(resolve_action("network_locations"))

    def test_unknown_action_raises(self):
        with self.assertRaisesRegex(ValueError, "Unknown built-in"):
            get_item_info({"action": "nope"})

    def test_config_invalid_format_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "menu.json"
            path.write_text('[]')
            with self.assertRaises(ValueError):
                load_config(path)

    def test_config_preserves_custom_value(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "menu.json"
            path.write_text(json.dumps({"menu": [{"action": "terminal"}], "appearance": "aero"}))
            cfg = load_config(path)
            self.assertEqual(cfg["appearance"], "aero")
            self.assertEqual(len(cfg["menu"]), 1)
            self.assertEqual(cfg["anchor"], "cursor")

    def test_config_invalid_anchor_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "menu.json"
            path.write_text(json.dumps({"menu": [], "anchor": "outside"}))
            with self.assertRaises(ValueError):
                load_config(path)

    def test_submenus_and_separator_cleaning(self):
        with mock.patch("shutil.which", side_effect=lambda x: "/usr/bin/" + x if x == "dolphin" else None):
            entries = normalized_menu([
                {"separator": True}, {"action": "terminal"}, {"separator": True},
                {"separator": True}, {"action": "files"}, {"separator": True},
                {"submenu": "Empty", "items": [{"action": "terminal"}]},
                {"separator": True},
            ])
        self.assertEqual([it["kind"] for it in entries], ["command"])
        self.assertEqual(entries[0]["title"], "File Manager")

    def test_unavailable_can_be_shown_disabled(self):
        with mock.patch("shutil.which", return_value=None):
            entries = normalized_menu([{"action": "terminal"}], show_unavailable=True)
        self.assertEqual(len(entries), 1)
        self.assertIsNone(entries[0]["command"])

    def test_custom_submenu_rendering(self):
        with mock.patch("shutil.which", return_value="/bin/echo"):
            entries = normalized_menu([{"submenu": "Custom", "items": [{"label": "Hello", "command": ["echo", "Hi"]}]}])
        self.assertIn("Hello", "\n".join(describe_menu(entries)))

    def test_home_expansion(self):
        self.assertEqual(expand_part("{home}/Network Locations"), str(Path.home() / "Network Locations"))

    def test_non_executable_absolute_path(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "script"
            f.write_text("hi")
            self.assertFalse(which_executable(str(f)))
            f.chmod(0o700)
            self.assertTrue(which_executable(str(f)))


if __name__ == "__main__":
    unittest.main()
