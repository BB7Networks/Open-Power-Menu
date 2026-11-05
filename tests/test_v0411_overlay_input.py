"""v0.4.11: regression coverage for AppGrid 1.9.6 full-screen input capture.

Node tests execute the actual helper and source-extracted QML functions with
mocked QWindow/AppGrid objects; live Wayland event routing is not emulated.
"""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

BASE = Path(__file__).resolve().parents[1]
HELPER = BASE / 'plasmoid/contents/ui/adapters/AppGridPanelGeometry.js'
QML = BASE / 'plasmoid/contents/ui/adapters/AppGridPanelBridge.qml'
MAIN = BASE / 'plasmoid/contents/ui/main.qml'


def grab(src, name):
    start = src.index('    function ' + name + '(')
    brace = src.index('{', start)
    depth = 0
    for i in range(brace, len(src)):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError(name)


@unittest.skipUnless(shutil.which('node'), 'Node required')
class OverlayMaskTests(unittest.TestCase):
    def run_node(self, script, include_qml=False):
        env = dict(os.environ)
        env['JS'] = HELPER.read_text().replace('.pragma library\n', '', 1)
        if include_qml:
            src = QML.read_text()
            env['QML'] = ('\n'.join([
                grab(src, 'applyAppGridPassThrough'),
                grab(src, 'restoreAppGridPassThrough'),
            ]))
        p = subprocess.run(['node', '-e', script], env=env, capture_output=True, text=True, timeout=12)
        self.assertEqual(p.returncode, 0, p.stderr + '\n' + p.stdout)

    def test_pass_through_geometry_on_all_panel_edges(self):
        self.run_node(r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const o={};vm.createContext(o);vm.runInContext(process.env.JS,o);
const panel={x:500,y:200,w:800,h:600};
const b=o.inputRect(1920,1080,'bottom',48,panel);
assert.equal(b.x,0);assert.equal(b.y,0);assert.equal(b.w,1920);
assert.equal(b.h,1024);assert.equal(b.cut,56);
const t=o.inputRect(1920,1080,'top',48,panel);
assert.equal(t.y,56);assert.equal(t.h,1024);
const l=o.inputRect(1920,1080,'left',55,panel);
assert.equal(l.x,63);assert.equal(l.w,1857);
const r=o.inputRect(1920,1080,'right',55,panel);
assert.equal(r.w,1857);assert.equal(r.x,0);
''')

    def test_refuse_when_interactive_content_or_geometry_unsafe(self):
        self.run_node(r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const o={};vm.createContext(o);vm.runInContext(process.env.JS,o);
assert.equal(o.inputRect(1920,1080,'bottom',48,{x:650,y:900,w:500,h:160}),null);
assert.equal(o.inputRect(1920,1080,'top',48,{x:100,y:30,w:500,h:500}),null);
assert.equal(o.inputRect(1920,1080,'left',48,{x:24,y:300,w:500,h:200}),null);
assert.equal(o.inputRect(1920,1080,'right',48,{x:1650,y:300,w:200,h:200})!==null,true);
assert.equal(o.inputRect(1920,1080,'bottom',200),null);
assert.equal(o.inputRect(300,1080,'bottom',48),null);
assert.equal(o.inputRect(1920,1080,'diagonal',48),null);
''')

    def test_applies_only_to_selected_hidden_appgrid_and_restores(self):
        self.run_node(r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const o={};vm.createContext(o);vm.runInContext(process.env.JS,o);
const types={BottomEdge:10,TopEdge:11,LeftEdge:12,RightEdge:13};
const w={width:1920,height:1080,visible:true,screen:{name:'DP-1'},panelRect:{x:580,y:170,w:760,h:690}};
const calls=[];
const applet={id:59,pluginName:'dev.xarbit.appgrid',setInputRect:(...args)=>calls.push(args)};
const item={gridOpen:true,gridWindow:w,isDragInFlight:false};
const c={PanelGeometry:o,PlasmaCore:{Types:types},
    AppGridLauncher:{trace(){},supportsPanelPassThrough(plan){return plan?.applet?.pluginName==='dev.xarbit.appgrid' && plan.item.gridOpen===true}},
    panelWindow:{height:56,width:1920,screen:{name:'DP-1'}},
    panelLocation:10,compactButtonHeight:40,selectedLauncherPlan:{applet,item},
    active:true,passThroughWindow:null,passThroughApplet:null,passThroughSignature:'',console};
vm.createContext(c);vm.runInContext(process.env.QML,c);
assert.equal(c.applyAppGridPassThrough(),true);
assert.equal(calls.length,1); assert.deepEqual(calls[0],[w,0,0,1920,1016]);
assert.equal(c.applyAppGridPassThrough(),true);assert.equal(calls.length,1);
// A drag owns the input mask until its end.
item.isDragInFlight=true;
assert.equal(c.applyAppGridPassThrough(),false);assert.equal(calls.length,1);
item.isDragInFlight=false;
c.restoreAppGridPassThrough();
assert.equal(calls.length,2);assert.deepEqual(calls[1],[w,0,0,0,0]);
assert.equal(c.passThroughWindow,null);
c.active=false;
assert.equal(c.applyAppGridPassThrough(),false);assert.equal(calls.length,2);
c.active=true;
c.selectedLauncherPlan={applet:{id:61,pluginName:'org.kde.plasma.kickoff',setInputRect() { throw Error('must not call'); }},item};
assert.equal(c.applyAppGridPassThrough(),false);assert.equal(calls.length,2);
''',include_qml=True)

    def test_cross_monitor_refusal(self):
        self.run_node(r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const o={};vm.createContext(o);vm.runInContext(process.env.JS,o);
let calls=0;
const win={width:1920,height:1080,visible:true,screen:{name:'HDMI-2'}};
const c={PanelGeometry:o,PlasmaCore:{Types:{BottomEdge:1}},
  AppGridLauncher:{supportsPanelPassThrough(plan){return plan.item.gridOpen===true}},
  panelWindow:{height:50,screen:{name:'DP-1'}},panelLocation:1,compactButtonHeight:42,
  selectedLauncherPlan:{applet:{pluginName:'dev.xarbit.appgrid',setInputRect(){calls++;}},item:{gridOpen:true,gridWindow:win}},
  active:true,passThroughWindow:null,passThroughApplet:null,passThroughSignature:'',console};
vm.createContext(c);vm.runInContext(process.env.QML,c);
assert.equal(c.applyAppGridPassThrough(),false);assert.equal(calls,0);
''',include_qml=True)

    def test_dismissal_has_explicit_delivery_trace_and_not_passively_killed(self):
        q=QML.read_text()
        self.assertIn('right-click received by launcher button', MAIN.read_text())
        self.assertIn('AppGrid panel input pass-through applied:',q)
        self.assertIn('function onGridOpenChanged()',q)
        self.assertIn('appGridPassThroughRetry.restart()',q)
        self.assertIn('function onIsDragInFlightChanged()',q)
        self.assertIn('restoreAppGridPassThrough();',q)
        self.assertIn('owner.setInputRect(win, 0, 0, 0, 0)',q)
        self.assertIn('value: root.hiddenStatusForRevision(root.launcherMaskRevision)',MAIN.read_text())
        self.assertNotIn('plan.applet.kill(',q)

if __name__=='__main__':
    unittest.main()
