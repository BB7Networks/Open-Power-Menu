"""v0.4.10 regression tests for AppGrid 1.9.6 in-process QML window closing.

These execute real helper JS on Node models. They cannot prove the runtime
window lookup works on the user's exact Plasma/Wayland panel.
"""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from tests.qml_js_harness import bundle_adapter_js

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT/'plasmoid/contents/ui/adapters/LauncherAdapters.js'
QML = ROOT/'plasmoid/contents/ui/main.qml'

@unittest.skipUnless(shutil.which('node'), 'Node required for QML JS behavior tests')
class AppGridInProcessTests(unittest.TestCase):
    def run_node(self, code):
        result=subprocess.run(['node','-e',code],env={**os.environ,'SOURCE':bundle_adapter_js()},capture_output=True,text=True,timeout=12)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_pending_close_animation_is_force_hidden_by_right_click(self):
        self.run_node(r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const c={};vm.createContext(c);vm.runInContext(process.env.SOURCE,c);
const window={visible:true};
const item={gridOpen:true,gridWindow:window,expanded:false,closeWindow(){this.gridOpen=false}};
const a={pluginName:'dev.xarbit.appgrid'};
const result=c.closeOriginal(item,a,()=>{});
assert.equal(result.ok,true); assert.equal(result.mode,'appgrid-native-close');
assert.equal(result.forceHidden,true);
assert.equal(window.visible,false); assert.equal(item.gridOpen,false);
assert.equal(c.originalIsVisiblyOpen(item,a),false);
''')

    def test_grid_open_false_but_window_still_visible_is_hidden(self):
        self.run_node(r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const c={};vm.createContext(c);vm.runInContext(process.env.SOURCE,c);
let closeCalls=0, probes=0;
const item={gridOpen:false,gridWindow:{visible:true},closeWindow(){closeCalls++}};
const result=c.closeOriginal(item,{pluginName:'dev.xarbit.appgrid'},()=>probes++);
assert.equal(result.ok,true); assert.equal(result.mode,'appgrid-local-closed');
assert.equal(result.forceHidden,true);assert.equal(item.gridWindow.visible,false);
assert.equal(closeCalls,1);assert.equal(probes,0); // Never probe an absent standalone daemon
''')

    def test_unknown_or_already_closed_window_not_mutated(self):
        self.run_node(r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const c={};vm.createContext(c);vm.runInContext(process.env.SOURCE,c);
const w={visible:false};const item={gridOpen:false,gridWindow:w,closeWindow(){}};
assert.equal(c.hideOwnedAppGridWindow(item),false);
const result=c.closeOriginal(item,{pluginName:'dev.xarbit.appgrid'},()=>{});
assert.equal(result.forceHidden,false); assert.equal(w.visible,false);
const other={expanded:true,gridWindow:{visible:true}};
const r=c.closeOriginal(other,{pluginName:'org.kde.plasma.kickoff'});
assert.equal(r.mode,'plasma-expanded');assert.equal(other.expanded,false);
assert.equal(other.gridWindow.visible,true); // never change unrelated applets
''')

    def test_debug_snapshots_are_both_before_and_after_close_and_open(self):
        q=QML.read_text()
        self.assertIn('launcher before right-click',q)
        self.assertIn('traceDismissal(',q)
        self.assertIn('launcher before left-click',q)
        self.assertIn('launcher after left-click',q)
        self.assertIn('observed AppGrid gridOpen change:', (ROOT/'plasmoid/contents/ui/adapters/AppGridPanelBridge.qml').read_text())
        self.assertIn('forcedHidden=', (ROOT/'plasmoid/contents/ui/adapters/LauncherAdapters.js').read_text())
        self.assertIn('value: root.hiddenStatusForRevision(root.launcherMaskRevision)',q)
        self.assertIn('LauncherAdapters.chooseIcon(',q)
        self.assertNotIn('selectedLauncherItem.visible =',q)

if __name__ == '__main__': unittest.main()
