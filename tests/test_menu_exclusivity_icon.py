"""v0.4.7 cross-menu exclusivity and launcher icon selection checks.

The Node harness executes the real QML JavaScript method bodies with a fake
Plasma item and queued D-Bus requests. No actual Plasma shell is present here.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tests.qml_js_harness import bundle_adapter_js

from openpowermenu.core import DEFAULT_CONFIG, load_config, save_config

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / 'plasmoid/contents/ui/main.qml'
JS = ROOT / 'plasmoid/contents/ui/adapters/LauncherAdapters.js'


def extract_qml_function(text: str, name: str) -> str:
    """Extract a self-contained JS method from the real QML file."""
    start = text.index('    function ' + name + '() {')
    brace = text.index('{', start)
    depth = 0
    for pos in range(brace, len(text)):
        if text[pos] == '{':
            depth += 1
        elif text[pos] == '}':
            depth -= 1
            if depth == 0:
                return text[start:pos + 1]
    raise AssertionError(f'Unbalanced function: {name}')


class MutualExclusionAndIconTests(unittest.TestCase):
    def test_default_inherits_launcher_icon_and_keeps_existing_custom_widget_icon_as_fallback(self):
        self.assertEqual(DEFAULT_CONFIG['button_icon_mode'], 'launcher')
        self.assertEqual(DEFAULT_CONFIG['button_icon'], '')
        with tempfile.TemporaryDirectory() as folder:
            old = deepcopy(DEFAULT_CONFIG)
            del old['button_icon_mode']
            del old['button_icon']
            old['launcher_applet_id'] = 59
            old['hide_original_launcher'] = True
            old['menu'].append({'label':'Personal', 'command':['true']})
            file = Path(folder) / 'menu.json'
            original = json.dumps(old).encode('utf-8')
            file.write_bytes(original)
            loaded = load_config(file)
            self.assertEqual(loaded['button_icon_mode'], 'launcher')
            self.assertEqual(loaded['launcher_applet_id'], 59)
            self.assertEqual(loaded['menu'], old['menu'])
            # A version upgrade cannot overwrite a personal menu.
            self.assertEqual(file.read_bytes(), original)

    def test_icon_options_are_validated_and_bad_icon_cannot_overwrite_menu(self):
        cfg = deepcopy(DEFAULT_CONFIG)
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'menu.json'
            save_config(cfg, file)
            before = file.read_bytes()
            for mode, icon in [('html', 'start-here-kde'), ('custom','https://other.com/x.svg'),
                               ('custom','relative/path.png'), ('custom','file://otherhost/a.png'),
                               ('custom', 'abc\x00def'), ('custom', 10),
                               ('custom', 'x'*600)]:
                wrong = dict(cfg, button_icon_mode=mode, button_icon=icon)
                with self.subTest(mode=mode, icon=str(icon)[:20]):
                    with self.assertRaises(ValueError):
                        save_config(wrong, file)
                    self.assertEqual(file.read_bytes(), before)
            for icon in ('start-here-kde', 'system-search',
                         'file:///home/demo/My%20Icons/Start.svg',
                         '/home/demo/icon.png'):
                with self.subTest(icon=icon):
                    save_config(dict(cfg, button_icon_mode='custom', button_icon=icon), file)
                    saved = load_config(file)
                    self.assertEqual(saved['button_icon'], icon)
                    self.assertEqual(saved['button_icon_mode'], 'custom')

    def test_service_transports_icon_and_editor_has_controls(self):
        s = (ROOT/'openpowermenu/service.py').read_text()
        self.assertIn('"button_icon_mode": cfg.get("button_icon_mode", "launcher")',s)
        self.assertIn('"button_icon": cfg.get("button_icon", "")',s)
        editor = (ROOT/'openpowermenu/editor.py').read_text()
        for phrase in ('Use original launcher icon', 'Custom icon',
                       'QFileDialog.getOpenFileName(', 'self.icon_mode',
                       'self.button_icon', 'self.cfg["button_icon_mode"]',
                       'self.cfg["button_icon"]'):
            self.assertIn(phrase, editor)
        self.assertNotIn('sh -c',editor)

    def test_qml_loads_icon_and_uses_writable_expanded_not_layout_hacks(self):
        q = QML.read_text()
        self.assertIn('Plasmoid.icon: root.effectiveButtonIcon', q)
        self.assertIn('LauncherAdapters.chooseIcon(', q)
        self.assertIn('LauncherAdapters.closeOriginal(plan.item, plan.applet,', q)
        self.assertIn('function onGridOpenChanged()', (ROOT/'plasmoid/contents/ui/adapters/AppGridPanelBridge.qml').read_text())
        self.assertIn('function onExpandedChanged()', q)
        self.assertIn('root.closeLauncherPopup(); // Right-click was the latest request.', q)
        self.assertIn('LauncherAdapters.originalIsVisiblyOpen(',q)
        self.assertIn('function finishOpeningPower(epoch)',q)
        self.assertIn('if (requestEpoch !== root.menuSwitchEpoch) return;',q)
        self.assertIn('dev.xarbit.appgrid.Standalone', (ROOT/'plasmoid/contents/ui/adapters/AppGridLauncher.js').read_text())
        self.assertIn('\"Hide\", []', (ROOT/'plasmoid/contents/ui/adapters/AppGridLauncher.js').read_text())
        self.assertIn('root.expanded = false; // Original launcher/Meta takes precedence.', q)
        self.assertIn('Qt.callLater(() => root.activateSelectedLauncher(epoch));', q)
        self.assertIn('applet.activated();', (ROOT/'plasmoid/contents/ui/adapters/PlasmaLauncher.js').read_text())
        self.assertIn('function activateSelectedLauncher(epoch)', q)
        self.assertIn('if (epoch !== root.menuSwitchEpoch', q)
        self.assertIn('value: root.hiddenStatusForRevision(root.launcherMaskRevision)', q)  # Preserve proven mechanism.
        self.assertNotIn('selectedLauncherItem.visible =',q)
        self.assertNotIn('selectedLauncherItem.opacity =',q)
        self.assertNotIn('plasma-org.kde.plasma.desktop-appletsrc',q)
        self.assertIn('flyout.positionAtRow(sourceRow, flyoutAnchor, sourceRow.menuScreen)',q)

    @unittest.skipUnless(shutil.which('node'), 'Node required for JS behavior tests')
    def test_js_closes_launcher_and_prefers_its_real_icon(self):
        s = bundle_adapter_js()
        test = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const c={}; vm.createContext(c);vm.runInContext(process.env.JS,c);
let applet={icon:'appgrid-theme-icon'};
assert.equal(c.chooseIcon(applet,'launcher','custom-a','fallback'),'appgrid-theme-icon');
assert.equal(c.chooseIcon(applet,'custom','custom-a','fallback'),'custom-a');
assert.equal(c.chooseIcon({icon:''},'launcher','custom-a','fallback'),'fallback');
assert.equal(c.chooseIcon(null,'launcher','','start-here-kde'),'start-here-kde');
const iconObject={isQIcon:true};
assert.equal(c.chooseIcon({icon:iconObject},'launcher','','fallback'),iconObject);
assert.equal(c.chooseIcon(null,'custom','','fallback'),'fallback');
const item={expanded:true,icon:'UNCHANGED',status:6};
assert.equal(c.closeExpanded(item),true);
assert.equal(item.expanded,false);
assert.equal(item.icon,'UNCHANGED'); assert.equal(item.status,6);
assert.equal(c.closeExpanded(item),true);
assert.equal(c.closeExpanded({}),false);
const impossible={get expanded(){return true},set expanded(x){throw Error('read only')}};
assert.equal(c.closeExpanded(impossible),false);
// Legacy centered AppGrid: its popup is *not* the Plasma expanded item.
const oldCenter={gridOpen:true,expanded:false,closed:0,closeWindow(){this.closed++;this.gridOpen=false}};
let hideRequests=0;
const hide=()=>hideRequests++;
assert.equal(c.closeOriginal(oldCenter,{pluginName:'dev.xarbit.appgrid'},hide).ok,true);
assert.equal(oldCenter.gridOpen,false);assert.equal(oldCenter.closed,1);
assert.equal(hideRequests,0);
assert.equal(c.closeOriginal(oldCenter,{pluginName:'dev.xarbit.appgrid'},hide).ok,true);
assert.equal(oldCenter.closed,2);assert.equal(hideRequests,0); // Idempotent local close; no irrelevant bus probe.
// External standalone AppGrid: no native popup or gridOpen, so use idempotent Hide.
const newCenter={expanded:false};
assert.equal(c.closeOriginal(newCenter,{pluginName:'dev.xarbit.appgrid'},hide).ok,true);
assert.equal(hideRequests,1);
// Other launcher is handled by writable expanded; no AppGrid-only call.
const kickoff={expanded:true};
assert.equal(c.closeOriginal(kickoff,{pluginName:'org.kde.plasma.kickoff'},hide).ok,true);
assert.equal(kickoff.expanded,false);assert.equal(hideRequests,1);
const panelAppgrid={expanded:true};
assert.equal(c.closeOriginal(panelAppgrid,{pluginName:'dev.xarbit.appgrid.panel'},hide).ok,true);
assert.equal(panelAppgrid.expanded,false);assert.equal(hideRequests,1);
assert.equal(c.originalIsOpen({gridOpen:true,closeWindow(){}},{pluginName:'dev.xarbit.appgrid'}),true);
assert.equal(c.originalIsOpen({gridOpen:false,closeWindow(){}},{pluginName:'dev.xarbit.appgrid'}),false);
assert.equal(c.originalIsOpen({expanded:true},null),true);
assert.equal(c.originalIsOpen({expanded:false},null),false);
assert.equal(c.originalIsOpen(null,null),false);

'''
        res = subprocess.run(['node','-e',test],env={**os.environ,'JS':s},
                             text=True,capture_output=True)
        self.assertEqual(res.returncode,0,res.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node required for window integration tests')
    def test_real_qml_closes_legacy_appgrid_window_and_observes_gridopen(self):
        q=QML.read_text()
        methods='\n'.join(extract_qml_function(q,n) for n in
                          ('closeLauncherPopup','onOriginalLauncherOpened'))
        helper=bundle_adapter_js()
        test=r'''
const assert=require('node:assert/strict');
const vm=require('node:vm');
const item={expanded:false,gridOpen:true,closed:0,closeWindow(){this.gridOpen=false;this.closed++}};
const applet={pluginName:'dev.xarbit.appgrid'};
const plan={item,applet};
const sends=[];
const timer={running:true};
const root={selectedLauncherPlan:plan,selectedLauncherItem:item,expanded:true,
  menuSwitchEpoch:2,requestedMenu:'power',
  send(...args){sends.push(args)},
  closeLauncherPopup(){return c.closeLauncherPopup()}};
const c={root,selectedLauncherPlan:plan,selectedLauncherItem:item,
  launcherCloseFollowup:timer,
  Plasmoid:{containment:null,id:1},
  LauncherVisibility:{prepare(){throw Error('unexpected')}},
  console,LauncherAdapters:{}};
Object.defineProperty(c,'selectedLauncherPlan',{get(){return root.selectedLauncherPlan},set(v){root.selectedLauncherPlan=v}});
vm.createContext(c);
const helpers={}; vm.createContext(helpers);
vm.runInContext(process.env.HELPERS,helpers);
c.LauncherAdapters=helpers;
vm.runInContext(process.env.QML_FUNCS,c);
assert.equal(c.closeLauncherPopup().ok,true);
assert.equal(item.closed,1);
assert.equal(item.gridOpen,false);
assert.equal(sends.length,0); // Older AppGrid has no daemon to call.
// AppGrid opens via Meta while Power menu is visible, during guard.
item.gridOpen=true;
c.onOriginalLauncherOpened();
assert.equal(item.closed,2);
assert.equal(root.expanded,true); // Latest right click wins.
// A later Meta key action outside guard wins and closes Power.
timer.running=false;
item.gridOpen=true;
c.onOriginalLauncherOpened();
assert.equal(root.expanded,false);
assert.equal(root.requestedMenu,'launcher');
assert.equal(root.menuSwitchEpoch,3);
// Future AppGrid 2.x uses the explicit non-toggling DBus Hide method.
root.selectedLauncherPlan={applet, item:{expanded:false}};
root.selectedLauncherItem=root.selectedLauncherPlan.item;
c.selectedLauncherItem=root.selectedLauncherItem;
assert.equal(c.closeLauncherPopup().ok,true);
assert.equal(sends.length,1);
assert.equal(sends[0][0],'org.freedesktop.DBus');
assert.equal(sends[0][3],'NameHasOwner');
assert.equal(sends[0][4][0],'dev.xarbit.appgrid');
sends[0][5](true,true); // An already-running daemon is present.
assert.equal(sends.length,2);
assert.equal(sends[1][0],'dev.xarbit.appgrid');
assert.equal(sends[1][1],'/Standalone');
assert.equal(sends[1][2],'dev.xarbit.appgrid.Standalone');
assert.equal(sends[1][3],'Hide');
assert.equal(sends[1][4].length,0);
sends[1][5](true,null);
'''
        r=subprocess.run(['node','-e',test],env={**os.environ,
                         'QML_FUNCS':methods, 'HELPERS':helper},
                         capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node required for QML JavaScript harness')
    def test_real_qml_switching_works_and_newer_click_cancels_pending_left(self):
        q=QML.read_text()
        code='\n'.join(extract_qml_function(q,n) for n in ('openMenu','activateLauncher'))
        test=r'''
const assert=require('node:assert/strict');
const vm=require('node:vm');
const events=[];
const callbacks=[];
const root={expanded:false,menuSwitchEpoch:0,requestedMenu:'none',
  pendingPowerEpoch:-1, pendingLauncherEpoch:-1,
  launcherSwitchError:'',awaitingAsyncClose:false,
  launcherClosePollCount:0};
const timer={running:false,start(){this.running=true;events.push('poll-start')},
  stop(){this.running=false;events.push('poll-stop')}};
const follow={restart(){events.push('follow-start')},stop(){events.push('follow-stop')}};
const settle={running:false,restart(){this.running=true;events.push('settle-start')},
  stop(){this.running=false;events.push('settle-stop')}};
Object.assign(root,{
  send(...args){events.push('send:'+args[3])},
  closeLauncherPopup(){events.push('close-original');return {ok:true,mode:'appgrid-native-close'}},
  fetchMenu(){events.push('fetch-menu')},
  activateSelectedLauncher(epoch){if(epoch===this.menuSwitchEpoch && this.requestedMenu==='launcher') events.push('activate-selected')}
});
const c={root,Qt:{callLater(fn){callbacks.push(fn)}},launcherCloseFollowup:follow,
  launcherClosePoll:timer,launcherActivationSettle:settle,
  fetchIntegration(){events.push('fetch-integration')},
  fetchMenu(){root.fetchMenu()},closeLauncherPopup(){return root.closeLauncherPopup()}};
for(const key of ['expanded','menuSwitchEpoch','requestedMenu','pendingPowerEpoch',
  'pendingLauncherEpoch','launcherSwitchError','awaitingAsyncClose','launcherClosePollCount'])
    Object.defineProperty(c,key,{configurable:true,get(){return root[key]},set(v){root[key]=v}});
vm.createContext(c);vm.runInContext(process.env.QML_FUNCS,c);
// A newer right click cancels the pending left-click's selected activation.
c.activateLauncher();
assert.equal(callbacks.length,1);
c.openMenu();
assert.equal(root.expanded,false);
assert.equal(root.requestedMenu,'power');
assert.equal(root.pendingPowerEpoch,root.menuSwitchEpoch);
assert.equal(timer.running,true);
callbacks.shift()();
assert.ok(!events.includes('activate-selected'));
assert.ok(events.includes('close-original'));
// A verified dismissal opens Power Menu (simulated handoff timer).
root.expanded=true;timer.stop();
// Left-click collapses Power first; a settle timer prevents native popup
// focus teardown from instantly closing the newly activated launcher.
c.activateLauncher();
assert.equal(root.expanded,false);
assert.equal(timer.running,false);
assert.equal(settle.running,true);
assert.equal(root.pendingLauncherEpoch,root.menuSwitchEpoch);
assert.equal(events.filter(x=>x==='activate-selected').length,0);
// Simulate the separate settle Timer (tested with real onTriggered below).
root.activateSelectedLauncher(root.pendingLauncherEpoch);
settle.stop(); root.pendingLauncherEpoch=-1;
assert.equal(events.filter(x=>x==='activate-selected').length,1);
// A second right-click while the first is waiting cancels that request.
c.openMenu();
assert.equal(timer.running,true);
c.openMenu();
assert.equal(timer.running,false);
assert.equal(root.requestedMenu,'none');
assert.equal(root.expanded,false);
assert.equal(root.pendingPowerEpoch,-1);
'''
        r=subprocess.run(['node','-e',test],env={**os.environ,'QML_FUNCS':code},
                         capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)


if __name__=='__main__':unittest.main()
