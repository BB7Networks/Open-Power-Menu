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
        self.assertIn('Layout.preferredHeight: fittedHeight', qml)
        self.assertIn('Layout.minimumHeight: fittedHeight', qml)
        self.assertIn('Layout.maximumHeight: fittedHeight', qml)
        self.assertIn('root.menuWorkArea.height', qml)
        self.assertNotIn('Math.min(590', qml)
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


def test_shared_metrics_preserve_custom_height_and_negative_work_area():
    import shutil, subprocess
    import pytest
    if not shutil.which('node'):
        pytest.skip('Node required')
    source = (ROOT/'plasmoid/contents/ui/MenuMetrics.js').read_text().replace('.pragma library', '')
    code = source + '''
const assert=require('node:assert/strict');
assert.deepEqual(workArea({x:-1920,y:-1080,width:1920,height:1080}, {x:42,y:36,width:1878,height:1000}),
 {x:-1878,y:-1044,width:1878,height:1000});
for (const scale of [1,1.25,1.5]) {
 // These already are logical coordinates: applying DPR again would be wrong.
 const available=1200/scale, padding=24;
 for (const density of ['compact','standard','comfortable']) {
  for (const icons of [0,iconSize('small',18),iconSize('large',30)]) {
   const natural=60+30*rowHeight(density,18,icons)+13;
   assert.equal(menuHeight('auto',600,natural,available,padding), Math.min(Math.ceil(natural),Math.floor(available-padding-8)));
   assert.equal(menuHeight('custom',360,natural,available,padding),360);
  }
 }
}
assert.equal(menuHeight('custom',900,800,500,24),468);
assert.equal(menuHeight('custom',900,800,1400,24),900); // preference survives screen constraint
assert.equal(menuHeight('auto',900,300,1400,24),300); // Reset to automatic
assert(iconSize('large',30)>iconSize('small',18));
assert(rowHeight('comfortable',18,0)>rowHeight('compact',18,0));
'''
    result = subprocess.run(['node','-e',code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
