"""Regression tests for Windows-safe source checkout and release packaging."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WindowsCheckoutTests(unittest.TestCase):
    def test_installers_have_distinct_paths(self):
        paths = ["Install.sh", "Uninstall.sh", "scripts/install-core.sh", "scripts/uninstall-core.sh"]
        for path in paths:
            self.assertTrue((ROOT / path).is_file(), path)
        self.assertEqual(len(set(path.casefold() for path in paths)), len(paths))
        self.assertIn("scripts/install-core.sh", (ROOT / "Install.sh").read_text())
        self.assertIn("scripts/uninstall-core.sh", (ROOT / "Uninstall.sh").read_text())
        release = (ROOT / "scripts/build-release.sh").read_text()
        self.assertIn('cp -a "$root/scripts/install-core.sh"', release)
        self.assertIn('"$root/scripts/uninstall-core.sh"', release)

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
