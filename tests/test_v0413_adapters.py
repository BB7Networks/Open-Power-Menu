"""0.4.13: launcher adapter boundaries and regressions.

Node runs each real QML-JS adapter through the same imported-namespace contract;
these tests do not simulate Qt signals or Wayland input delivery.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from tests.qml_js_harness import bundle_adapter_js

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "plasmoid/contents/ui"
ADAPTERS = UI / "adapters"
PREVIOUS = Path('/mnt/data/OpenPowerMenu-RightClick-v0.4.12')


class ArchitectureTests(unittest.TestCase):
    def test_core_is_launcher_independent(self):
        qml = (UI / "main.qml").read_text()
        self.assertIn('import "adapters/LauncherAdapters.js" as LauncherAdapters', qml)
        self.assertIn('AdapterUi.AppGridPanelBridge {', qml)
        self.assertIn('LauncherAdapters.closeOriginal(', qml)
        self.assertIn('LauncherAdapters.originalIsVisiblyOpen(', qml)
        self.assertIn('LauncherAdapters.activate(', qml)
        self.assertIn('LauncherAdapters.chooseIcon(', qml)
        self.assertNotIn('dev.xarbit.appgrid', qml)
        self.assertNotIn('setInputRect(', qml)
        self.assertNotIn('gridOpenChanged', qml)
        self.assertNotIn('LauncherInteraction', qml)
        self.assertIn('value: root.hiddenStatusForRevision(root.launcherMaskRevision)', qml)
        self.assertIn('restoreMode: Binding.RestoreBindingOrValue', qml)

    def test_qml_and_script_imports_are_all_package_local(self):
        for path in (UI / 'main.qml', ADAPTERS / 'AppGridPanelBridge.qml'):
            for directory in re.findall(r'^import "([^".]+)" as \w+', path.read_text(), re.M):
                self.assertTrue((path.parent / directory).is_dir(), (path, directory))
            for script in re.findall(r'^import "([^"\n]+\.js)" as \w+', path.read_text(), re.M):
                self.assertTrue((path.parent / script).is_file(), (path, script))
        for path in ADAPTERS.glob('*.js'):
            for script in re.findall(r'^\.import "([^"\n]+)" as \w+', path.read_text(), re.M):
                self.assertTrue((path.parent / script).is_file(), (path, script))
            self.assertTrue(path.read_text().startswith('.pragma library'), path)
        self.assertNotIn('LauncherInteraction.js', [p.name for p in UI.iterdir()])

    def test_input_geometry_is_identical_to_live_proven_v0411(self):
        previous = Path('/mnt/data/OpenPowerMenu-RightClick-v0.4.11/plasmoid/contents/ui/LauncherPassThrough.js')
        if not previous.exists():
            self.skipTest('known-good baseline missing')
        self.assertEqual(previous.read_bytes(), (ADAPTERS/'AppGridPanelGeometry.js').read_bytes())

    def test_menu_backend_and_visibility_are_unchanged_since_0412(self):
        if not PREVIOUS.is_dir():
            self.skipTest('previous release unavailable')
        for rel in ('openpowermenu/core.py',
                    'plasmoid/contents/ui/LauncherVisibility.js',
                    'plasmoid/contents/ui/SideFlyout.qml',
                    'plasmoid/contents/ui/configGeneral.qml'):
            self.assertEqual((ROOT/rel).read_bytes(), (PREVIOUS/rel).read_bytes(), rel)

    def test_bridge_restores_on_disable_change_and_destruction(self):
        q = (ADAPTERS/'AppGridPanelBridge.qml').read_text()
        for part in ('onActiveChanged:', 'onSelectedLauncherPlanChanged:',
                     'onGridOpenChanged()', 'onIsDragInFlightChanged()',
                     'onVisibleChanged()', 'Component.onDestruction: reset()',
                     'if (!active) reset();', 'restoreAppGridPassThrough();',
                     'owner.setInputRect(win, 0, 0, 0, 0)', 'bridge.launcherOpened();'):
            self.assertIn(part, q)
        self.assertIn('onLauncherOpened: root.onOriginalLauncherOpened()',
                      (UI/'main.qml').read_text())


@unittest.skipUnless(shutil.which('node'), 'Node required')
class AdapterBehaviorTests(unittest.TestCase):
    def run_js(self, script):
        result = subprocess.run(['node', '-e', script],
                     env={**os.environ, 'SOURCES':bundle_adapter_js()},
                     capture_output=True, text=True, timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_routes_kickoff_kicker_third_party_without_appgrid_calls(self):
        self.run_js(r'''
const vm=require('node:vm'), assert=require('node:assert/strict');
const c={}; vm.createContext(c); vm.runInContext(process.env.SOURCES,c);
for (const name of ['org.kde.plasma.kickoff','org.kde.plasma.kicker','example.other.launcher','dev.xarbit.appgrid.panel']) {
  let activation=0; const item={expanded:true,gridWindow:{visible:true}};
  const applet={pluginName:name,icon:'test-icon',activated(){activation++},setInputRect(){throw Error('never mask generic')}};
  assert.equal(c.LauncherAdapters.kind(applet),'plasma');
  assert.equal(c.LauncherAdapters.activate(applet),true);assert.equal(activation,1);
  assert.equal(c.LauncherAdapters.chooseIcon(applet,'launcher','','fallback'),'test-icon');
  assert.equal(c.LauncherAdapters.originalIsVisiblyOpen(item,applet),true);
  assert.equal(c.LauncherAdapters.closeOriginal(item,applet,()=>{throw Error('no daemon')} ).mode,'plasma-expanded');
  assert.equal(item.expanded,false);
  assert.equal(item.gridWindow.visible,true); // generic must not modify 3rd-party owned windows
  assert.equal(c.AppGrid.supportsPanelPassThrough({applet,item}),false);
}
''')

    def test_unrecognized_custom_window_is_not_force_closed(self):
        self.run_js(r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const c={};vm.createContext(c);vm.runInContext(process.env.SOURCES,c);
const item={gridOpen:true,gridWindow:{visible:true},expanded:false,closeWindow(){throw Error('must not call')}};
const r=c.LauncherAdapters.closeOriginal(item,{pluginName:'example.fullscreen'});
assert.equal(r.ok,true); // generic expanded=false means no standard popup open
assert.equal(r.mode,'plasma-expanded');
assert.equal(item.gridWindow.visible,true); assert.equal(item.gridOpen,true);
''')

    def test_appgrid_center_gets_exact_special_case_no_other_plugin_does(self):
        self.run_js(r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const c={};vm.createContext(c);vm.runInContext(process.env.SOURCES,c);
const item={gridOpen:true,gridWindow:{visible:true},expanded:false,closeWindow(){this.gridOpen=false}};
const applet={id:59,pluginName:'dev.xarbit.appgrid',setInputRect(){}};
assert.equal(c.LauncherAdapters.kind(applet),'appgrid-center');
assert.equal(c.LauncherAdapters.originalIsVisiblyOpen(item,applet),true);
assert.equal(c.AppGrid.supportsPanelPassThrough({applet,item}),true);
const r=c.LauncherAdapters.closeOriginal(item,applet,()=>{throw Error('no daemon')});
assert.equal(r.mode,'appgrid-native-close');assert.equal(r.forceHidden,true);
assert.equal(item.gridWindow.visible,false);
''')

    def test_standalone_bus_no_owner_or_stale_callback_has_no_side_effect(self):
        self.run_js(r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const c={};vm.createContext(c);vm.runInContext(process.env.SOURCES,c);
let epoch=3;const pending=[],done=[];
const send=(...a)=>pending.push(a);
c.LauncherAdapters.requestAsyncClose({pluginName:'dev.xarbit.appgrid'},send,()=>epoch===3,(ok,why)=>done.push([ok,why]));
assert.equal(pending[0][3],'NameHasOwner'); pending[0][5](true,false);
assert.equal(pending.length,1);assert.equal(done.length,1);assert.equal(done[0][1],'not-running');
c.LauncherAdapters.requestAsyncClose({pluginName:'dev.xarbit.appgrid'},send,()=>epoch===3,(ok,why)=>done.push([ok,why]));
epoch=4;pending[1][5](true,true);
assert.equal(pending.length,2);assert.equal(done.length,1); // stale request: no Hide
''')


if __name__ == '__main__':
    unittest.main()
