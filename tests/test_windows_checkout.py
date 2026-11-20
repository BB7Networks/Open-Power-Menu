"""Regression tests for Windows-safe source checkout and release packaging."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WindowsCheckoutTests(unittest.TestCase):
    def test_installers_have_distinct_paths(self):
        paths = ["install.sh", "uninstall.sh", "legacy/1.0.1/install.sh", "legacy/1.0.1/uninstall.sh", "legacy/1.0.1/scripts/install-core.sh", "legacy/1.0.1/scripts/uninstall-core.sh"]
        for path in paths:
            self.assertTrue((ROOT / path).is_file(), path)
        for wrapper in ('install.sh', 'uninstall.sh'):
            self.assertFalse((ROOT / wrapper.capitalize()).exists())
        self.assertEqual(len(set(path.casefold() for path in paths)), len(paths))
        self.assertIn("scripts/install-core.sh", (ROOT / "legacy/1.0.1/install.sh").read_text())
        self.assertIn("scripts/uninstall-core.sh", (ROOT / "legacy/1.0.1/uninstall.sh").read_text())
        release = (ROOT / "legacy/1.0.1/scripts/build-release.sh").read_text()
        self.assertIn("docs legacy;", release)
        self.assertIn("OpenPowerMenu-LegacyFixture-v", release)

    def test_source_has_no_windows_casefold_collisions(self):
        ignored = {".git", "dist", ".pytest_cache", "__pycache__", ".venv"}
        paths = {}
        for path in ROOT.rglob("*"):
            if not path.is_file() or ignored.intersection(path.relative_to(ROOT).parts):
                continue
            relative = path.relative_to(ROOT).as_posix()
            key = relative.casefold()
            self.assertNotIn(key, paths, f"Windows filename collision: {paths.get(key)} and {relative}")
            paths[key] = relative


if __name__ == "__main__":
    unittest.main()
