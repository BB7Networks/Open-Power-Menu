"""v0.4.7 tests: actual right-click handoff paths and QML close polling.

Uses the *real* JS helpers and source-extracted QML handlers with simulated
applet visibility. These do not replace a live Plasma/Wayland acceptance test.
"""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from tests.qml_js_harness import bundle_adapter_js

ROOT=Path(__file__).resolve().parents[1]
QML=ROOT/'plasmoid/contents/ui/main.qml'
HELPER=ROOT/'plasmoid/contents/ui/adapters/LauncherAdapters.js'

def block_after(source, prefix):
    start=source.index(prefix)+len(prefix)
    left=source.index('{',start)
    n=0
    for i in range(left,len(source)):
        if source[i]=='{': n+=1
        elif source[i]=='}':
            n-=1
            if n==0: return source[left:i+1]
    raise AssertionError(prefix)

def run_node(test_code, **sources):
    run=subprocess.run(['node','-e',test_code],env={**os.environ,**sources},
                       text=True,capture_output=True,timeout=12)
    if run.returncode!=0:
        raise AssertionError(run.stderr)

@unittest.skipUnless(shutil.which('node'), 'Node required to execute QML JS')
class HandoffTests(unittest.TestCase):
    def test_legacy_window_must_be_physically_hidden_before_power_opens(self):
        js=bundle_adapter_js()
        run_node(r'''
const assert=require('node:assert/strict');const vm=require('node:vm');
const c={};vm.createContext(c);vm.runInContext(process.env.JS,c);
const item={expanded:false,gridOpen:true,gridWindow:{visible:true},closeWindow(){this.gridOpen=false}};
const applet={pluginName:'dev.xarbit.appgrid'};
assert.equal(c.originalIsOpen(item,applet),true);
assert.equal(c.closeOriginal(item,applet,()=>{}).mode,'appgrid-native-close');
assert.equal(item.gridOpen,false);
assert.equal(c.originalIsOpen(item,applet),false);
assert.equal(c.originalIsVisiblyOpen(item,applet),false); // v0.4.10 closes owned animation window immediately
assert.equal(item.gridWindow.visible,false); // exclusive menus take precedence
assert.equal(c.closeOriginal(item,applet,()=>{}).mode,'appgrid-local-closed');
''',JS=js)

    def test_failed_native_close_uses_guarded_activated_fallback(self):
        js=bundle_adapter_js()
        run_node(r'''
const assert=require('node:assert/strict');const vm=require('node:vm');
const c={};vm.createContext(c);vm.runInContext(process.env.JS,c);
let toggles=0;
const item={gridOpen:true,gridWindow:{visible:true},closeWindow(){throw Error('not callable')}};
const applet={pluginName:'dev.xarbit.appgrid',activated(){toggles++;item.gridOpen=!item.gridOpen}};
assert.equal(c.closeOriginal(item,applet,()=>{}).mode,'appgrid-activation-fallback');
assert.equal(toggles,1);assert.equal(item.gridOpen,false);
// Never risk triggering the launcher open while it's already closing.
assert.equal(c.closeOriginal(item,applet,()=>{}).mode,'appgrid-local-closed');
assert.equal(toggles,1);
item.gridWindow.visible=false;
assert.equal(c.originalIsVisiblyOpen(item,applet),false);
// If state is known open but neither close path works, refuse safely.
const broken={gridOpen:true,closeWindow(){throw Error('failed')}};
assert.equal(c.closeOriginal(broken,{pluginName:'dev.xarbit.appgrid'},()=>{}).mode,'appgrid-close-failed');
assert.equal(broken.gridOpen,true);
''',JS=js)

    def test_real_qml_close_poll_waits_for_animation_and_can_fail_safely(self):
        q=QML.read_text()
        # Precisely take the onTriggered body of the close-poll Timer.
        i=q.index('id: launcherClosePoll')
        tick=block_after(q[i:],'onTriggered:')
        finish=block_after(q, 'function finishOpeningPower(epoch)')
        js=bundle_adapter_js()
        run_node(r'''
const assert=require('node:assert/strict');const vm=require('node:vm');
const h={};vm.createContext(h);vm.runInContext(process.env.JS,h);
const item={gridOpen:false,gridWindow:{visible:true},expanded:false};
const applet={pluginName:'dev.xarbit.appgrid'};
const root={openingPower:true,requestedMenu:'power',pendingPowerEpoch:5,menuSwitchEpoch:5,
   launcherClosePollCount:0,launcherSwitchError:'',awaitingAsyncClose:false,
   selectedLauncherPlan:{item,applet},selectedLauncherItem:item,expanded:false,
   closeLauncherPopup(){this.retries++}, retries:0,
   finishOpeningPower(epoch){return c.finishOpeningPower(epoch)},
   fetchMenu(){this.loaded++},loaded:0};
const poll={running:true,stop(){this.running=false},restart(){this.running=true}};
const follow={running:false,restart(){this.running=true}};
const c={root,menuSwitchEpoch:5,requestedMenu:'power',expanded:false,
    LauncherAdapters:h,launcherClosePoll:poll,launcherCloseFollowup:follow,
    pendingPowerEpoch:5,awaitingAsyncClose:false,launcherSwitchError:'',
    openingPower:true,openingEntriesReady:false,
    // This handoff fixture has a ready backend; startup readiness is tested separately.
    preparePowerPopup(){root.expanded=true;follow.restart()},
    console,fetchMenu(_,done){root.loaded++;done()},stop(){poll.stop()}};
for(const key of ['expanded','menuSwitchEpoch','requestedMenu','pendingPowerEpoch','awaitingAsyncClose','launcherSwitchError'])
    Object.defineProperty(c,key,{get(){return root[key]},set(v){root[key]=v}});
vm.createContext(c);
vm.runInContext('function onTick() '+process.env.TICK+'\nfunction finishOpeningPower(epoch) '+process.env.FINISH,c);
// The Timer calls the source-extracted finishOpeningPower through root.
// Closed logically but still drawn: do not show Power yet.
c.onTick();
assert.equal(root.expanded,false);assert.equal(root.loaded,0);
assert.equal(root.launcherClosePollCount,1);
// Window completes the close animation; next poll opens Power.
item.gridWindow.visible=false;c.onTick();
assert.equal(root.expanded,true);assert.equal(root.loaded,1);assert.equal(follow.running,true);
assert.equal(poll.running,false);
// If the observed window never closes, no two popups may be shown.
root.expanded=false;root.requestedMenu='power';root.pendingPowerEpoch=6;root.menuSwitchEpoch=6;
root.launcherClosePollCount=49;item.gridWindow.visible=true;poll.running=true;
c.onTick();
assert.equal(root.expanded,false);assert.equal(root.pendingPowerEpoch,-1);
assert.match(root.launcherSwitchError,/did not close/);
assert.equal(poll.running,false);
''',JS=js,TICK=tick,FINISH=finish)

    def test_stale_standalone_hide_callback_cannot_complete_newer_click(self):
        q=QML.read_text()
        close=block_after(q,'function closeLauncherPopup()')
        js=bundle_adapter_js()
        run_node(r'''
const assert=require('node:assert/strict');const vm=require('node:vm');
const h={};vm.createContext(h);vm.runInContext(process.env.JS,h);
const item={expanded:false};const applet={pluginName:'dev.xarbit.appgrid'};
const root={menuSwitchEpoch:2,requestedMenu:'power',selectedLauncherItem:item,
  selectedLauncherPlan:{item,applet},awaitingAsyncClose:false,launcherSwitchError:'',
  send(...args){this.replies.push(args[5])},replies:[]};
const c={root,LauncherAdapters:h,Plasmoid:{},console,selectedLauncherPlan:root.selectedLauncherPlan,
  launcherClosePoll:{stop(){}}};
Object.defineProperty(c,'selectedLauncherPlan',{get(){return root.selectedLauncherPlan},set(v){root.selectedLauncherPlan=v}});
vm.createContext(c);vm.runInContext('function closeLauncherPopup() '+process.env.CLOSE,c);
assert.equal(c.closeLauncherPopup().mode,'appgrid-daemon-hide');
assert.equal(root.awaitingAsyncClose,true);
assert.equal(root.replies.length,1);
// The bus-owner check is async; a newer click makes the first response stale.
root.menuSwitchEpoch=3;root.awaitingAsyncClose=true;
root.replies[0](true,true);
assert.equal(root.replies.length,1); // Stale owner cannot issue Hide.
assert.equal(root.awaitingAsyncClose,true);
assert.equal(root.launcherSwitchError,'');
// The next request checks the owner, then sends Hide only when owned.
assert.equal(c.closeLauncherPopup().mode,'appgrid-daemon-hide');
assert.equal(root.replies.length,2);
root.replies[1](true,true);
assert.equal(root.replies.length,3);
root.replies[2](true,null);
assert.equal(root.awaitingAsyncClose,false);
''',JS=js,CLOSE=close)

if __name__=='__main__': unittest.main()
