"""v0.4.16: avoid native popup focus races and observe generic launcher flicker.

Node executes the shipped QML JS functions and Timer.onTriggered handler. It
cannot emulate KWin/Wayland focus events; validate the final handoff locally.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT/'plasmoid/contents/ui/main.qml'


def braced(source, brace):
    level = 0
    for i in range(brace, len(source)):
        if source[i] == '{':
            level += 1
        elif source[i] == '}':
            level -= 1
            if level == 0:
                return source[brace:i+1]
    raise ValueError('unterminated QML block')


def function(source, name):
    start = source.index('    function '+name+'(')
    return source[start:source.index('{', start)] + braced(source, source.index('{', start))


def timer_handler(source, timer):
    start = source.index('id: '+timer)
    trigger = source.index('onTriggered: {', start)
    return 'function settleTick() '+braced(source,source.index('{',trigger))


class PopupHandoffPolicy(unittest.TestCase):
    def test_timing_and_flicker_probe_are_scoped(self):
        q = MAIN.read_text()
        self.assertIn('interval: 140',q)
        self.assertIn('const wasPowerPopupOpen = expanded === true;', function(q,'activateLauncher'))
        self.assertIn('launcherActivationSettle.restart();',function(q,'activateLauncher'))
        self.assertIn('launcherActivationSettle.stop();',function(q,'openMenu'))
        handler=timer_handler(q, 'launcherActivationSettle')
        self.assertIn('LauncherAdapters.originalIsOpen(',handler)
        self.assertIn('epoch !== root.menuSwitchEpoch',handler)
        self.assertIn('root.activateSelectedLauncher(epoch);',handler)
        self.assertIn('launcher visibility:', function(q,'logLauncherVisibility'))
        self.assertIn('original launcher status changed',q)
        self.assertIn('original panel container became visible',q)
        self.assertIn('original applet item became visible',q)
        self.assertIn('root.logLauncherVisibility("original launcher expanded changed");',q)
        # The generic flicker probe is read-only. Never fix cosmetic issues by
        # overriding KDE's AppletContainer.visible or item.visible bindings.
        for meth in ('logLauncherVisibility','activateLauncher','openMenu'):
            text=function(q,meth)
            self.assertIsNone(re.search(r'\.visible\s*=(?!=)',text))
            self.assertIsNone(re.search(r'\.status\s*=(?!=)',text))

    @unittest.skipUnless(shutil.which('node'),'Node required for QML-JS mock')
    def test_handoff_waits_cancels_stale_and_avoids_second_toggle(self):
        q=MAIN.read_text()
        code='\n'.join((function(q,'activateLauncher'),
                        function(q,'openMenu'), timer_handler(q,'launcherActivationSettle')))
        js=r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const cbs=[],messages=[],events=[];
const launcher={expanded:false};
const applet={activated(){events.push('activated');launcher.expanded=!launcher.expanded}};
const root={expanded:false,menuSwitchEpoch:0,requestedMenu:'none',pendingPowerEpoch:-1,
  pendingLauncherEpoch:-1,awaitingAsyncClose:false,launcherSwitchError:'',
  selectedLauncherPlan:{item:launcher,applet},selectedLauncherItem:launcher};
const poll={running:false,start(){this.running=true},stop(){this.running=false}};
const follow={stop(){}};
const settle={running:false,restart(){this.running=true},stop(){this.running=false}};
Object.assign(root,{activateSelectedLauncher(epoch){
  if(epoch===this.menuSwitchEpoch&&this.requestedMenu==='launcher') applet.activated();},
  closeLauncherPopup(){return {ok:true}},fetchMenu(){}});
const c={root,Qt:{callLater(f){cbs.push(f)}},
  launcherClosePoll:poll,launcherCloseFollowup:follow,launcherActivationSettle:settle,
  LauncherAdapters:{originalIsOpen(item){return item&&item.expanded===true}},
  console:{info(...args){messages.push(args.join(' '))}},
  fetchIntegration(){},closeLauncherPopup(){return root.closeLauncherPopup()}};
for(const key of ['expanded','menuSwitchEpoch','requestedMenu','pendingPowerEpoch',
                  'pendingLauncherEpoch','awaitingAsyncClose','launcherSwitchError',
                  'launcherClosePollCount']) Object.defineProperty(c,key,{
  configurable:true,get(){return root[key]},set(v){root[key]=v}});
vm.createContext(c);vm.runInContext(process.env.QML_FUNCS,c);
// Ordinary left-click stays on the one-turn path.
c.activateLauncher();assert.equal(settle.running,false);assert.equal(cbs.length,1);
cbs.shift()();assert.equal(events.length,1);launcher.expanded=false;
// Right-click popup is visible. Switching to launcher must not activate
// before the old window has settled.
root.expanded=true;root.requestedMenu='power';
c.activateLauncher();assert.equal(root.expanded,false);assert.equal(settle.running,true);
assert.equal(events.length,1);assert.equal(root.pendingLauncherEpoch,root.menuSwitchEpoch);
c.settleTick();assert.equal(events.length,2);assert.equal(launcher.expanded,true);
// If Meta opened the launcher before the settle timer, do not toggle shut.
root.expanded=true;root.requestedMenu='power';launcher.expanded=false;
c.activateLauncher(); launcher.expanded=true;
c.settleTick();assert.equal(events.length,2);assert.equal(launcher.expanded,true);
// A later right-click cancels the pending delayed activation.
root.expanded=true;root.requestedMenu='power';launcher.expanded=false;
c.activateLauncher();const oldEpoch=root.pendingLauncherEpoch;
c.openMenu();assert.equal(settle.running,false);assert.equal(root.pendingLauncherEpoch,-1);
assert.notEqual(root.menuSwitchEpoch,oldEpoch);
c.settleTick();assert.equal(events.length,2);
// Repeated/duplicate timer callbacks cannot fire twice.
root.expanded=true;root.requestedMenu='power';c.activateLauncher();
c.settleTick();c.settleTick();assert.equal(events.length,3);
assert.equal(root.pendingLauncherEpoch,-1);
'''
        r=subprocess.run(['node','-e',js],env={**os.environ,'QML_FUNCS':code},
                         capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_appgrid_bridge_matches_last_release(self):
        previous=Path('/mnt/data/OpenPowerMenu-RightClick-v0.4.15')
        if not previous.is_dir(): self.skipTest('baseline tree unavailable')
        paths=('plasmoid/contents/ui/adapters/AppGridLauncher.js',
               'plasmoid/contents/ui/adapters/AppGridPanelBridge.qml',
               'plasmoid/contents/ui/adapters/AppGridPanelGeometry.js',
               'plasmoid/contents/ui/adapters/LauncherAdapters.js',
               'plasmoid/contents/ui/adapters/PlasmaLauncher.js',
               'plasmoid/contents/ui/LauncherVisibility.js',
               )
        for name in paths:
            self.assertEqual((ROOT/name).read_bytes(),(previous/name).read_bytes(),name)


if __name__=='__main__': unittest.main()
