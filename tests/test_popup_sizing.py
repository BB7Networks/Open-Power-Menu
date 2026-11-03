"""Guard against recreating unused popup footer space after header migration.

The CI runner has no Plasma QML runtime; these tests verify binding topology,
not live popup rendering. Live Wayland testing is still required.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / 'plasmoid/contents/ui/main.qml'


class MainPopupSizingTests(unittest.TestCase):
    def test_preferred_height_tracks_actual_rendered_rows(self):
        qml = QML.read_text()
        self.assertIn('readonly property real naturalHeight:', qml)
        self.assertIn('menuColumn.implicitHeight', qml)
        self.assertIn('menuHeader.implicitHeight', qml)
        self.assertIn('menuStatusLabel.implicitHeight', qml)
        self.assertIn('Screen.desktopAvailableHeight', qml)
        self.assertRegex(qml, r'Layout\.preferredHeight:\s*Math\.max\(76,\s*Math\.min\(heightCap,\s*naturalHeight\)\)')
        self.assertNotIn('Layout.minimumHeight: 180', qml)
        self.assertNotIn('Layout.preferredHeight: Math.min(590, 85 * Kirigami.Units.gridUnit)', qml)

    def test_scrollview_tracks_content_and_reserves_no_footer(self):
        qml = QML.read_text()
        self.assertIn('contentHeight: menuColumn.implicitHeight', qml)
        self.assertIn('width: menuScroll.availableWidth', qml)
        self.assertIn('id: menuStatusLabel', qml)
        self.assertEqual(qml.count('id: refreshButton'), 1)
        self.assertEqual(qml.count('id: configureButton'), 1)
        self.assertLess(qml.index('id: configureButton'), qml.index('id: menuScroll'))
        self.assertNotRegex(qml, r'Kirigami\.Separator\s*\{[^}]+\}\s*RowLayout\s*\{\s*Layout\.fillWidth: true\s*Layout\.margins: 8')

    def test_does_not_change_flyout_anchor_contract(self):
        qml = QML.read_text()
        side = (ROOT / 'plasmoid/contents/ui/SideFlyout.qml').read_text()
        self.assertIn('flyout.positionAtRow(sourceRow, flyoutAnchor, sourceRow.menuScreen);', qml)
        self.assertIn('flyout.popupDirection = flyout.chooseSide(flyoutAnchor);', qml)
        self.assertIn('const requestedTop = rowGlobal.y + row.height - popupH;', side)
        self.assertIn('Qt.createComponent(Qt.resolvedUrl("SideFlyout.qml"))', side)

    def test_snapshot_helper_is_non_destructive(self):
        src = (ROOT / 'tools/panel-snapshot.sh').read_text()
        self.assertIn('mktemp -d', src)
        self.assertIn('chmod 700', src)
        self.assertNotIn('plasma-plasmashell.service', src)
        for unsafe in ('rm -rf', 'killall', 'kwriteconfig', 'sed -i', 'plasmashell --replace'):
            self.assertNotIn(unsafe, src)


if __name__ == '__main__':
    unittest.main()
