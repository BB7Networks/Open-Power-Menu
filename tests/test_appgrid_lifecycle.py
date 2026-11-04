"""Execute shipped adapters/handlers against AppGrid's close-animation contract.

This models state and event ordering, not a compositor or the reported flash.
"""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from tests.qml_js_harness import bundle_adapter_js
from tests.test_v0416_popup_handoff import function, timer_handler

pytestmark = pytest.mark.skipif(not shutil.which('node'), reason='Node required')
MAIN = Path(__file__).resolve().parents[1] / 'plasmoid/contents/ui/main.qml'


def run_node(code):
    source = MAIN.read_text()
    methods = '\n'.join(function(source, name) for name in (
        'activateLauncher', 'activateSelectedLauncher', 'openMenu', 'closeLauncherPopup',
        'finishOpeningPower', 'onOriginalLauncherOpened'))
    methods += '\n' + timer_handler(source, 'launcherActivationSettle')
    result = subprocess.run(['node', '-e', code], capture_output=True, text=True, timeout=15,
                            env={**os.environ, 'ADAPTERS': bundle_adapter_js(), 'METHODS': methods})
    assert result.returncode == 0, result.stderr


def test_repeated_handoffs_rapid_requests_drafts_and_sequenced_trace():
    run_node(r'''
const assert=require('node:assert/strict'), vm=require('node:vm');
const logs=[], h={console:{info(message){logs.push(message)}}};
vm.createContext(h); vm.runInContext(process.env.ADAPTERS,h);
for(const hidden of [false,true]) for(const draft of [null,{token:'opaque',entries:[{title:'PRIVATE'}]}]) {
  let activations=0, closes=0, deferred=[];
  const callbacks=[], animations=[];
  const item={gridOpen:false,gridWindow:{visible:false},expanded:false,
    closeWindow(){closes++; this.gridOpen=false; animations.push(()=>this.gridWindow.visible=false)}};
  const applet={id:59,pluginName:'dev.xarbit.appgrid',status:hidden?1:2,
    activated(){activations++; if(item.gridOpen) item.closeWindow();
      else {item.gridOpen=true;item.gridWindow.visible=true}}};
  const root={selectedLauncherPlan:{item,applet},selectedLauncherItem:item,launcherAppletId:59,
    menuSwitchEpoch:0,requestedMenu:'none',expanded:false,pendingPowerEpoch:-1,pendingLauncherEpoch:-1,
    awaitingAsyncClose:false,launcherSwitchError:'',maskActive:hidden,hideOriginalLauncherRequested:hidden,
    layoutDraft:draft,fetchMenu(){},send(){throw Error('Unexpected D-Bus activation')}};
  const timer=()=>({running:false,start(){this.running=true},restart(){this.running=true},stop(){this.running=false}});
  const c={root,console:h.console,LauncherAdapters:h,Qt:{callLater(f){callbacks.push(f)}},
    launcherActivationSettle:timer(),launcherClosePoll:timer(),launcherCloseFollowup:timer(),fetchIntegration(){},
    fetchMenu(){},closeLauncherPopup(){return root.closeLauncherPopup()}};
  for(const name of Object.keys(root)) Object.defineProperty(c,name,{configurable:true,get(){return root[name]},set(v){root[name]=v}});
  vm.createContext(c);vm.runInContext(process.env.METHODS,c);
  for(const name of ['activateSelectedLauncher','closeLauncherPopup','onOriginalLauncherOpened']) root[name]=c[name];
  function drain(){while(callbacks.length)callbacks.shift()()}
  function finishAnimations(){while(animations.length)animations.shift()()}
  for(let i=0;i<50;i++) {
    const before=activations;
    c.activateLauncher();drain();assert.equal(activations,before+1);
    assert.equal(item.gridOpen,true);assert.equal(item.gridWindow.visible,true);
    c.openMenu();assert.equal(item.gridOpen,false);assert.equal(item.gridWindow.visible,false);
    finishAnimations();c.finishOpeningPower(root.menuSwitchEpoch);
    assert.equal(root.expanded,true);
    const count=closes;
    c.closeLauncherPopup(); // the delayed right-click follow-up
    assert.equal(closes,count);assert.equal(animations.length,0);
    c.activateLauncher();assert.equal(root.expanded,false);
    c.settleTick();assert.equal(item.gridWindow.visible,true);
    // A completed stale close from an already-closed follow-up must not hide it.
    finishAnimations();assert.equal(item.gridWindow.visible,true);
    c.settleTick();assert.equal(activations,before+2); // duplicate timer does not toggle
    c.activateLauncher();drain();finishAnimations();assert.equal(item.gridOpen,false);
    // Rapid left-left-right: both unsent activations are stale.
    const rapid=activations;
    c.activateLauncher();c.activateLauncher();c.openMenu();drain();
    assert.equal(activations,rapid);c.finishOpeningPower(root.menuSwitchEpoch);
    root.expanded=false;
    assert.equal(root.layoutDraft,draft);
  }
  // A synchronous gridOpen signal occurs before AppGrid finishes showGrid().
  root.expanded=true;root.requestedMenu='power';c.launcherCloseFollowup.running=true;
  item.gridOpen=true;const count=closes;c.onOriginalLauncherOpened();
  assert.equal(closes,count);item.gridWindow.visible=true;drain();
  assert.equal(closes,count+1);assert.equal(item.gridWindow.visible,false);finishAnimations();
  // A newer left request cancels that deferred close.
  item.gridOpen=true;root.expanded=true;c.onOriginalLauncherOpened();
  c.activateLauncher();drain();assert.equal(closes,count+1);
}
const traces=logs.filter(line=>line.startsWith('Open Power Menu: AppGrid trace '))
  .map(line=>JSON.parse(line.slice('Open Power Menu: AppGrid trace '.length)));
assert.ok(traces.length>1000);
traces.forEach((entry,index)=>assert.equal(entry.seq,index+1));
assert.ok(traces.some(e=>e.event==='activation-callback'&&e.callbackEpoch!==e.epoch));
assert.ok(traces.some(e=>e.draft===true&&e.maskActive===false));
assert.ok(!JSON.stringify(traces).includes('PRIVATE'));
const count=logs.length;
for(const name of ['org.kde.plasma.kickoff','org.kde.plasma.kicker'])
  h.traceRequest({selectedLauncherPlan:{applet:{pluginName:name}}},'ignored',0);
assert.equal(logs.length,count);
''')
