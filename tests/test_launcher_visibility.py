"""Runtime-only, launcher-agnostic integration: selection, safe recovery, no panel writes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from openpowermenu.cli import main
from openpowermenu.core import DEFAULT_CONFIG, load_config, save_config
from openpowermenu.plasma_panels import list_panel_applets, is_likely_launcher

ROOT = Path(__file__).resolve().parents[1]
VISIBILITY = ROOT / 'plasmoid/contents/ui/LauncherVisibility.js'


class LauncherVisibilityTests(unittest.TestCase):
    def test_hidden_option_defaults_off_and_auto(self):
        self.assertIs(DEFAULT_CONFIG['hide_original_launcher'], False)
        self.assertEqual(DEFAULT_CONFIG['launcher_applet_id'], 0)
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(Path(tmp) / 'missing.json')
            self.assertIs(cfg['hide_original_launcher'], False)
            self.assertEqual(cfg['launcher_applet_id'], 0)

    def test_invalid_configuration_cannot_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'menu.json'
            cfg = dict(DEFAULT_CONFIG)
            save_config(cfg, target)
            before = target.read_bytes()
            for key, value in [('hide_original_launcher','false'),
                               ('launcher_applet_id',True), ('launcher_applet_id','11'),
                               ('launcher_applet_id', -1), ('launcher_applet_id', 2**32)]:
                wrong = dict(cfg, **{key:value})
                with self.assertRaises(ValueError):
                    save_config(wrong, target)
                self.assertEqual(target.read_bytes(), before)

    def test_cli_recovery_restores_visibility_and_keeps_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}):
                target = Path(tmp) / 'open-power-menu' / 'menu.json'
                cfg = dict(DEFAULT_CONFIG)
                cfg['hide_original_launcher'] = True
                cfg['launcher_applet_id'] = 49
                save_config(cfg, target)
                self.assertEqual(main(['--show-launcher-button']), 0)
                self.assertIs(load_config(target)['hide_original_launcher'], False)
                self.assertEqual(load_config(target)['launcher_applet_id'], 49)
                backups = list(target.parent.glob('menu.json.bak-*'))
                self.assertEqual(len(backups), 1)
                self.assertTrue(json.loads(backups[0].read_text())['hide_original_launcher'])

    def test_readonly_panel_inventory_includes_third_party_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)/'appletsrc'
            config.write_text('''[Containments][2]
plugin=org.kde.panel
[Containments][2][Applets][15]
plugin=org.openpowermenu.start
[Containments][2][Applets][31]
plugin=dev.xarbit.appgrid.panel
[Containments][2][Applets][31][Configuration]
name=Won't become an applet
[Containments][2][Applets][44]
plugin=com.example.ourspecialmenu
[Containments][2][Applets][46]
plugin=org.kde.plasma.digitalclock
[Containments][10]
plugin=org.kde.plasma.folder
[Containments][10][Applets][55]
plugin=org.kde.plasma.kickoff
''')
            home = Path(tmp)/'data'
            md = home/'plasma/plasmoids/com.example.ourspecialmenu/metadata.json'
            md.parent.mkdir(parents=True)
            md.write_text('{"KPlugin":{"Name":"Super User Launcher"}}')
            before = config.read_bytes()
            applets = list_panel_applets(config, home)
            self.assertEqual({a.applet_id for a in applets}, {31, 44, 46})
            self.assertEqual(applets[0].applet_id, 31)
            custom = next(a for a in applets if a.applet_id == 44)
            self.assertTrue(custom.likely_launcher)
            self.assertIn('Super User Launcher',custom.option_label)
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse(is_likely_launcher('com.example.clock','Analog Clock'))
            with patch.dict(os.environ,{'XDG_CONFIG_HOME':str(Path(tmp)/'missing')}):
                self.assertEqual(main(['--launcher-diagnostics']),0)

    def test_editor_discovery_and_safe_opt_in(self):
        editor = (ROOT/'openpowermenu/editor.py').read_text()
        for phrase in ("Hide the original launcher's panel button", 'list_panel_applets()',
                       'self.launcher_target', 'launcher_applet_id',
                       'open-power-menu --show-launcher-button'):
            self.assertIn(phrase, editor)
        svc = (ROOT/'openpowermenu/service.py').read_text()
        self.assertIn('"launcher_applet_id": cfg.get("launcher_applet_id", 0)', svc)
        qml = (ROOT/'plasmoid/contents/ui/main.qml').read_text()
        for phrase in ('GetIntegration', 'LauncherVisibility.prepare(', 'launcherAppletId',
                       'target: root.maskedLauncher', 'value: root.hiddenStatusForRevision(root.launcherMaskRevision)',
                       'restoreMode: Binding.RestoreBindingOrValue',
                       'releaseMask();', 'LauncherVisibility.didHide('):
            self.assertIn(phrase,qml)
        for forbidden in ('root.maskFirst', 'root.maskSecond', 'root.maskIcon',
                          'value: 1;', 'opacity: 0', 'Layout.maximumWidth'):
            self.assertNotIn(forbidden,qml[:qml.index('    function fetchIntegration(')])

    def test_no_modification_of_saved_plasma_or_launcher_state(self):
        js = VISIBILITY.read_text()
        for phrase in ('org.kde.plasma.kickoff', 'dev.xarbit.appgrid',
                       'requestedId > 0', 'findContainmentItem', 'win.contentItem'):
            self.assertIn(phrase,js)
        qml = (ROOT/'plasmoid/contents/ui/main.qml').read_text()
        for forbidden in ('removeApplet(', 'unlink(', 'writeConfig(',
                          'plasma-org.kde.plasma.desktop-appletsrc'):
            self.assertNotIn(forbidden, js + qml)
        for forbidden in ('visible = false', 'enabled = false', 'opacity = 0;', 'destroy('):
            self.assertNotIn(forbidden, js)
        self.assertNotIn('panel-snapshot.sh', (ROOT/'scripts/install-core.sh').read_text())

    def test_native_widget_settings_page_accepts_loader_properties(self):
        qml = (ROOT/'plasmoid/contents/ui/configGeneral.qml').read_text()
        self.assertIn('Kirigami.Page {', qml)
        self.assertIn('title: "General"', qml)
        for prop in ('cfg_buttonIconDefault', 'cfg_leftActionDefault',
                     'cfg_buttonIcon', 'cfg_leftAction'):
            self.assertIn(prop, qml)
        self.assertIn('Kirigami.FormLayout {', qml)

    @unittest.skipUnless(shutil.which('node'), 'Node is optional; JS mocked QML tests skipped')
    def test_scene_graph_selection_and_plasma_hidden_status(self):
        src = VISIBILITY.read_text().replace('.pragma library\n', '', 1)
        test = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
let context = {};
vm.createContext(context);
vm.runInContext(process.env.ADAPTER_JS, context);
const mk = (id,pluginName,title='') => ({id,pluginName,title,status:2});
const self = mk(12,'org.openpowermenu.start');
const custom = mk(41,'com.example.unrecognized','Various things');
const grid = mk(59,'dev.xarbit.appgrid','AppGrid');
const kickoff = mk(52,'org.kde.plasma.kickoff','Application Launcher');
assert.equal(context.findOriginal([self,grid],12,0),grid);
assert.throws(()=>context.findOriginal([self,grid,kickoff],12,0),/unique/);
assert.equal(context.findOriginal([self,custom,grid],12,41),custom);
assert.throws(()=>context.findOriginal([self,grid],12,41),/not found/);
assert.throws(()=>context.findOriginal([self],12,12),/not found/);
// The real panel uses a Loader with isAppletContainer and applet=item.
// The launcher intentionally has NO compactRepresentationItem or Layout hints.
const item = {parent:null,visible:true};
const wrapper = {isAppletContainer:true,applet:item,visible:true,parent:null};
item.parent = wrapper;
let root = {parent:null,Window:{window:{contentItem:{children:[]}}}};
const panel = {plasmoid:{id:2},children:[],itemFor(a){return a===grid?item:a===self?root:null;}};
wrapper.parent=panel;
root.Window.window.contentItem.children=[{children:[panel]}];
const plan=context.prepare(root,[self,grid],self,12,2,59);
assert.equal(plan.applet,grid);
assert.equal(plan.item,item);
assert.equal(plan.container,wrapper);
assert.equal(context.didHide(plan,6),false);
// Binding in QML changes ONLY applet.status. KDE panel bindings respond:
grid.status=6;
item.visible=false;
wrapper.visible=false;
assert.equal(context.didHide(plan,6),true);
item.visible=true;
assert.equal(context.didHide(plan,6),false);
// During edit mode Plasma deliberately shows otherwise hidden applets.
grid.containment={corona:{editMode:true}};
assert.equal(context.didHide(plan,6),true);
grid.containment={corona:{editMode:false}};
item.visible=false;
// A target without its real panel wrapper must be left visible.
wrapper.isAppletContainer=false;
assert.throws(()=>context.prepare(root,[self,grid],self,12,2,59),/no KDE panel container/);
wrapper.isAppletContainer=true;
assert.throws(()=>context.prepare(root,[self],self,12,2,59),/not found/);
root.Window.window.contentItem={children:[{itemFor:()=>null,children:[]}]};
assert.throws(()=>context.prepare(root,[self,grid],self,12,2,59),/Could not find/);
'''
        result = subprocess.run(['node','-e',test],
                                env={**os.environ,'ADAPTER_JS':src}, capture_output=True,
                                text=True,check=False)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_upstream_supported_visibility_contract_documented(self):
        integration = (ROOT/'INTEGRATION.md').read_text()
        for name in ('LayoutManager.js', 'AppletContainer.qml', 'shellcorona.cpp',
                     'HiddenStatus', 'activateLauncherMenu'):
            self.assertIn(name, integration)


if __name__ == '__main__':
    unittest.main()
