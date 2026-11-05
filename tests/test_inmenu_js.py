"""Execute the actual draft/controller JS and activation guard with Node."""
from pathlib import Path
import shutil
import subprocess

import pytest

from test_v0416_popup_handoff import braced, function

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'plasmoid/contents/ui'


def library(name, exports):
    source = (UI / (name + '.js')).read_text()
    source = '\n'.join(line for line in source.splitlines() if not line.startswith('.'))
    return f'const {name} = (() => {{\n{source}\nreturn {{{exports}}};\n}})();\n'


def test_draft_and_controller_behavior():
    if not shutil.which('node'):
        pytest.skip('Node is required for QML JavaScript tests')
    code = 'const assert=require("node:assert/strict");\n'
    code += library('LayoutDraft', 'references,start,dirty,find,children,valid,move,select,nextIndex')
    code += 'const Draft=LayoutDraft;\n'
    code += library('LayoutController', 'begin,cancel,toggle,save,keep')
    code += r'''
const entries=[{id:'a',kind:'command',title:'Hidden'},
 {id:'g',kind:'submenu',title:'Group',items:[{id:'b',kind:'command',title:'B'}]},
 {id:'e',kind:'submenu',title:'Empty',items:[]},{id:'s',kind:'separator',title:'Separator'}];
const draft=Draft.start({token:'token',entries});
assert.equal(Draft.dirty(draft),false);
let moved=Draft.move(draft,'a','g','b');
assert.deepEqual(Draft.children(moved.entries,'g').map(e=>e.id),['a','b']);
moved=Draft.move(moved,'g','e','');
assert.equal(Draft.children(moved.entries,'e')[0].items.length,2);
assert.equal(Draft.dirty(moved),true);
assert.equal(draft.entries.length,4); // failed/accepted edits never mutate original input
assert.throws(()=>Draft.move(draft,'g','g',''));
assert.throws(()=>Draft.move(moved,'e','g',''));
assert.throws(()=>Draft.move(draft,'missing','',''));
assert.throws(()=>Draft.move(draft,'a','g','s'));
assert.strictEqual(Draft.move(draft,'a','','a'),draft);
const full=Draft.start({token:'t',entries:[{id:'g',kind:'submenu',items:Array.from({length:200},(_,i)=>({id:'x'+i,kind:'command'}))},{id:'a',kind:'command'}]});
assert.throws(()=>Draft.move(full,'a','g',''));
let nested={id:'leaf',kind:'command'};
for(let i=7;i>=0;i--)nested={id:'deep'+i,kind:'submenu',items:[nested]};
const deep=Draft.start({token:'t',entries:[nested,{id:'extra',kind:'submenu',items:[]}]});
assert.throws(()=>Draft.move(deep,'extra','deep7',''));
const visible=[{kind:'separator'},{kind:'command',enabled:false},{kind:'submenu'},{kind:'command'}];
assert.equal(Draft.nextIndex(visible,-1,1,false),2);
assert.equal(Draft.nextIndex(visible,2,-1,false),3);
assert.equal(Draft.nextIndex(visible,-1,1,true),0);
assert.equal(Draft.nextIndex([{kind:'separator'}],-1,1,false),-1);
let requests=[],fetches=0;
const root={layoutDraft:null,layoutBusy:false,layoutExpired:false,layoutEpoch:0,menuFetchEpoch:0,
 layoutStatus:'',menuStatus:'',expanded:true,
 send(service,path,iface,method,args,done){requests.push({method,args,done})},fetchMenu(){fetches++}};
assert.equal(root.layoutDraft,null); // locked default
LayoutController.begin(root); assert.equal(root.layoutBusy,true);
assert.equal(requests[0].method,'BeginLayoutEdit');
requests.shift().done(true,JSON.stringify({ok:true,token:'t1',entries}));
root.layoutDraft=Draft.move(root.layoutDraft,'a','g','');
const originalDraft=root.layoutDraft;
root.expanded=false; root.expanded=true;
assert.strictEqual(root.layoutDraft,originalDraft); // popup dismissal is not cancellation
LayoutController.toggle(root); assert.strictEqual(root.layoutDraft,originalDraft);
assert.match(root.layoutStatus,/Save layout or Cancel/);
LayoutController.save(root);
const save=requests.shift(); assert.equal(save.method,'SaveLayoutEdit');
assert.deepEqual(Object.keys(JSON.parse(save.args[1])[0]),['id','items']);
LayoutController.cancel(root); assert.strictEqual(root.layoutDraft,originalDraft); // save in flight
save.done(true,JSON.stringify({ok:false,code:'conflict',message:'changed elsewhere'}));
assert.strictEqual(root.layoutDraft,originalDraft); assert.equal(root.layoutBusy,false);
LayoutController.keep(root); requests.shift().done(false,'unavailable');
assert.strictEqual(root.layoutDraft,originalDraft); assert.match(root.layoutStatus,/Backend unavailable/);
LayoutController.save(root); requests.shift().done(true,JSON.stringify({ok:true}));
assert.equal(root.layoutDraft,null); assert.equal(fetches,1);
LayoutController.begin(root); requests.shift().done(true,JSON.stringify({ok:true,token:'t2',entries}));
LayoutController.keep(root); const late=requests.shift();
LayoutController.cancel(root); assert.equal(root.layoutDraft,null);
assert.equal(requests.shift().method,'CancelLayoutEdit');
LayoutController.begin(root); requests.shift().done(true,JSON.stringify({ok:true,token:'t3',entries}));
late.done(true,JSON.stringify({ok:false,code:'expired',message:'old session'}));
assert.equal(root.layoutDraft.token,'t3'); assert.equal(root.layoutExpired,false);
LayoutController.keep(root); requests.shift().done(true,JSON.stringify({ok:false,code:'expired',message:'restarted'}));
assert.equal(root.layoutExpired,true); assert.equal(root.layoutDraft.token,'t3');
LayoutController.save(root); assert.equal(requests.length,0);
LayoutController.cancel(root); requests.shift();
LayoutController.begin(root); requests.shift().done(false,'');
assert.equal(root.layoutDraft,null); assert.equal(root.layoutBusy,false);
assert.match(root.menuStatus,/bash install.sh/);
for(let i=0;i<5;i++){
 LayoutController.begin(root); requests.shift().done(true,JSON.stringify({ok:true,token:'cycle'+i,entries}));
 LayoutController.cancel(root); requests.shift();
 assert.equal(root.layoutDraft,null);
}
'''
    code += '\n' + function((UI / 'main.qml').read_text(), 'launchItem') + r'''
let layoutEditing=true,layoutBusy=false,launchPending=false,menuSwitchEpoch=0,commandError='',expanded=true;
function send(...args){root.send(...args)}
launchItem('0'); assert.equal(requests.length,0);
layoutEditing=false;layoutBusy=true;launchItem('0');assert.equal(requests.length,0);
layoutBusy=false;launchItem('0');assert.equal(requests[0].method,'Run');
requests.shift().done(true,false);assert.equal(expanded,true);assert.match(commandError,/Could not start/);
launchItem('0');requests.shift().done(true,true);assert.equal(expanded,false);
expanded=true;launchItem('0');menuSwitchEpoch++;requests.shift().done(true,true);
assert.equal(expanded,true); // stale launch callback cannot close a newer popup
'''
    result = subprocess.run(['node', '-e', code], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_locked_popup_and_flyout_keyboard_handlers():
    if not shutil.which('node'):
        pytest.skip('Node is required for QML JavaScript tests')
    main = (UI / 'main.qml').read_text()
    side = (UI / 'SideFlyout.qml').read_text()
    handlers = ''
    for name, source in [('mainKeys', main), ('sideKeys', side)]:
        start = source.rindex('Keys.onPressed: event =>')
        handlers += f'function {name}(event) ' + braced(source, source.index('{', start)) + '\n'
    code = 'const assert=require("node:assert/strict");\n'
    code += library('LayoutDraft', 'nextIndex') + handlers + r'''
const Qt=Object.fromEntries(['Up','Down','Right','Left','Return','Enter','Escape'].map(k=>['Key_'+k,k]));
let opens=0,launches=[],returned=0,childClosed=0,childFocused=0;
let activeIndex=-1;
const entries=[{kind:'separator'},{kind:'command',enabled:false,key:'disabled'},
 {kind:'submenu',key:'group'},{kind:'command',key:'command'}];
const rows=entries.map((entry,i)=>({entry,y:i*28,height:28,
 openChild(){opens++},childPopup:{focusFirst(){childFocused++}}}));
const root={visibleEntries:entries,layoutEditing:false,layoutBusy:false,launchPending:false,
 launchItem(key){launches.push(key)}};
const flyout={entries,activeIndex:-1,visible:true,focusFirst(){childFocused++},
 closeChild(){childClosed++},returnToParent(){returned++},triggered(key){launches.push(key)}};
const normalRows={itemAt(i){return rows[i]}},flyoutRows=normalRows;
const menuScroll={contentItem:{contentY:0},availableHeight:55},viewport=menuScroll;
function showFlyout(){opens++}
function key(handler,key){const e={key,accepted:false};handler(e);return e}
key(mainKeys,'Down');assert.equal(activeIndex,2);assert.equal(flyout.visible,false);
assert.equal(menuScroll.contentItem.contentY,29);
key(mainKeys,'Right');assert.equal(opens,1);assert.equal(childFocused,1);
key(mainKeys,'Down');assert.equal(activeIndex,3);
key(mainKeys,'Right');assert.equal(launches.length,0);
key(mainKeys,'Return');assert.deepEqual(launches,['command']);
key(mainKeys,'Down');assert.equal(activeIndex,2);
key(mainKeys,'Up');assert.equal(activeIndex,3);
root.layoutEditing=true;assert.equal(key(mainKeys,'Return').accepted,false);
root.layoutEditing=false;root.layoutBusy=true;key(mainKeys,'Return');
root.layoutBusy=false;root.launchPending=true;key(mainKeys,'Return');
assert.equal(launches.length,1);
key(sideKeys,'Down');assert.equal(flyout.activeIndex,2);assert.equal(childClosed,1);
key(sideKeys,'Right');assert.equal(opens,2);assert.equal(childFocused,2);
key(sideKeys,'Down');assert.equal(flyout.activeIndex,3);
key(sideKeys,'Enter');assert.deepEqual(launches,['command','command']);
flyout.visible=true;key(sideKeys,'Left');assert.equal(returned,1);assert.equal(flyout.visible,false);
flyout.visible=true;key(sideKeys,'Escape');assert.equal(returned,2);assert.equal(flyout.visible,false);
flyout.activeIndex=1;key(sideKeys,'Return');assert.equal(launches.length,2);
'''
    result = subprocess.run(['node', '-e', code], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_icon_preference_transport_defaults_and_recovery():
    if not shutil.which('node'):
        pytest.skip('Node is required')
    code = 'const assert=require("node:assert/strict");\n'
    code += function((UI / 'main.qml').read_text(), 'fetchIntegration')
    code += r'''
let launcherAppletId=0,hideOriginalLauncherRequested=false,buttonIconMode='',customButtonIcon='',menuAppearance='',showMenuIcons=true;
let response={},ok=true;
function send(service,path,iface,method,args,callback){callback(ok,JSON.stringify(response))}
function synchronizeLauncherVisibility(){}
function releaseMask(){}
fetchIntegration(); assert.equal(showMenuIcons,true);
response={show_menu_icons:false,button_icon:'custom',button_icon_mode:'custom'};
fetchIntegration();assert.equal(showMenuIcons,false);assert.equal(customButtonIcon,'custom');
ok=false;response={};fetchIntegration();assert.equal(showMenuIcons,false);
ok=true;fetchIntegration();assert.equal(showMenuIcons,true);
response={show_menu_icons:true};fetchIntegration();assert.equal(showMenuIcons,true);
'''
    result = subprocess.run(['node', '-e', code], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
