"""0.4.14: generic Plasma launcher's hidden button must not reappear during popup transitions.

These are executable policy tests against functions extracted from the shipped
QML. Node mocks lifecycle events but does not emulate a live QML binding or KDE.
"""
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import unittest

MAIN = Path(__file__).resolve().parents[1]/'plasmoid/contents/ui/main.qml'


def extract_function(source, name):
    start = source.index('    function ' + name + '(')
    brace = source.index('{', start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
            if depth == 0:
                return source[start:i+1]
    raise AssertionError('unclosed function ' + name)


class GenericPlasmaMaskRegression(unittest.TestCase):
    def test_status_guard_keeps_reversible_binding(self):
        src = MAIN.read_text()
        self.assertIn('value: root.hiddenStatusForRevision(root.launcherMaskRevision)', src)
        self.assertIn('return PlasmaCore.Types.HiddenStatus;', extract_function(src, 'hiddenStatusForRevision'))
        self.assertIn('when: root.maskActive && root.maskedLauncher !== null', src)
        self.assertIn('restoreMode: Binding.RestoreBindingOrValue', src)
        self.assertIn('root.logLauncherVisibility("original launcher status changed");', src)
        self.assertRegex(src, r'onStatusChanged\(\)\s*\{[\s\S]*?root\.repairLauncherMask\(\);')
        # Never bypass Plasma's normal widget visibility/layout management.
        for method in ('repairLauncherMask', 'synchronizeLauncherVisibility'):
            body = extract_function(src, method)
            self.assertIsNone(re.search(
                r'\b(?:target|applet|container|item)\.(?:status|visible)\s*=(?!=)',
                body))
        self.assertIn('launcherMaskRevision += 1;', extract_function(src, 'repairLauncherMask'))

    @unittest.skipUnless(shutil.which('node'), 'node is required')
    def test_open_transition_does_not_unmask_same_launcher(self):
        functions = '\n'.join(extract_function(MAIN.read_text(), n) for n in
                              ('repairLauncherMask', 'synchronizeLauncherVisibility'))
        script = r'''
const assert=require('node:assert/strict'), vm=require('node:vm');
const code=process.env.QML_FUNCTIONS;
function make(status, deferred=false) {
    const launcher={id:42, status, pluginName:'org.kde.plasma.kickoff'};
    const plan={applet:launcher,item:{visible:true},container:{visible:true}};
    const callbacks=[];
    const ctx={
      maskActive:true, hideOriginalLauncherRequested:true,
      maskedLauncher:launcher, maskPlan:plan, selectedLauncherPlan:plan,
      launcherMaskError:'',launcherAppletId:42,
      launcherMaskIdentity:0,launcherMaskRepairInProgress:false,
      launcherMaskRepairScheduled:false,launcherMaskRepairAttempts:0,
      Plasmoid:{containment:{applets:[launcher], id:2},id:100},
      PlasmaCore:{Types:{HiddenStatus:6}},
      LauncherVisibility:{findOriginal(){return launcher},prepare(){return plan},didHide(){return false}},
      Qt:{callLater(fn){callbacks.push(fn)}},
      maskRepairBudget:{restart(){}},
      maskVerification:{restart(){}},
      console:{info(){},warn(){}},
      releaseMask(){throw Error('mask released during popup transition')}
    };
    ctx.root=ctx;
    // Emulate QML Binding evaluation when the revision dependency changes.
    let revision=0;
    Object.defineProperty(ctx,'launcherMaskRevision',{
        get(){return revision},
        set(value){revision=value; if(!deferred) launcher.status=6}
    });
    vm.createContext(ctx);
    vm.runInContext(code,ctx);
    return {ctx,launcher,plan,callbacks};
}
// Popup transition may leave representation reported as visible even while
// the applet's HiddenStatus still holds. Periodic refresh must not unmask it.
{
 const {ctx,launcher,plan}=make(6);
 ctx.synchronizeLauncherVisibility();
 assert.equal(ctx.maskActive,true);assert.equal(ctx.maskPlan,plan);
 assert.equal(ctx.maskedLauncher,launcher);
 assert.equal(ctx.launcherMaskRevision,0);
}
// Native launcher transiently replaces the hidden status during opening.
// Reassert the Binding on the *same* target, not release it.
{
 const {ctx,launcher,callbacks}=make(2);
 ctx.synchronizeLauncherVisibility();
 assert.equal(ctx.maskActive,true);
 assert.equal(callbacks.length,0); // same event turn, not a frame later
 assert.equal(ctx.launcherMaskRevision,1);
 assert.equal(launcher.status,6);
 assert.equal(ctx.launcherMaskRepairAttempts,1);
}
// Closing/unhiding or changing the selected widget invalidates old retries.
{
 const {ctx,callbacks}=make(2,true);
 ctx.repairLauncherMask();
 assert.equal(callbacks.length,1);
 assert.equal(ctx.launcherMaskRevision,1); // immediate first attempt
 ctx.launcherMaskIdentity++;
 ctx.maskActive=false;
 callbacks.shift()();
 assert.equal(ctx.launcherMaskRevision,1); // invalidated deferred retry
}
// If the launcher refuses to remain hidden, stop rather than spin forever.
{
 const {ctx}=make(2);
 let restores=0;
 ctx.releaseMask=()=>{restores++};
 ctx.launcherMaskRepairAttempts=20;
 ctx.repairLauncherMask();
 assert.equal(restores,1);
 assert.equal(ctx.launcherMaskRevision,0);
}
'''
        result = subprocess.run(['node','-e',script],
                    env={**os.environ, 'QML_FUNCTIONS':functions},
                    text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_known_good_adapters_are_untouched(self):
        old=Path('/mnt/data/OpenPowerMenu-RightClick-v0.4.13')
        if not old.is_dir():
            self.skipTest('previous release unavailable in test environment')
        root=MAIN.parents[3]
        for path in ('plasmoid/contents/ui/adapters/AppGridLauncher.js',
                     'plasmoid/contents/ui/adapters/AppGridPanelBridge.qml',
                     'plasmoid/contents/ui/adapters/AppGridPanelGeometry.js',
                     'plasmoid/contents/ui/adapters/LauncherAdapters.js',
                     'plasmoid/contents/ui/adapters/PlasmaLauncher.js',
                     'plasmoid/contents/ui/LauncherVisibility.js',
                     'plasmoid/contents/ui/SideFlyout.qml',
                     ):
            self.assertEqual((root/path).read_bytes(),(old/path).read_bytes(),path)


if __name__=='__main__': unittest.main()
