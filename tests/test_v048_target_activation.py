"""Regression: same selected Plasma applet receives both left and right operations."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from tests.qml_js_harness import bundle_adapter_js

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / 'plasmoid/contents/ui/main.qml'
JS = ROOT / 'plasmoid/contents/ui/adapters/LauncherAdapters.js'


def grab_method(source, method):
    token = '    function ' + method + '('
    start = source.index(token)
    begin = source.index('{',start)
    level=0
    for end in range(begin,len(source)):
        if source[end] == '{': level+=1
        if source[end] == '}':
            level-=1
            if level==0:return source[start:end+1]
    raise ValueError(method)


@unittest.skipUnless(shutil.which('node'), 'Requires Node for execution of real QML JS')
class SelectedInstanceTests(unittest.TestCase):
    def run_js(self, code):
        q=QML.read_text()
        methods='\n'.join(grab_method(q,n) for n in ('activateSelectedLauncher','activateLauncher','closeLauncherPopup'))
        helper=bundle_adapter_js()
        r=subprocess.run(['node','-e',code],env={**os.environ,'SOURCE':methods,'HELPER':helper},text=True,capture_output=True,timeout=12)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_selected_launcher_activated_and_closed_is_same_instance(self):
        self.run_js(r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const item={expanded:false,gridOpen:false,gridWindow:{visible:false},closeCount:0,
  closeWindow(){this.closeCount++;this.gridOpen=false;this.gridWindow.visible=false}};
let selectedActivations=0,otherActivations=0;
const selected={id:59,pluginName:'dev.xarbit.appgrid',activated(){selectedActivations++;item.gridOpen=true;item.gridWindow.visible=true}};
const other={id:75,pluginName:'dev.xarbit.appgrid',activated(){otherActivations++}};
const plan={applet:selected,item};
const root={selectedLauncherPlan:plan,launcherAppletId:59,menuSwitchEpoch:0,
  requestedMenu:'none',pendingPowerEpoch:-1,awaitingAsyncClose:false,
  launcherSwitchError:'',expanded:false,send(){throw Error('Must not use global activation')},
  activateSelectedLauncher(epoch){return env.activateSelectedLauncher(epoch)}};
const env={root,console,Plasmoid:{},LauncherVisibility:{prepare(){throw Error('Unexpected lookup')}},
  Qt:{callLater(fn){this.pending.push(fn)},pending:[]},
  LauncherAdapters:null,selectedLauncherPlan:plan,launcherClosePoll:{stop(){}},launcherCloseFollowup:{stop(){}}};
for (const key of ['selectedLauncherPlan','menuSwitchEpoch','requestedMenu','pendingPowerEpoch','awaitingAsyncClose','launcherSwitchError','expanded'])
 Object.defineProperty(env,key,{get(){return root[key]},set(v){root[key]=v}});
const helpers={};vm.createContext(helpers);vm.runInContext(process.env.HELPER,helpers);env.LauncherAdapters=helpers;
vm.createContext(env);vm.runInContext(process.env.SOURCE,env);
// Old code used a global search and might activate a different launcher.
// The new code invokes exactly widget 59, so its runtime state is observable.
env.activateLauncher();assert.equal(env.Qt.pending.length,1);env.Qt.pending.shift()();
assert.equal(selectedActivations,1);assert.equal(otherActivations,0);
assert.equal(item.gridOpen,true);
assert.equal(env.closeLauncherPopup().mode,'appgrid-native-close');
assert.equal(item.closeCount,1);assert.equal(item.gridOpen,false);
''')

    def test_explicit_target_unavailable_does_not_activate_any_other_launcher(self):
        self.run_js(r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
let global=0,old=0;
const root={menuSwitchEpoch:4,requestedMenu:'launcher',launcherAppletId:59,
  selectedLauncherPlan:{applet:{id:72,activated(){old++}}},
  launcherSwitchError:'',send(){global++}};
const env={root,console,Plasmoid:{containment:null,id:3},LauncherVisibility:{prepare(){throw Error('not found')}},
 selectedLauncherPlan:root.selectedLauncherPlan};
for(const key of ['menuSwitchEpoch','requestedMenu','launcherSwitchError','selectedLauncherPlan'])
 Object.defineProperty(env,key,{get(){return root[key]},set(v){root[key]=v}});
vm.createContext(env);vm.runInContext(process.env.SOURCE,env);
env.activateSelectedLauncher(4);
assert.equal(global,0);assert.equal(old,0);
assert.match(root.launcherSwitchError,/Selected launcher cannot be activated/);
''')

    def test_global_fallback_only_when_no_target_selected(self):
        self.run_js(r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const sent=[];
const root={menuSwitchEpoch:4,requestedMenu:'launcher',launcherAppletId:0,
  selectedLauncherPlan:null,launcherSwitchError:'',
  send(...args){sent.push(args);args[5](true,null)}};
const env={root,console,Plasmoid:{containment:null,id:3},LauncherVisibility:{prepare(){throw Error('no unique launcher')}},
 selectedLauncherPlan:null};
for(const key of ['menuSwitchEpoch','requestedMenu','launcherSwitchError','selectedLauncherPlan'])
 Object.defineProperty(env,key,{get(){return root[key]},set(v){root[key]=v}});
vm.createContext(env);vm.runInContext(process.env.SOURCE,env);
env.activateSelectedLauncher(4);
assert.equal(sent.length,1);assert.equal(sent[0][3],'activateLauncherMenu');
''')

if __name__ == '__main__':unittest.main()
