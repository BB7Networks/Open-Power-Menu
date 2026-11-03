"""Screen-clamped bottom-edge submenu alignment tests.

PopupPlasmaWindow horizontally centers RightEdge/LeftEdge side popups on the
anchor item's vertical center. See SideFlyout.positionAtRow.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


def place(row_y, row_h, popup_h, screen_y, screen_h, margin=4):
    # Mirror of SideFlyout.positionAtRow's vertical geometry policy.
    top = screen_y + margin
    bottom = screen_y + screen_h - margin
    top_limit = max(top, bottom - popup_h)
    want = row_y + row_h - popup_h
    target_top = max(top,min(want,top_limit))
    proxy_center = target_top + popup_h / 2
    return target_top, proxy_center


class BottomAlignmentTests(unittest.TestCase):
    def test_bottom_panel_aligns_to_parent_row_bottom(self):
        top, anchor = place(653,34,176,0,900)
        self.assertEqual(top+176,653+34)
        self.assertAlmostEqual(anchor,top+88)

    def test_middle_row_has_bottom_aligned_flyout(self):
        top,_=place(400,34,185,0,900)
        self.assertEqual(top+185,434)

    def test_nested_submenus_also_bottom_align(self):
        top,_=place(614,34,146,0,900)
        self.assertEqual(top+146,648)

    def test_at_top_edge_clamps_down(self):
        top,_=place(22,34,185,0,900)
        self.assertEqual(top,4)

    def test_at_screen_bottom_stays_visible(self):
        top,_=place(854,34,176,0,900)
        self.assertEqual(top+176,888)

    def test_nonzero_multimonitor_screen_origin(self):
        top,_=place(450,34,156,240,600)
        self.assertEqual(top+156,484)

    def test_tall_submenu_clamps_if_screen_short(self):
        top,_=place(100,34,340,0,400)
        self.assertEqual(top,4)

    def test_helper_used_by_top_level_and_nested(self):
        main=(ROOT/'plasmoid/contents/ui/main.qml').read_text()
        side=(ROOT/'plasmoid/contents/ui/SideFlyout.qml').read_text()
        self.assertIn('flyout.positionAtRow(sourceRow, flyoutAnchor, sourceRow.menuScreen);',main)
        self.assertIn('childPopup.positionAtRow(row, childAnchor, row.menuScreen);',side)
        self.assertIn('visualParent = flyoutAnchor',main)
        self.assertIn('"visualParent": childAnchor',side)
        self.assertIn('const requestedTop = rowGlobal.y + row.height - popupH;',side)
        self.assertNotIn('childPopup.chooseSide(row)',side)


if __name__=='__main__': unittest.main()
