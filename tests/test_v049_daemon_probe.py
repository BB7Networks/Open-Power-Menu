"""v0.4.9 regression: a false legacy gridOpen flag cannot skip standalone Hide.

The QML handler is extracted and exercised with simulated replies; this does
not assert that the user's live AppGrid window actually belongs to the daemon.
"""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from tests.qml_js_harness import bundle_adapter_js

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT/'plasmoid/contents/ui/main.qml'
HELPER = ROOT/'plasmoid/contents/ui/adapters/LauncherAdapters.js'


def grab(source, name):
    start = source.index('    function '+name+'(')
    brace = source.index('{', start)
    depth = 0
    for p in range(brace,len(source)):
        if source[p] == '{': depth += 1
        elif source[p] == '}':
            depth -= 1
            if depth == 0: return source[start:p+1]
    raise ValueError(name)


@unittest.skipUnless(shutil.which('node'), 'Node required for QML JS model tests')
class OwnerProbeTests(unittest.TestCase):
    def run_js(self, source):
        qml = QML.read_text()
        funcs = grab(qml,'closeLauncherPopup')
        helper = bundle_adapter_js()
        r = subprocess.run(['node','-e',source], env={**os.environ,'QML':funcs,'JS':helper},
                           capture_output=True,text=True,timeout=12)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_legacy_196_closed_state_uses_local_close_without_daemon_probe(self):
        self.run_js(r'''
const assert=require('node:assert/strict');const vm=require('node:vm');
const h={};vm.createContext(h);vm.runInContext(process.env.JS,h);
let localCloses=0;
const item={gridOpen:false,gridWindow:{visible:false},expanded:false,
  closeWindow(){localCloses++;}};
const applet={pluginName:'dev.xarbit.appgrid',id:59};
const plan={applet,item};const calls=[];
const root={menuSwitchEpoch:10,requestedMenu:'power',selectedLauncherPlan:plan,
  awaitingAsyncClose:false,launcherSwitchError:'',send(...args){calls.push(args)}};
const c={root,LauncherAdapters:h,console,selectedLauncherPlan:plan,
  launcherClosePoll:{stop(){}}};
Object.defineProperty(c,'selectedLauncherPlan',{get(){return root.selectedLauncherPlan},set(v){root.selectedLauncherPlan=v}});
vm.createContext(c);vm.runInContext(process.env.QML,c);
const result=c.closeLauncherPopup();
assert.equal(result.mode,'appgrid-local-closed');
assert.equal(localCloses,0); // Already closed: do not restart AppGrid's exit animation.
assert.equal(root.awaitingAsyncClose,false);
assert.equal(calls.length,0); // v0.4.9's redundant D-Bus probe is removed.
''')

    def test_newer_standalone_build_still_probes_and_hides_running_daemon(self):
        self.run_js(r'''
const assert=require('node:assert/strict');const vm=require('node:vm');
const h={};vm.createContext(h);vm.runInContext(process.env.JS,h);
const item={expanded:false};  // no legacy gridOpen or gridWindow
const applet={pluginName:'dev.xarbit.appgrid',id:59};
const plan={applet,item};const calls=[];
const root={menuSwitchEpoch:10,requestedMenu:'power',selectedLauncherPlan:plan,
  awaitingAsyncClose:false,launcherSwitchError:'',send(...args){calls.push(args)}};
const c={root,LauncherAdapters:h,console,selectedLauncherPlan:plan,
  launcherClosePoll:{stop(){}}};
Object.defineProperty(c,'selectedLauncherPlan',{get(){return root.selectedLauncherPlan},set(v){root.selectedLauncherPlan=v}});
vm.createContext(c);vm.runInContext(process.env.QML,c);
const result=c.closeLauncherPopup();
assert.equal(result.mode,'appgrid-daemon-hide');
assert.equal(root.awaitingAsyncClose,true);
assert.equal(calls.length,1);
assert.equal(calls[0][3],'NameHasOwner');
calls[0][5](true,true);
assert.equal(calls.length,2);assert.equal(calls[1][0],'dev.xarbit.appgrid');
assert.equal(calls[1][3],'Hide');assert.equal(calls[1][4].length,0);
calls[1][5](true,null);
assert.equal(root.awaitingAsyncClose,false);assert.equal(root.launcherSwitchError,'');
''')

    def test_no_daemon_owner_does_not_activate_a_new_service(self):
        self.run_js(r'''
const assert=require('node:assert/strict');const vm=require('node:vm');
const h={};vm.createContext(h);vm.runInContext(process.env.JS,h);
const item={expanded:false}; // standalone build, not 1.9.x
const plan={applet:{pluginName:'dev.xarbit.appgrid'},item};const calls=[];
const root={menuSwitchEpoch:3,requestedMenu:'power',selectedLauncherPlan:plan,
  awaitingAsyncClose:false,launcherSwitchError:'',send(...args){calls.push(args)}};
const c={root,LauncherAdapters:h,selectedLauncherPlan:plan,console,launcherClosePoll:{stop(){}}};
Object.defineProperty(c,'selectedLauncherPlan',{get(){return root.selectedLauncherPlan},set(v){root.selectedLauncherPlan=v}});
vm.createContext(c);vm.runInContext(process.env.QML,c);
c.closeLauncherPopup();
assert.equal(calls.length,1);assert.equal(calls[0][3],'NameHasOwner');
calls[0][5](true,false);
assert.equal(calls.length,1); // no autoactivation of dormant AppGrid daemon
assert.equal(root.awaitingAsyncClose,false);
''')

    def test_stale_reply_never_hides_a_new_launcher(self):
        self.run_js(r'''
const assert=require('node:assert/strict');const vm=require('node:vm');
const h={};vm.createContext(h);vm.runInContext(process.env.JS,h);
const plan={applet:{pluginName:'dev.xarbit.appgrid'},item:{expanded:false}};const calls=[];
const root={menuSwitchEpoch:5,requestedMenu:'power',selectedLauncherPlan:plan,
  awaitingAsyncClose:false,launcherSwitchError:'',send(...args){calls.push(args)}};
const c={root,LauncherAdapters:h,selectedLauncherPlan:plan,console,launcherClosePoll:{stop(){}}};
Object.defineProperty(c,'selectedLauncherPlan',{get(){return root.selectedLauncherPlan},set(v){root.selectedLauncherPlan=v}});
vm.createContext(c);vm.runInContext(process.env.QML,c);
c.closeLauncherPopup();root.menuSwitchEpoch=6;root.requestedMenu='launcher';
calls[0][5](true,true);
assert.equal(calls.length,1); // stale owner check cannot issue Hide
''')

if __name__=='__main__': unittest.main()
