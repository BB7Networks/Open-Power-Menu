"""Pure-Python tests for the widget-facing API and reversible packaging."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from openpowermenu.core import DEFAULT_CONFIG
from openpowermenu.menu_api import to_public_menu, command_at_key, public_json

ROOT = Path(__file__).resolve().parents[1]


class WidgetMenuTests(unittest.TestCase):
    def test_menu_round_trip_public_keys(self):
        with patch('openpowermenu.core.which_executable', return_value=True), \
             patch('openpowermenu.core.desktop_is_available', return_value=True), \
             patch('pathlib.Path.exists', return_value=True):
            entries = json.loads(public_json(DEFAULT_CONFIG))
            self.assertTrue(entries)
            self.assertTrue(any(e['kind'] == 'submenu' for e in entries))
            def validate(tree):
                for entry in tree:
                    self.assertNotIn('argv', entry)
                    self.assertNotIn('command', entry)
                    if entry['kind'] == 'command':
                        self.assertIsNotNone(command_at_key(DEFAULT_CONFIG, entry['key']))
                    elif entry['kind'] == 'submenu':
                        validate(entry['items'])
            validate(entries)

    def test_cannot_inject_commands_by_keys(self):
        for key in ('', '0;rm -rf ~', '0/1', '-1', '../etc/passwd', 'NaN', '1.2.3.4.5.6.7.8.9.10.11.12.13', '99999', '1.0'):
            self.assertIsNone(command_at_key(DEFAULT_CONFIG, key), key)

    def test_disabled_item_never_resolves(self):
        cfg = {'menu': [{'command': ['/this/definitely/does/not/exist'], 'label': 'Missing'}], 'show_unavailable': True}
        j = json.loads(public_json(cfg))
        self.assertEqual(j[0]['enabled'], False)
        self.assertIsNone(command_at_key(cfg, '0'))

    def test_exposes_only_expected_dbus_methods(self):
        data = (ROOT/'openpowermenu'/'service.py').read_text()
        for name in ('GetMenu', 'Run', 'Ping'):
            self.assertIn('def '+name+'(', data)
        self.assertIn('registerObject(OBJECT_PATH, BUS_NAME, service,', data)
        self.assertNotIn('shell=True', data)

    def test_plasma_widget_metadata_xml_and_qml(self):
        widget = ROOT/'plasmoid'
        meta=json.loads((widget/'metadata.json').read_text())
        self.assertEqual(meta['KPackageStructure'], 'Plasma/Applet')
        self.assertEqual(meta['KPlugin']['Id'], 'org.openpowermenu.start')
        ElementTree.parse(widget/'contents/config/main.xml')
        qml=(widget/'contents/ui/main.qml').read_text()
        self.assertIn('Qt.RightButton',qml)
        self.assertIn('activateLauncherMenu',qml)
        self.assertIn('GetMenu',qml)
        self.assertIn('Run',qml)
        self.assertIn('compactRepresentation: Item {',qml)
        self.assertIn('fullRepresentation: Item {',qml)
        self.assertIn('preferredRepresentation: compactRepresentation',qml)
        self.assertNotIn('Plasmoid.compactRepresentation:',qml)
        self.assertNotIn('Plasmoid.fullRepresentation:',qml)
        self.assertNotIn('Plasmoid.preferredRepresentation:',qml)
        self.assertNotIn('xdotool',qml)


if __name__ == '__main__':
    unittest.main()


class FlyoutAndConfigureTests(unittest.TestCase):
    def test_uses_cascading_popups_not_inline_menu_rows(self):
        qml = (ROOT / 'plasmoid/contents/ui/main.qml').read_text()
        self.assertIn('visibleEntries = menuEntries;', qml)
        self.assertIn('SideFlyout {', qml)
        self.assertIn('popup.showFlyout(menuRow.entry, menuRow)', qml)
        self.assertIn('flyout.visualParent = flyoutAnchor', qml)
        self.assertNotIn('flyout.popup(sourceRow', qml)
        self.assertNotIn('QQC2.Menu {', qml)
        self.assertNotIn('openSections', qml)
        side = (ROOT / 'plasmoid/contents/ui/SideFlyout.qml').read_text()
        self.assertIn('PlasmaCore.PopupPlasmaWindow {', side)
        self.assertIn('popupDirection: Qt.RightEdge', side)
        self.assertIn('floating: true', side)
        self.assertIn('"visualParent": childAnchor', side)
        self.assertIn('Screen.desktopAvailableHeight', side)
        self.assertIn('anchor.mapToGlobal(0, 0)', side)
        self.assertIn('screenRect.width <= 0', side)
        self.assertIn('freeRight >= required', side)
        self.assertIn('freeLeft >= required', side)
        self.assertIn('flyout.popupDirection = flyout.chooseSide(flyoutAnchor)', qml)
        self.assertIn('Qt.createComponent(Qt.resolvedUrl("SideFlyout.qml"))', side)

    def test_header_opens_external_menu_editor(self):
        qml = (ROOT / 'plasmoid/contents/ui/main.qml').read_text()
        self.assertIn('Plasmoid.hasConfigurationInterface: true', qml)
        self.assertIn('function openEditor()', qml)
        self.assertIn('"Edit", []', qml)
        self.assertIn('onClicked: root.openEditor()', qml)
        self.assertNotIn('Plasmoid.action("configure")', qml)
        config = (ROOT / 'plasmoid/contents/ui/configGeneral.qml').read_text()
        self.assertIn('import QtQuick.Layouts', config)
        self.assertIn('cfg_buttonIcon', config)
        self.assertIn('cfg_leftAction', config)

    def test_preserves_launcher_and_backend(self):
        qml = (ROOT / 'plasmoid/contents/ui/main.qml').read_text()
        self.assertIn('activateLauncherMenu', qml)
        self.assertIn('org.openpowermenu.Service', qml)
        self.assertIn('Run", [key]', qml)
        self.assertIn('org.kde.plasmashell', qml)
        self.assertNotIn('xdotool', qml)
