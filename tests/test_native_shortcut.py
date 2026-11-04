"""Native Plasma shortcut routes to the existing OPM popup, not a standalone app."""
from pathlib import Path
import os
import shutil
import subprocess
import pytest
from test_v0416_popup_handoff import function

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'plasmoid/contents/ui/main.qml'


def test_widget_activation_handler_and_native_configuration():
    qml = MAIN.read_text(encoding='utf-8')
    assert 'target: Plasmoid' in qml
    assert 'function onActivated() { root.activatePowerShortcut(); }' in qml
    handler = function(qml, 'activatePowerShortcut')
    assert 'root.openMenu()' in handler
    assert 'powerIsOpen' in handler
    assert 'expanded = false;' in handler
    assert 'property bool powerIsOpen: false' in qml
    assert 'root.powerIsOpen = false;' in qml
    assert 'powerIsOpen = true;' in function(qml, 'finishOpeningPower')
    assert 'Plasmoid.globalShortcut: "Meta+X"' not in qml  # Never force this on every reload.
    assert 'Plasmoid.globalShortcut = "Meta+X"' in qml
    assert 'opmDefaultShortcutTried' in (ROOT / 'plasmoid/contents/config/main.xml').read_text()
    assert 'setupMenuShortcut' not in (ROOT / 'openpowermenu/editor.py').read_text()


@pytest.mark.skipif(not shutil.which('node'), reason='Node required for native shortcut JS test')
def test_native_activation_after_plasma_eager_expand():
    qml = MAIN.read_text(encoding='utf-8')
    js = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const root={expanded:true,requestedMenu:'none',powerIsOpen:false,opens:0,
  openMenu(){this.opens++;this.expanded=!this.powerIsOpen;}};
const poll={running:false};
const ctx={root,launcherClosePoll:poll};
for(const key of ['expanded','requestedMenu','powerIsOpen'])
  Object.defineProperty(ctx,key,{get(){return root[key]},set(v){root[key]=v}});
vm.createContext(ctx);vm.runInContext(process.env.QML_FUNCTION,ctx);
ctx.activatePowerShortcut();
assert.equal(root.opens,1);
assert.equal(root.expanded,true);
// When the actual OPM popup is open, repeated Meta+X requests close it.
root.requestedMenu='power';root.powerIsOpen=true;root.expanded=true;
ctx.activatePowerShortcut();assert.equal(root.opens,2);
// A pending right-click handoff also toggles off rather than duplicating it.
root.requestedMenu='power';root.powerIsOpen=false;root.expanded=true;poll.running=true;
ctx.activatePowerShortcut();assert.equal(root.opens,3);
"""
    result = subprocess.run(['node','-e',js],
        env={**os.environ,'QML_FUNCTION':function(qml,'activatePowerShortcut')},
        text=True,capture_output=True,timeout=12)
    assert result.returncode == 0, result.stderr + result.stdout


@pytest.mark.skipif(not shutil.which('node'), reason='Node required for native shortcut JS test')
def test_default_shortcut_only_once_and_preserves_user_preference():
    qml = MAIN.read_text(encoding='utf-8')
    js = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const code=process.env.QML_FUNCTION;
function run(initialShortcut,attempted){
 const Plasmoid={globalShortcut:initialShortcut,configuration:{opmDefaultShortcutTried:attempted}};
 const context={Plasmoid};vm.createContext(context);vm.runInContext(code,context);
 context.initializeDefaultShortcut();
 return {Plasmoid,context};
}
let a=run('',false);
assert.equal(a.Plasmoid.globalShortcut,'Meta+X');
assert.equal(a.Plasmoid.configuration.opmDefaultShortcutTried,true);
a.Plasmoid.globalShortcut='';
a.context.initializeDefaultShortcut();
assert.equal(a.Plasmoid.globalShortcut,'');
let b=run('Ctrl+Alt+X',false);
assert.equal(b.Plasmoid.globalShortcut,'Ctrl+Alt+X');
let c=run('',true);
assert.equal(c.Plasmoid.globalShortcut,'');
"""
    result = subprocess.run(['node','-e',js],
        env={**os.environ,'QML_FUNCTION':function(qml,'initializeDefaultShortcut')},
        text=True,capture_output=True,timeout=12)
    assert result.returncode == 0, result.stderr + result.stdout
