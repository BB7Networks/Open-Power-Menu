"""Unit tests for the side selection policy mirrored by SideFlyout.qml.

These verify the geometry decision; only a real Plasma/Wayland session can
verify the resulting popup window's compositor placement and event handling.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def choose_side(anchor_x, anchor_width, screen_x, screen_width, flyout_width):
    right_space = screen_x + screen_width - (anchor_x + anchor_width)
    left_space = anchor_x - screen_x
    required = flyout_width + 4
    if right_space >= required:
        return "right"
    if left_space >= required:
        return "left"
    return "right" if right_space >= left_space else "left"


class AdaptivePlacementTests(unittest.TestCase):
    def test_bottom_left_panel(self):
        self.assertEqual(choose_side(140, 315, 0, 1920, 278), "right")

    def test_top_right_panel(self):
        self.assertEqual(choose_side(1595, 300, 0, 1920, 278), "left")

    def test_right_side_panel(self):
        self.assertEqual(choose_side(940, 300, 0, 1280, 278), "left")

    def test_left_side_panel(self):
        self.assertEqual(choose_side(42, 300, 0, 1280, 278), "right")

    def test_multimonitor_offset(self):
        self.assertEqual(choose_side(2960, 300, 1920, 1366, 278), "left")

    def test_ultrawide_prefers_right_when_both_fit(self):
        self.assertEqual(choose_side(1200, 320, 0, 3440, 278), "right")

    def test_narrow_screen_chooses_less_cramped_side(self):
        self.assertEqual(choose_side(390, 300, 0, 800, 278), "left")
        self.assertEqual(choose_side(30, 300, 0, 500, 278), "right")

    def test_qml_anchors_to_visible_row_not_parent_popup(self):
        main = (ROOT/'plasmoid/contents/ui/main.qml').read_text()
        side = (ROOT/'plasmoid/contents/ui/SideFlyout.qml').read_text()
        self.assertIn('flyout.screenRect = sourceRow.menuScreen;', main)
        self.assertIn('readonly property rect menuScreen: Qt.rect(', main)
        self.assertIn('Screen.virtualX, Screen.virtualY', main)
        self.assertIn('floating: true', side)
        self.assertNotIn('floating: false\n', side)
        self.assertIn('const point = anchor.mapToGlobal(0, 0);', side)
        self.assertIn('if (availableScreen.width <= 0', side)
        self.assertIn('return Qt.RightEdge;', side)
        self.assertIn('popupDirection: Qt.RightEdge', side)
        self.assertIn('childPopup.screenRect = row.menuScreen;', side)
        self.assertNotIn('root.screenGeometry', main)

    def test_adaptive_side_geometry_when_screen_resolution_available(self):
        # 328px main menu at x=0 on a 1920px-wide screen: flyout to the right.
        self.assertEqual(choose_side(20, 328, 0, 1920, 278), "right")
        # Right-edge launcher: flyout to left, without relying on panel orientation.
        self.assertEqual(choose_side(1550, 328, 0, 1920, 278), "left")
        # Screen to the left of primary uses negative origins.
        self.assertEqual(choose_side(-290, 310, -1920, 1920, 278), "left")


if __name__ == '__main__':
    unittest.main()
