#!/usr/bin/env python3
"""Private Plasma seat + production backend + recorded (never real) power calls.

Requires editor.Dockerfile dependencies, qml6-module-qttest and the native build.
X11 uses the real Meta+X shortcut and XTest key events, with an application behind
OPM. Wayland uses the applet activation signal and QtTest window key events in
an isolated copy of the widget. No fixture forwards a power/session request.
"""
import argparse
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
from plasma_popup import prepare
import plasma_popup
from plasma_startup import wait_for
from fixture_evidence import Evidence, tail
from private_compositor import active as compositor_active

SCRIPT = Path(__file__).resolve()


def observed_flyout_return(log, offset):
    """Require this input's show/hide transition, not an earlier hidden sample."""
    with log.open('rb') as stream:
        stream.seek(offset)
        lines=stream.read().decode(errors='replace').splitlines()
    shown=False
    for line in lines:
        if 'OPM_POPUP_TRACE ' not in line:continue
        try:row=json.loads(line.split('OPM_POPUP_TRACE ',1)[1])
        except ValueError:continue
        if row.get('callback')!='flyout.visibleChanged':continue
        visible=row['details']['window']['visible']
        if visible:shown=True
        elif shown:return True
    return False


def power_fixture():
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtDBus import QDBusConnection, QDBusVirtualObject
    app = QCoreApplication([])
    bus = QDBusConnection.sessionBus()
    class Recorder(QDBusVirtualObject):
        def introspect(self, path):
            return ''
        def handleMessage(self, msg, connection):
            member = msg.member()
            final = member in ('logoutAndShutdown', 'logoutAndReboot', 'logout',
                               'promptShutDown', 'promptReboot', 'promptLogout',
                               'SuspendWithFlags', 'HibernateWithFlags')
            if final:
                with open(os.environ['OPM_POWER_RECORD'], 'a') as output:
                    output.write(json.dumps({'interface': msg.interface(), 'path': msg.path(),
                                             'member': member, 'arguments': msg.arguments()})+'\n')
                connection.send(msg.createReply())
            elif member in ('CanSuspend', 'CanHibernate', 'CanPowerOff', 'CanReboot'):
                connection.send(msg.createReply('yes' if msg.interface() == 'org.freedesktop.login1.Manager' else True))
            elif member == 'HasInhibit':
                connection.send(msg.createReply(False))
            else:
                connection.send(msg.createErrorReply('org.test.Refused', 'Unimplemented test request; never forwarded'))
            return True
    fixture = Recorder()
    for name in ('org.kde.Shutdown','org.kde.LogoutPrompt','org.freedesktop.PowerManagement','org.freedesktop.login1'):
        assert bus.registerService(name), name
    for path in ('/Shutdown','/LogoutPrompt','/org/freedesktop/PowerManagement','/org/freedesktop/PowerManagement/Inhibit','/org/freedesktop/login1'):
        assert bus.registerVirtualObject(path, fixture), path
    print('SAFE_FIXTURE_READY', flush=True)
    app.exec()


def background():
    from PySide6.QtGui import QGuiApplication, QWindow
    app=QGuiApplication([]); window=QWindow()
    window.setTitle('OPM harmless application'); window.resize(640,400); window.show(); window.requestActivate()
    app.exec()


def instrument(case):
    prepare(case)
    # Holding I while invoking Meta+X can also activate the distribution's
    # Meta+I default. Its asynchronously launched System Settings window then
    # receives the deliberate repress. Isolate that unrelated application
    # shortcut in this disposable profile; keep the real OPM Meta+X path and
    # all physical input/release and exact mock-count assertions unchanged.
    settings=Path('/usr/share/kglobalaccel/systemsettings.desktop')
    if settings.is_file():
        overrides=case/'data/kglobalaccel';overrides.mkdir()
        source=settings.read_text()
        assert 'X-KDE-Shortcuts=' in source
        (overrides/settings.name).write_text('\n'.join(
            'X-KDE-Shortcuts=' if line.startswith('X-KDE-Shortcuts=') else line
            for line in source.splitlines())+'\n')
    path=case/'data/plasma/plasmoids/org.openpowermenu.start/contents/ui/main.qml'
    source=path.read_text().replace('import QtQuick\n','import QtQuick\nimport QtTest\n',1)
    source=source.replace('function handleKey(event) {', 'function handleKey(event) { console.info("OPM_KEY_ROOT",Date.now(),event.key,event.isAutoRepeat);')
    source=source.replace('Keys.onPressed: event => handleKey(event)', 'Keys.onPressed: event => handleKey(event)\n        Keys.onReleased: event => console.info("OPM_RELEASE_ROOT",Date.now(),event.key,event.isAutoRepeat)')
    source=source.replace('widget: Plasmoid.id, platform:', 'entries:root.menuEntries, commandError:root.commandError, layoutEditing:root.layoutEditing, launchPending:root.launchPending, widget: Plasmoid.id, platform:')
    source=source.replace('const value = reply.value;', 'const value = reply.value; if(methodName==="PowerCapabilitiesPending") console.info("OPM_PENDING",Date.now(),reply.isError,JSON.stringify(value),typeof value);')
    side=path.parent/'SideFlyout.qml'
    side_source=side.read_text().replace('import QtQuick\n','import QtQuick\nimport QtTest\n',1)
    side_source=side_source.replace('function handleKey(event) {', 'function handleKey(event) { console.info("OPM_KEY_SIDE",Date.now(),event.key,event.isAutoRepeat);').replace('Keys.onPressed: event => handleKey(event)', 'Keys.onPressed: event => handleKey(event)\n        Keys.onReleased: event => console.info("OPM_RELEASE_SIDE",Date.now(),event.key,event.isAutoRepeat)')
    side_source=side_source.replace('    id: flyout\n','''    id: flyout
    function fixtureKey(key, modifiers, kind) {
        if(activeChild && activeChild.visible) activeChild.fixtureKey(key,modifiers,kind);
        else flyoutSurface.fixtureKey(key,modifiers,kind);
    }
''',1)
    side_source=side_source.replace('        id: flyoutSurface\n','''        id: flyoutSurface
        TestCase { id: fixtureInput; name: "FlyoutInputOnly"; when: false }
        function fixtureKey(key, modifiers, kind) {
            if(kind==="press") fixtureInput.keyPress(Qt["Key_"+key], modifiers, 0);
            else if(kind==="release") fixtureInput.keyRelease(Qt["Key_"+key], modifiers, 0);
            else fixtureInput.keyClick(Qt["Key_"+key], modifiers, 0);
        }
''',1)
    side.write_text(side_source)
    drive_url=json.dumps((case/'drive.json').as_uri())
    source=source.replace('    property var menuEntries: []', '''
    property int fixtureSequence: 0
    Timer {
        interval: 20; repeat: true; running: true
        onTriggered: {
            const request=new XMLHttpRequest();
            request.open("GET", DRIVE_URL);
            request.onreadystatechange=function() {
                if(request.readyState!==XMLHttpRequest.DONE) return;
                const packet=JSON.parse(request.responseText);
                if(packet.sequence<=root.fixtureSequence) return;
                root.fixtureSequence=packet.sequence;
                if(packet.activate) Plasmoid.activated();
                else root.fullRepresentationItem.fixtureKeys(packet.keys,packet.modifiers||0,packet.kind||"click");
                console.info("OPM_KEYBOARD_ACK",packet.sequence);
            };
            request.send();
        }
    }
    property var menuEntries: []'''.replace('DRIVE_URL',drive_url))
    source=source.replace('id: popup\n','''id: popup
        TestCase { id: fixtureInput; name: "InputOnly"; when: false }
        function fixtureKeys(keys, modifiers, kind) {
            for(const key of keys) {
                if(flyout.visible && flyout.keyboardActivationRequested) flyout.fixtureKey(key,modifiers,kind);
                else if(kind==="press") fixtureInput.keyPress(Qt["Key_"+key], modifiers, 0);
                else if(kind==="release") fixtureInput.keyRelease(Qt["Key_"+key], modifiers, 0);
                else fixtureInput.keyClick(Qt["Key_"+key], modifiers, 0);
            }
        }
''',1)
    path.write_text(source)
    (case/'drive.json').write_text('{"sequence":0}')
    (case/'bin').mkdir()
    lock=case/'bin/loginctl'
    lock.write_text('''#!/bin/sh
[ "$1" = lock-session ] || exit 1
printf '%s\\n' '{"member":"Lock","arguments":[]}' >> "$OPM_POWER_RECORD"
''')
    lock.chmod(0o755)


def session(args):
    case=Path(args.output)
    evidence=Evidence(case,args.platform)
    os.environ['DBUS_SYSTEM_BUS_ADDRESS']=os.environ['DBUS_SESSION_BUS_ADDRESS']
    processes=[]; files=[]; sequence=0
    def spawn(command,name,pipe=False):
        output=(case/name).open('w'); files.append(output)
        p=subprocess.Popen(list(map(str,command)),stdout=subprocess.PIPE if pipe else output,stderr=output,text=True)
        processes.append(p); return p
    def command(*argv): return subprocess.check_output(argv,text=True).strip()
    def state():
        # Poll only the tail: repeatedly parsing all retained diagnostic frames
        # needlessly loads the test seat during keyboard timing checks.
        path=case/'plasma.log'
        if not path.exists(): return None
        with path.open('rb') as log:
            log.seek(max(0,path.stat().st_size-65536))
            lines=log.read().decode(errors='replace').splitlines()
        for line in reversed(lines):
            if 'OPM_POPUP_TRACE ' not in line: continue
            try: return json.loads(line.split('OPM_POPUP_TRACE ',1)[1])['state']
            except (ValueError,KeyError): pass
        return None
    def plasma_inactive():
        current=state()
        if not current: return False
        popup=current.get('popup') or {}
        windows=[current.get('panelWindow'),popup.get('window'),(popup.get('flyout') or {}).get('window')]
        return not any((window or {}).get('active',False) for window in windows)
    def records():
        path=case/'requests.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    def packet(**value):
        nonlocal sequence
        sequence+=1
        path=case/'drive-next.json';path.write_text(json.dumps({'sequence':sequence,**value}));path.replace(case/'drive.json')
        wait_for(lambda: 'OPM_KEYBOARD_ACK '+str(sequence) in (case/'plasma.log').read_text())
    def activate():
        if args.platform=='xcb': command('xdotool','key','--clearmodifiers','super+x')
        else: packet(activate=True)
    def keys(*values):
        # Zero delay deliberately includes genuine same-millisecond presses
        # mislabeled by Qt. Only native physical evidence can distinguish them.
        if args.platform=='xcb':
            evidence.record('key-click',keys=values,focus=evidence.focus(),requests=len(records()))
            command('xdotool','key','--clearmodifiers','--delay','0',*values)
        else: packet(keys=[v.upper() if len(v)==1 else v for v in values])
    def popup_has_input_focus():
        if args.platform!='xcb':return True
        focused=subprocess.run(['xdotool','getwindowfocus'],capture_output=True,text=True)
        window=focused.stdout.strip()
        # PointerRoot/None is an expected intermediate state while KWin
        # restores focus. Keep observing; it is not an input-ready window.
        if focused.returncode or not window.isdigit() or int(window)<=1:return False
        props=subprocess.run(['xprop','-id',window,'_NET_WM_PID','_NET_WM_WINDOW_TYPE'],capture_output=True,text=True)
        return props.returncode==0 and ('= '+str(plasma.pid)) in props.stdout and '_KDE_NET_WM_WINDOW_TYPE_APPLET_POPUP' in props.stdout
    def open_menu():
        if app_id:
            command('xdotool','windowactivate','--sync',app_id)
            # EWMH active-window acknowledgement precedes X input focus.
            # Do not overlap the fixture's application activation with Meta+X.
            wait_for(lambda: command('xdotool','getwindowfocus') == app_id)
            wait_for(plasma_inactive)
        activate()
        # Plasma first eagerly expands before OPM's existing readiness handoff.
        # Observe the completed opening, not that provisional host popup.
        wait_for(lambda: state() and state()['expanded'] and state()['powerIsOpen']
                 and not state()['openingPower'] and state()['popup']['window']['visible']
                 and state()['popup']['activeFocus'] and not state()['launchPending'])
        if args.platform=='xcb':
            # Qt's grouped active state can precede XSetInputFocus. Wait for
            # actual delivery to the applet, without requesting focus ourselves.
            wait_for(popup_has_input_focus)
    config=case/'config/open-power-menu/menu.json'; config.parent.mkdir(exist_ok=True)
    def configure(confirm,custom=False):
        children=[{'action':a} for a in ('shutdown','reboot','logout','sleep','hibernate','lock')]
        children += [{'separator':True},{'label':'Unavailable','command':['/opm-test-unavailable'],'access_key':'D'}]
        if custom: children[0]['access_key']='Z'; children[1]['access_key']=''
        cfg={'menu':[{'submenu':'Shut down or sign out','access_key':'U','items':children}],
             'confirm_power_actions':confirm,'hide_original_launcher':args.hidden,'launcher_applet_id':3,
             'show_unavailable':True,'auto_close_on_pointer_leave':False}
        config.write_text(json.dumps(cfg))
        (case/'config/ksmserverrc').write_text('[General]\nconfirmLogout='+str(not confirm).lower()+'\n')
    try:
        if args.platform=='xcb':
            read,write=os.pipe(); output=(case/'display.log').open('w');files.append(output)
            display_command=(['Xephyr','-title','OPM PRIVATE MOCKS - no real power actions',
                              '-screen','1280x800'] if args.manual_seconds else
                             ['Xvfb','-screen','0','1280x800x24'])
            display_env={**os.environ,'DISPLAY':os.environ.get('OPM_PARENT_DISPLAY','')}
            p=subprocess.Popen(display_command+['-displayfd',str(write),'-nolisten','tcp'],
                               env=display_env,stdout=output,stderr=output,pass_fds=(write,))
            processes.append(p);os.close(write);assert select.select([read],[],[],10)[0]
            os.environ['DISPLAY']=':'+os.read(read,64).decode().strip();os.close(read)
            command('dbus-update-activation-environment','DISPLAY')
            os.environ['OPM_PRIVATE_X11_EVIDENCE']=os.environ['DISPLAY']
            probe=Path(os.environ.get('OPM_TEST_X11_PROBE',str(Path(args.backend).parent/'native-x11-input-probe')))
            assert probe.is_file(), 'Build the private XI2 evidence probe'
            spawn([probe],'xinput.jsonl')
            wait_for(lambda:'"event":"ready"' in tail(case/'xinput.jsonl'))
        fixture=spawn([sys.executable,SCRIPT,'--power-fixture'],'fixture.log',pipe=True)
        assert select.select([fixture.stdout],[],[],10)[0]
        assert fixture.stdout.readline().strip()=='SAFE_FIXTURE_READY'
        configure(False)
        spawn([args.backend,'--service','--bus-name','org.openpowermenu.Service'],'backend.log')
        if args.platform=='xcb':
            spawn(['kwin_x11'],'kwin.log')
            spawn([plasma_popup.shortcut_daemon()],'shortcuts.log')
        else:
            binary=case/'bin/kwin_wayland'; shutil.copyfile(shutil.which('kwin_wayland'),binary);binary.chmod(0o700)
            compositor=spawn([binary,'--virtual','--width','1280','--height','800','--no-lockscreen','--no-global-shortcuts','--socket',os.environ['WAYLAND_DISPLAY']],'kwin.log')
            wait_for(lambda:(Path(os.environ['XDG_RUNTIME_DIR'])/os.environ['WAYLAND_DISPLAY']).is_socket())
            def compositor_ready():
                return compositor_active(compositor)
            # A Wayland socket alone can precede a fatal renderer failure.
            wait_for(compositor_ready)
        plasma=spawn(['plasmashell','--no-respawn'],'plasma.log')
        wait_for(lambda:state() and state()['button'])
        app=spawn([sys.executable,SCRIPT,'--background'],'application.log')
        app_id=wait_for(lambda:subprocess.run(['xdotool','search','--onlyvisible','--pid',str(app.pid)],capture_output=True,text=True).stdout.strip()) if args.platform=='xcb' else None
        if args.platform=='xcb':
            command('qdbus6','org.kde.plasmashell','/PlasmaShell','org.kde.PlasmaShell.evaluateScript',
                    'panels().forEach(p=>p.widgets().forEach(w=>{if(w.type==="org.openpowermenu.start")w.globalShortcut="Meta+X";}));')
        if args.manual_seconds:
            # Physical acceptance stays on this nested display/private bus.
            # No automatic selections, forwards, install or shell restart.
            print('SAFE_MANUAL_READY',case/'requests.jsonl',flush=True)
            deadline=time.monotonic()+args.manual_seconds
            while time.monotonic()<deadline:
                assert fixture.poll() is None, 'Mock services exited; stopping the seat'
                if any(p.poll() is not None for p in processes): break
                time.sleep(.1)
            print('SAFE_MANUAL_FINISHED requests',len(records()),flush=True)
            return
        # Same applet/global shortcut toggles off without creating an operation.
        open_menu();activate();wait_for(lambda:not state()['expanded'] and state()['requestedMenu']=='none');assert not records()
        report=[]
        for confirm in (False,True):
            configure(confirm)
            for key,method in [('u','promptShutDown' if confirm else 'logoutAndShutdown'),
                               ('r','promptReboot' if confirm else 'logoutAndReboot'),
                               ('i','promptLogout' if confirm else 'logout'),
                               ('s','SuspendWithFlags'),('h','HibernateWithFlags'),('l','Lock')]:
                evidence.begin('ordinary-'+key+'-confirmation-'+str(confirm))
                before=len(records());open_menu()
                # Consecutive submenu/access keys have no artificial pause.
                keys('u',key)
                wait_for(lambda:len(records())>before)
                wait_for(lambda:not state()['expanded'])
                assert len(records())==before+1, records()[before:]
                assert records()[-1]['member']==method, records()[-1]
                assert state()['hideOriginalLauncher']==args.hidden
                report.append({'confirmation':confirm,'keys':['Meta+X','U',key.upper()],'request':records()[-1]})
        evidence.begin('escape-flyout-then-root')
        before=len(records());open_menu()
        log=case/'plasma.log';offset=log.stat().st_size
        keys('u','Escape')
        # A hidden snapshot can precede U opening the flyout. It does not prove
        # Escape returned to the parent. Observe the actual transition before
        # injecting the next key, then require native root input focus again.
        wait_for(lambda:observed_flyout_return(log,offset))
        wait_for(lambda:state()['expanded'] and not state()['popup']['flyout']['window']['visible']
                 and popup_has_input_focus())
        keys('Escape');wait_for(lambda:not state()['expanded']);assert len(records())==before
        evidence.begin('arrow-enter-navigation')
        open_menu();keys('Down','Right','Down','Up','Return')
        wait_for(lambda:len(records())==before+1);wait_for(lambda:not state()['expanded'])
        assert records()[-1]['member']=='promptShutDown'
        evidence.begin('modified-access-keys-ignored')
        before=len(records());open_menu();keys('u')
        wait_for(lambda:state()['popup']['flyout']['window']['visible'] and state()['popup']['flyout']['window']['active'])
        if args.platform=='xcb':
            command('xdotool','key','--clearmodifiers','ctrl+u','alt+u','shift+u')
        else:
            for modifier in (0x04000000,0x08000000,0x02000000): packet(keys=['U'],modifiers=modifier)
        assert len(records())==before
        assert not state()['layoutEditing']
        assert state()['popup']['flyout']['window']['visible']
        evidence.begin('left-to-parent-then-escape')
        keys('Left');wait_for(lambda:state()['expanded'] and not state()['popup']['flyout']['window']['visible']
                             and popup_has_input_focus())
        keys('Escape');wait_for(lambda:not state()['expanded'])
        evidence.begin('custom-access-keys')
        configure(False,custom=True);before=len(records());open_menu();keys('u','r','d')
        assert len(records())==before
        keys('z');wait_for(lambda:len(records())==before+1);assert records()[-1]['member']=='logoutAndShutdown'
        wait_for(lambda:not state()['expanded'])
        # A held U opens the submenu, but its genuine X server auto-repeat
        # must never choose Shutdown. Release and a fresh press selects once.
        if args.held_repeat and args.platform=='xcb':
            evidence.begin('held-U-server-autorepeat')
            configure(True);before=len(records());open_menu()
            command('xdotool','keydown','u')
            try:
                time.sleep(1) # Test input is held; there is no production delay.
                assert len(records())==before
                assert state()['expanded'] and state()['popup']['flyout']['window']['visible']
                assert 'InputGuard.rejected' in (case/'plasma.log').read_text()
            finally: command('xdotool','keyup','u')
            keys('u');wait_for(lambda:len(records())==before+1)
            wait_for(lambda:not state()['expanded'])
            assert records()[-1]['member']=='promptShutDown'

        if args.held_repeat:
            stress=[]
            def down(key):
                evidence.record('key-down',key=key,focus=evidence.focus(),requests=len(records()))
                if args.platform=='xcb': command('xdotool','keydown',key.lower() if len(key)==1 else key)
                else: packet(keys=[key],kind='press')
            def up(key):
                if args.platform=='xcb': command('xdotool','keyup',key.lower() if len(key)==1 else key)
                else: packet(keys=[key],kind='release')
                evidence.record('key-up-sent',key=key,focus=evidence.focus(),requests=len(records()))
            def repeats(key):
                if args.platform=='xcb':
                    # Genuine server repeats plus duplicate down events, with
                    # no physical release. This is test input, not a cooldown.
                    time.sleep(.8)
                    for _ in range(3): down(key)
                else:
                    # QtTest press events explicitly report isAutoRepeat=false.
                    for _ in range(4): down(key)
            configure(False)
            evidence.begin('held-U-focus-transfer-dismiss-reopen-release-rapid-U-U')
            before=len(records());open_menu();down('U')
            try:
                repeats('U');assert len(records())==before
                assert state()['popup']['flyout']['window']['visible']
                # Real global shortcut dismissal/reopen while U remains down.
                activate();wait_for(lambda:not state()['expanded'])
                open_menu();repeats('U')
                assert len(records())==before
                assert not state()['popup']['flyout']['window']['visible']
            finally: up('U')
            keys('u','u');wait_for(lambda:len(records())==before+1)
            wait_for(lambda:not state()['expanded'])
            assert records()[-1]['member']=='logoutAndShutdown'
            stress.append({'case':'held-U-focus-transfer-dismiss-reopen-release-rapid-U-U','requests':1})
            # Repeated key events after acceptance cannot select another action
            # after the root/flyout are opened again while that key remains down.
            for key,method in [('R','logoutAndReboot'),('I','logout'),('S','SuspendWithFlags'),('H','HibernateWithFlags'),('L','Lock')]:
                evidence.begin('held-'+key+'-dismiss-reopen-deliberate-repress-'+method)
                before=len(records());open_menu();keys('u');down(key)
                try:
                    wait_for(lambda:len(records())==before+1);wait_for(lambda:not state()['expanded'])
                    # QtTest cannot target an unmapped Wayland popup: it falls
                    # back to the panel and may invoke KRunner. Real compositor
                    # input also does not reach our hidden windows.
                    if args.platform=='xcb': repeats(key)
                    assert len(records())==before+1
                    open_menu();keys('u');repeats(key);assert len(records())==before+1
                finally: up(key)
                keys(key.lower());wait_for(lambda:len(records())==before+2)
                wait_for(lambda:not state()['expanded'])
                assert [row['member'] for row in records()[before:]]==[method,method]
                stress.append({'case':'held-'+key+'-dismiss-reopen-deliberate-repress','requests':2})
            # A key pressed outside the menu cannot turn into a selection when
            # the popup opens. Release, then two zero-delay presses still work.
            if args.platform=='xcb':
                evidence.begin('held-before-opening')
                before=len(records());down('U')
                try:
                    open_menu();repeats('U');assert len(records())==before
                    assert not state()['popup']['flyout']['window']['visible']
                finally: up('U')
                keys('u','u');wait_for(lambda:len(records())==before+1);wait_for(lambda:not state()['expanded'])
                stress.append({'case':'held-before-opening','requests':1})
            evidence.begin('held-Escape-returns-one-level-only')
            before=len(records());open_menu();keys('u');down('Escape')
            try:
                repeats('Escape');assert state()['expanded']
                assert not state()['popup']['flyout']['window']['visible']
            finally: up('Escape')
            keys('Escape');wait_for(lambda:not state()['expanded']);assert len(records())==before
            stress.append({'case':'held-Escape-returns-one-level-only','requests':0})
            (case/'stress.json').write_text(json.dumps(stress,indent=2)+'\n')
        (case/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        if args.platform=='wayland': assert compositor_ready(), 'Private compositor stopped during keyboard tests'
        print('PASS',args.platform,'hidden',args.hidden,'requests',len(records()),flush=True)
    except BaseException:
        evidence.failure(processes,state=state(),requests=records())
        for line in tail(case/'plasma.log',200000).splitlines():
            if any(token in line for token in ('OPM_KEY_', 'OPM_RELEASE_', 'InputGuard.')):
                print('OPM_INPUT_EVIDENCE '+line[:3000],flush=True)
        raise
    finally:
        evidence.record('teardown-begin',processes=[{'pid':p.pid,'returncode':p.poll()} for p in processes])
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait()
            evidence.record('process-ended',pid=p.pid,command=str(p.args[0]),returncode=p.returncode)
            if p.stdout:p.stdout.close()
        for output in files:output.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output');p.add_argument('--backend');p.add_argument('--platform',choices=['xcb','wayland'])
    p.add_argument('--hidden',action='store_true');p.add_argument('--session',action='store_true')
    p.add_argument('--held-repeat',action='store_true',help='Stress physical X11 repeats and shared Wayland key state')
    p.add_argument('--manual-seconds',type=int,default=0,help='Open one private Xephyr/mock seat for physical input (30–900 seconds); requires Xephyr and a parent X display')
    p.add_argument('--widget-source',type=Path,help='Optional checkout for before/after UI comparison; default is this checkout')
    p.add_argument('--power-fixture',action='store_true');p.add_argument('--background',action='store_true')
    args=p.parse_args()
    if args.power_fixture:return power_fixture()
    if args.background:return background()
    if args.session:return session(args)
    if args.manual_seconds and not 30<=args.manual_seconds<=900:
        p.error('--manual-seconds must be between 30 and 900')
    if args.manual_seconds and (args.platform=='wayland' or not os.environ.get('DISPLAY') or not shutil.which('Xephyr')):
        p.error('Manual acceptance requires Xephyr, DISPLAY and --platform xcb')
    os.environ['OPM_TEST_INPUT_MODULE']=str(Path(args.backend).resolve().parent/'nativeinput')
    if args.widget_source: plasma_popup.ROOT=args.widget_source.resolve()
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    for platform in (['xcb'] if args.manual_seconds else [args.platform] if args.platform else ['xcb','wayland']):
        for hidden in ([args.hidden] if args.manual_seconds else (False,True)):
            case=output/(platform+('-hidden' if hidden else '-visible'));case.mkdir();instrument(case)
            with tempfile.TemporaryDirectory(prefix='opm-keyboard-') as runtime:
                env={**os.environ,'DISPLAY':'','WAYLAND_DISPLAY':'opm-keyboard-test' if platform=='wayland' else '',
                     'XDG_RUNTIME_DIR':runtime,'QT_QPA_PLATFORM':platform,'QT_QUICK_BACKEND':'software',
                     # Read the private shell's diagnostics even on Qt builds
                     # whose default log sink is journald instead of stderr.
                     'QT_FORCE_STDERR_LOGGING':'1',
                     'KDE_FULL_SESSION':'true','KDE_SESSION_VERSION':'6','QML_XHR_ALLOW_FILE_READ':'1',
                     'PATH':str(case/'bin')+os.pathsep+os.environ['PATH'],'OPM_POWER_RECORD':str(case/'requests.jsonl')}
                if args.manual_seconds:
                    env['OPM_PARENT_DISPLAY']=os.environ['DISPLAY']
                    print('Private mock seat:',case,'— capture the Xephyr keyboard before Meta+X; see HELD-KEY-STABILIZATION.md',flush=True)
                env.update({f'XDG_{key.upper()}_HOME':str(case/key) for key in ('config','data','cache','state')})
                if platform=='wayland': env['KWIN_COMPOSE']=os.environ.get('OPM_TEST_KWIN_COMPOSE','Q')
                else: env.pop('KWIN_COMPOSE',None) # KWin X11 does not support QPainter.
                with (case/'session.log').open('w') as log:
                    run=subprocess.run(['dbus-run-session','--',sys.executable,SCRIPT,'--session','--platform',platform,
                        '--output',case,'--backend',args.backend]+(['--hidden'] if hidden else [])+(['--held-repeat'] if args.held_repeat else [])+
                        (['--manual-seconds',str(args.manual_seconds)] if args.manual_seconds else []),
                        env=env,stdout=log,stderr=subprocess.STDOUT,timeout=max(180,args.manual_seconds+60))
                if run.returncode:
                    # A failed Docker layer is not available for later artifact
                    # collection. Preserve the component diagnostics in its log.
                    failure=case/'failure.json'
                    if failure.is_file():
                        print('OPM_FIXTURE '+json.dumps(json.loads(failure.read_text())),flush=True)
                    for name in ('session.log', 'plasma.log', 'kwin.log', 'backend.log',
                                 'fixture.log', 'application.log', 'shortcuts.log'):
                        path = case/name
                        if path.exists():
                            print('\nPRIVATE FIXTURE '+name+'\n'+path.read_text(errors='replace')[-14000:],
                                  file=sys.stderr, flush=True)
                    raise AssertionError('Private keyboard seat failed: '+str(case))
            print('PASS',case,flush=True)


if __name__=='__main__':main()
