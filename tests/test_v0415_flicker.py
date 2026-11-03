"""v0.4.15: same-tick hide reassertion and stable cached launcher selection.

The portable QML-JS mock is not an actual Qt/Plasma rendering test.
"""
from pathlib import Path
import os
import re
import subprocess
import shutil
import unittest

HERE=Path(__file__).resolve().parents[1]
MAIN=HERE/'plasmoid/contents/ui/main.qml'


def extract_function(text, name):
    start=text.index('    function '+name+'(')
    brace=text.index('{', start)
    depth=0
    for idx in range(brace,len(text)):
        if text[idx]=='{': depth+=1
        elif text[idx]=='}':
            depth-=1
            if depth==0: return text[start:idx+1]
    raise AssertionError('unclosed QML function '+name)


class FlickerPolicy(unittest.TestCase):
    def test_same_turn_repair_with_no_direct_panel_visibility_override(self):
        src=MAIN.read_text()
        code=extract_function(src,'repairLauncherMask')
        self.assertIn('launcherMaskRepairInProgress = true;', code)
        self.assertIn('launcherMaskRevision += 1;', code)
        self.assertLess(code.index('launcherMaskRevision += 1;'),code.index('Qt.callLater('))
        self.assertIn('launcherMaskRepairInProgress = false;',code)
        self.assertIn('restoreMode: Binding.RestoreBindingOrValue',src)
        self.assertIn('value: root.hiddenStatusForRevision(root.launcherMaskRevision)',src)
        self.assertNotRegex(code, r'\b(?:applet|item|container|target)\.visible\s*=')
        self.assertNotRegex(code, r'\b(?:applet|item|container|target)\.status\s*=(?!=)')
        self.assertIn('LauncherVisibility.findOriginal(',extract_function(src,'synchronizeLauncherVisibility'))

    @unittest.skipUnless(shutil.which('node'),'node not installed')
    def test_immediate_repair_nested_event_and_cached_selection(self):
        code='\n'.join(extract_function(MAIN.read_text(),f) for f in
                       ('repairLauncherMask','synchronizeLauncherVisibility'))
        js=r'''
const assert=require('node:assert/strict');
const vm=require('node:vm');
const src=process.env.FUNCTIONS;
function create(initial, nested=false) {
    const launcher={id:59,pluginName:'org.kde.plasma.kickoff',status:initial};
    const plan={applet:launcher,item:{visible:false},container:{visible:false}};
    const callbacks=[];let walked=0, looked=0, releases=0, budget=0;
    const ctx={
      launcherAppletId:59, maskActive:true, maskedLauncher:launcher,
      selectedLauncherPlan:plan,maskPlan:plan,
      hideOriginalLauncherRequested:true,launcherMaskRevision:0,
      launcherMaskRepairInProgress:false,launcherMaskRepairScheduled:false,
      launcherMaskRepairAttempts:0,launcherMaskIdentity:0,launcherMaskError:'',
      Plasmoid:{containment:{applets:[launcher],id:2},id:777},
      PlasmaCore:{Types:{HiddenStatus:6}},
      LauncherVisibility:{findOriginal(){looked++;return launcher},
                            prepare(){walked++;return plan}},
      Qt:{callLater(f){callbacks.push(f)}},
      maskRepairBudget:{restart(){budget++}},
      maskVerification:{restart(){}},
      console:{warn(){},info(){}},
      releaseMask(){releases++},
    };
    ctx.root=ctx;
    let revision=0;
    Object.defineProperty(ctx,'launcherMaskRevision', {
      get(){return revision},
      set(v){
        revision=v;
        if(nested) ctx.repairLauncherMask(); // nested statusChanged in binding evaluation
        launcher.status=6; // QML Binding writes HiddenStatus in the same turn
      }
    });
    vm.createContext(ctx);vm.runInContext(src,ctx);
    return {ctx,launcher,plan,callbacks,stats(){return {looked,walked,releases,budget}}};
}
// An external status write is repaired without scheduling a deferred turn.
{
  const {ctx,launcher,callbacks}=create(2);
  ctx.repairLauncherMask();
  assert.equal(launcher.status,6);
  assert.equal(ctx.launcherMaskRevision,1);
  assert.equal(ctx.launcherMaskRepairAttempts,1);
  assert.equal(callbacks.length,0);
}
// QML can emit statusChanged *inside* Binding.value evaluation; never recurse.
{
  const {ctx,launcher,callbacks}=create(2,true);
  ctx.repairLauncherMask();
  assert.equal(launcher.status,6);
  assert.equal(ctx.launcherMaskRevision,1);
  assert.equal(ctx.launcherMaskRepairAttempts,1);
  assert.equal(callbacks.length,0);
}
// Repeated integration polls should validate the selected applet only,
// not rebuild the entire scene graph / container during popup activation.
{
  const {ctx,plan,callbacks,stats}=create(6);
  for(let i=0;i<10;i++) ctx.synchronizeLauncherVisibility();
  assert.equal(ctx.maskActive,true);
  assert.equal(ctx.maskPlan,plan);
  assert.equal(stats().looked,10);
  assert.equal(stats().walked,0);
  assert.equal(stats().releases,0);
  assert.equal(callbacks.length,0);
}
// A changed launcher selection must not use the cached path.
{
  const {ctx,launcher,stats}=create(6);
  ctx.LauncherVisibility.findOriginal=()=>({id:60});
  ctx.LauncherVisibility.prepare=()=>({applet:launcher,item:{visible:false},container:{visible:false}});
  ctx.synchronizeLauncherVisibility();
  assert.equal(ctx.maskActive,true);
  assert.equal(ctx.maskedLauncher,launcher);
}
'''
        result=subprocess.run(['node','-e',js],
            env={**os.environ,'FUNCTIONS':code},capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_appgrid_adapters_are_untouched(self):
        prior=Path('/mnt/data/OpenPowerMenu-RightClick-v0.4.14')
        if not prior.is_dir(): self.skipTest('prior release unavailable')
        for rel in ('plasmoid/contents/ui/adapters/AppGridLauncher.js',
                    'plasmoid/contents/ui/adapters/AppGridPanelBridge.qml',
                    'plasmoid/contents/ui/adapters/AppGridPanelGeometry.js',
                    'plasmoid/contents/ui/adapters/LauncherAdapters.js',
                    'plasmoid/contents/ui/adapters/PlasmaLauncher.js',
                    'plasmoid/contents/ui/LauncherVisibility.js',
                    'plasmoid/contents/ui/SideFlyout.qml',
                    ):
            self.assertEqual((HERE/rel).read_bytes(),(prior/rel).read_bytes(),rel)

if __name__=='__main__': unittest.main()
