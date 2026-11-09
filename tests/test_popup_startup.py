"""Exercise the shipped opening handlers with asynchronous, reordered D-Bus replies.

Real Plasma geometry is also tested by native/tests/plasma_startup.py.
"""
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from tests.test_v0416_popup_handoff import function

UI = Path(__file__).resolve().parents[1] / 'plasmoid/contents/ui/main.qml'


def test_opening_waits_for_preferences_model_and_layout_and_cancels_stale_replies():
    if not shutil.which('node'):
        pytest.skip('Node required')
    source = UI.read_text()
    methods = '\n'.join(function(source, name) for name in (
        'openMenu', 'finishOpeningPower', 'preparePowerPopup', 'fetchIntegration',
        'fetchMenu', 'rebuild', 'activateLauncher'))
    script = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
function fixture() {
 const calls=[],later=[];
 const timer=()=>({running:false,start(){this.running=true},stop(){this.running=false},restart(){this.running=true}});
 const c={console,Qt:{callLater(f){later.push(f)}},
  LauncherAdapters:{traceRequest(){},originalIsVisiblyOpen(item){return item && item.expanded===true}},launcherClosePoll:timer(),launcherCloseFollowup:timer(),
  launcherActivationSettle:timer(),powerRefresh:timer(),menuSwitchEpoch:0,menuFetchEpoch:0,integrationFetching:false,integrationCallbacks:[],
  expanded:false,requestedMenu:'none',openingPower:false,openingEntriesReady:false,openingPreferencesReady:false,
  pendingPowerEpoch:-1,pendingLauncherEpoch:-1,awaitingAsyncClose:false,launcherSwitchError:'',
  powerIsOpen:false,powerRefreshAttempts:0,layoutEditing:false,layoutBusy:false,menuEntries:[],visibleEntries:[],
  fetching:false,menuStatus:'',backendMissing:false,launcherAppletId:0,menuHeightMode:'auto',menuCustomHeight:600,
  closeLauncherPopup(){return {ok:true}},synchronizeLauncherVisibility(){},releaseMask(){},activateSelectedLauncher(){},
  fullRepresentationItem:{prepared:0,prepareForOpen(){this.prepared++}},
  send(service,path,iface,method,args,done){calls.push({method,args,done})}};
 c.root=c;vm.createContext(c);vm.runInContext(METHODS,c);
 return {c,calls,later,reply(method,value,ok=true){const i=calls.findIndex(x=>x.method===method);assert(i>=0,method);calls.splice(i,1)[0].done(ok,typeof value==='boolean'?value:JSON.stringify(value))},
 drain(){while(later.length)later.shift()()}};
}
const menu=[{kind:'command',key:'safe',title:'Safe',enabled:true}];
for(const order of ['preferences-first','menu-first']) for(const mode of ['auto','custom']) {
 const f=fixture(),c=f.c; c.openMenu();c.finishOpeningPower(c.menuSwitchEpoch);
 assert.equal(c.expanded,false);assert.equal(c.fetching,true);
 const prefs=()=>f.reply('GetIntegration',{menu_density:'comfortable',menu_icon_size:'large',menu_height_mode:mode,menu_custom_height:910});
 const entries=()=>{f.reply('GetMenu',menu);assert.equal(c.expanded,false);f.reply('PowerCapabilitiesPending',false)};
 if(order==='preferences-first'){prefs();f.drain();assert.equal(c.expanded,false);entries()}
 else {entries();f.drain();assert.equal(c.expanded,false);prefs()}
 assert.equal(c.expanded,false);assert.equal(c.preloadFullRepresentation,true);
 f.drain();assert.equal(c.expanded,true);assert.equal(c.menuDensity,'comfortable');assert.equal(c.menuIconSize,'large');
 assert.equal(c.menuHeightMode,mode);assert.equal(c.menuCustomHeight,910);assert.equal(c.fullRepresentationItem.prepared,2);
 assert.equal(c.visibleEntries.length,1);assert.equal(f.calls.length,0);
 c.openMenu();assert.equal(c.expanded,false);
 c.openMenu();c.finishOpeningPower(c.menuSwitchEpoch);
 // Cancel a new opening while its requests are outstanding.
 c.openMenu();f.reply('GetIntegration',{});f.reply('GetMenu',menu);f.drain();assert.equal(c.expanded,false);
 assert.equal(c.menuCustomHeight,600); // Only backend preferences changed it; no save was sent.
 assert(!f.calls.some(x=>x.method==='SetMenuHeight'));
}
// Initial capabilities can arrive after GetMenu; prepare only after discovery.
{
 const f=fixture(),c=f.c;c.openMenu();c.finishOpeningPower(c.menuSwitchEpoch);
 f.reply('GetIntegration',{});f.reply('GetMenu',[]);f.reply('PowerCapabilitiesPending',true);f.drain();
 assert.equal(c.expanded,false);assert.equal(c.powerRefresh.running,true);
 c.fetchMenu(true,c.powerRefresh.readyCallback);f.reply('GetMenu',menu);f.reply('PowerCapabilitiesPending',false);f.drain();
 assert.equal(c.expanded,true);assert.equal(c.visibleEntries.length,1);
}
// Errors expose a usable recovery popup instead of leaving an opening stuck.
{
 const f=fixture(),c=f.c;c.openMenu();c.finishOpeningPower(c.menuSwitchEpoch);
 f.reply('GetIntegration',null,false);f.reply('GetMenu',null,false);f.drain();
 assert.equal(c.expanded,true);assert.equal(c.backendMissing,true);
}
// A launcher opened through Meta during backend loading keeps ownership.
{
 const f=fixture(),c=f.c;c.openMenu();c.finishOpeningPower(c.menuSwitchEpoch);
 f.reply('GetIntegration',{});f.reply('GetMenu',menu);f.reply('PowerCapabilitiesPending',false);
 c.selectedLauncherItem={expanded:true};f.drain();assert.equal(c.expanded,false);assert.equal(c.openingPower,false);
}
// Repeated preference polls share a slow opening request, never starve it.
{
 const f=fixture(),c=f.c;c.openMenu();c.finishOpeningPower(c.menuSwitchEpoch);
 for(let poll=0;poll<10;poll++) c.fetchIntegration();
 assert.equal(f.calls.filter(x=>x.method==='GetIntegration').length,1);
 f.reply('GetMenu',menu);f.reply('PowerCapabilitiesPending',false);
 f.reply('GetIntegration',{menu_height_mode:'custom',menu_custom_height:900});f.drain();
 assert.equal(c.expanded,true);assert.equal(c.menuCustomHeight,900);
}
// A left-click after data completion but before layout preparation cancels it.
{
 const f=fixture(),c=f.c;c.openMenu();c.finishOpeningPower(c.menuSwitchEpoch);
 f.reply('GetIntegration',{});f.reply('GetMenu',menu);f.reply('PowerCapabilitiesPending',false);
 c.activateLauncher();f.drain();assert.equal(c.expanded,false);assert.equal(c.fullRepresentationItem.prepared,0);
}
'''
    result = subprocess.run(['node', '-e', 'const METHODS='+json.dumps(methods)+';\n'+script],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
