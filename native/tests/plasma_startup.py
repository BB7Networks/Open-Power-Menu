#!/usr/bin/env python3
"""Disposable real-Plasma startup regression. Never uses the user's desktop/bus.

Run in the test container: python3 native/tests/plasma_startup.py --output DIR.
X11 uses real right-clicks. Wayland uses the applet activation handler and real
KWin popup windows. Backend actions are refused; only read-only methods exist.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import select
import subprocess
import sys
import time
import tempfile

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]


def backend():
    from PySide6.QtCore import QCoreApplication, QTimer
    from PySide6.QtDBus import QDBusConnection, QDBusVirtualObject
    app = QCoreApplication([])
    bus = QDBusConnection.sessionBus()
    class Backend(QDBusVirtualObject):
        def introspect(self, path):
            return '<interface name="org.openpowermenu.Service">' + ''.join(
                f'<method name="{name}"><arg type="{typ}" direction="out"/></method>'
                for name, typ in [('GetMenu', 's'), ('GetIntegration', 's'), ('PowerCapabilitiesPending', 'b')]) + '</interface>'
        def handleMessage(self, msg, connection):
            name = msg.member()
            print(json.dumps({'time': time.time()*1000, 'request': name}), flush=True)
            if name == 'GetMenu':
                entries = [{'kind': 'command', 'key': str(i), 'title': f'Safe test command {i}',
                            'icon': 'applications-system', 'enabled': i != 3} for i in range(12)]
                entries[0] = {'kind':'submenu', 'key':'group', 'title':'Safe test group', 'enabled':True,
                              'icon':'folder', 'items':[entries[1], entries[3],
                              {'kind':'submenu','key':'nested','title':'Nested group','items':[entries[2]]}]}
                value = json.dumps(entries)
                delay = int(os.environ['OPM_MENU_DELAY'])
            elif name == 'GetIntegration':
                value = json.dumps({'menu_density': os.environ['OPM_DENSITY'],
                                    'menu_height_mode': os.environ['OPM_HEIGHT_MODE'], 'menu_custom_height': int(os.environ['OPM_CUSTOM_HEIGHT']),
                                    'menu_icon_size': os.environ['OPM_ICON_SIZE'], 'appearance': os.environ['OPM_APPEARANCE']})
                delay = int(os.environ['OPM_PREF_DELAY'])
            elif name == 'PowerCapabilitiesPending':
                value, delay = False, 0
            else:
                connection.send(msg.createErrorReply('org.freedesktop.DBus.Error.NotSupported', 'Test backend refuses actions'))
                return True
            def reply():
                print(json.dumps({'time': time.time()*1000, 'response': name}), flush=True)
                connection.send(msg.createReply([value]))
            QTimer.singleShot(delay, reply)
            return True
    service = Backend()
    assert bus.registerService('org.openpowermenu.Service')
    assert bus.registerVirtualObject('/OpenPowerMenu', service)
    app.exec()


PROBE = '''
    property bool startupPanelPainted: false
    property bool startupPopupPainted: false
    property int startupPhase: 0
    function startupDriveWayland() {
        const popup=root.fullRepresentationItem;
        const window=popup ? popup.Window.window : null;
        if(startupPhase===0 && startupPanelPainted && root.Window.window && root.Window.window.visible) {
            startupPhase=1;
            root.activatePowerShortcut();
        } else if(startupPhase===1 && root.expanded && startupPopupPainted) {
            startupPhase=2;
            root.activatePowerShortcut();
        } else if(startupPhase===2 && !root.expanded && (!window || !window.visible)) {
            startupPhase=3;
            root.activatePowerShortcut();
        }
    }
    Connections {
        target: root.Window.window
        function onFrameSwapped() { root.startupPanelPainted=true; }
    }
    function startupProbe(event) {
        const p = root.fullRepresentationItem;
        const w = p ? p.Window.window : null;
        const button = root.compactRepresentationItem;
        const center = button ? button.mapToGlobal(button.width/2,button.height/2) : null;
        return {time:Date.now(),event:event,open:root.expanded,entries:root.menuEntries.length,
            fetching:root.fetching,density:root.menuDensity,icons:root.menuIconSize,mode:root.menuHeightMode,
            saved:root.menuCustomHeight,area:root.menuWorkArea.height,
            heightPreference:root.menuHeightPreference,
            button:center ? [center.x,center.y] : null,
            panelPainted:root.startupPanelPainted,popupPainted:root.startupPopupPainted,
            panelVisible:root.Window.window ? root.Window.window.visible : false,
            natural:p ? p.naturalHeight : null,preferred:p ? p.Layout.preferredHeight : null,
            min:p ? p.Layout.minimumHeight : null,max:p ? p.Layout.maximumHeight : null,
            padding:p ? p.themeVerticalPadding : null,actual:p ? p.height : null,
            firstRow:p ? p.startupRowCenter() : null,
            flyout:p ? p.startupFlyoutState() : null,
            window:w ? [w.x,w.y,w.width,w.height,w.visible] : null};
    }
    Timer {
        interval:20; repeat:true; running:true
        property string previous: ""
        onTriggered: {
            const data=root.startupProbe("sample");
            const compare=JSON.stringify(Object.assign({},data,{time:0}));
            if(compare!==previous) { console.info("OPM_STARTUP",JSON.stringify(data)); previous=compare; }
        }
    }
'''


def instrument(case, platform):
    widget = case/'data/plasma/plasmoids/org.openpowermenu.start'
    shutil.copytree(ROOT/'plasmoid', widget)
    path = widget/'contents/ui/main.qml'
    source = path.read_text()
    # Keep shortcuts out of the fixture. Instrument a copy, never installed files.
    source = source.replace('Component.onCompleted: Qt.callLater(() => root.initializeDefaultShortcut())',
                            'Component.onCompleted: console.info("OPM_WIDGET_READY",Date.now())')
    source = source.replace('    property var menuEntries: []', PROBE+'\n    property var menuEntries: []')
    source = source.replace('        id: popup\n', '''        id: popup
        onFittedHeightChanged: console.info("OPM_STARTUP", JSON.stringify(root.startupProbe("height")))
        function startupRowCenter() {
            const row=normalRows.itemAt(0);
            const point=row ? row.mapToGlobal(row.width/2,row.height/2) : Qt.point(0,0);
            return [point.x,point.y];
        }
        function startupFlyoutState() {
            return {visible:flyout.visible,appearance:flyout.appearance,width:flyout.width,height:flyout.height,
                    text:String(flyout.textColor),surface:String(flyout.surfaceColor)};
        }
        Connections {
            target: popup.Window.window
            property int frames: 0
            function onVisibleChanged() {
                frames=0;
                root.startupPopupPainted=false;
                console.info("OPM_STARTUP", JSON.stringify(root.startupProbe("visibility")));
            }
            function onFrameSwapped() {
                if(root.expanded && frames++<2) {
                    root.startupPopupPainted=true;
                    console.info("OPM_STARTUP", JSON.stringify(root.startupProbe("frame")));
                }
            }
        }
''')
    if platform == 'wayland':
        # Drive activation from actual exposure/paint/hide transitions, not
        # timers that can overtake a backend response on a loaded CI runner.
        source=source.replace('previous=compare; }','previous=compare; }\n            root.startupDriveWayland();')
    path.write_text(source)


def read_states(path):
    rows = []
    if path.exists():
        for line in path.read_text(errors='replace').splitlines():
            if 'OPM_STARTUP ' in line:
                rows.append(json.loads(line.split('OPM_STARTUP ', 1)[1]))
    return rows


def wait_for(predicate, timeout=15):
    until = time.monotonic()+timeout
    while time.monotonic() < until:
        value = predicate()
        if value:
            return value
        time.sleep(.025)
    raise AssertionError('Timed out waiting for isolated Plasma: see retained logs')


def session(args):
    case = Path(args.output).resolve()
    assert (case/'runtime-path.txt').read_text()==os.environ['XDG_RUNTIME_DIR']
    processes, files = [], []
    def spawn(command, name, env=None, pass_fds=()):
        out = (case/name).open('w'); files.append(out)
        p = subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT, env=env, pass_fds=pass_fds)
        processes.append(p)
        return p
    def stop(p):
        if p.poll() is None:
            p.terminate()
            try: p.wait(timeout=5)
            except subprocess.TimeoutExpired: p.kill(); p.wait()
    try:
        if args.platform == 'xcb':
            # Let Xvfb allocate its own display. Never attach to an existing seat.
            read_fd, write_fd = os.pipe()
            spawn(['Xvfb', '-displayfd', str(write_fd), '-screen', '0', f'{args.width}x{args.height}x24',
                   '-nolisten', 'tcp'], 'display.log', pass_fds=(write_fd,))
            os.close(write_fd)
            try:
                assert select.select([read_fd],[],[],10)[0], 'Xvfb did not allocate a display'
                display=os.read(read_fd,64).decode().strip()
                assert display.isdigit(), 'Xvfb failed to start'
                os.environ['DISPLAY']=':'+display
            finally:
                os.close(read_fd)
            subprocess.run(['dbus-update-activation-environment','DISPLAY'],check=True)
            spawn(['kwin_x11', '--replace'], 'kwin.log', {key:value for key,value in os.environ.items() if key!='KWIN_COMPOSE'})
        else:
            binary=case/'bin/kwin_wayland'; binary.parent.mkdir()
            shutil.copyfile(shutil.which('kwin_wayland'), binary); binary.chmod(0o700)
            spawn([str(binary), '--virtual', '--width', str(args.width), '--height', str(args.height),
                   '--scale', str(args.scale), '--output-count', str(args.outputs), '--no-lockscreen',
                   '--no-global-shortcuts', '--socket', os.environ['WAYLAND_DISPLAY']], 'kwin.log')
            wait_for(lambda: (Path(os.environ['XDG_RUNTIME_DIR'])/os.environ['WAYLAND_DISPLAY']).is_socket())
        spawn([sys.executable, str(SCRIPT), '--backend'], 'backend.jsonl')
        for phase in ['fresh', 'shell-restart']:
            log = case/f'{phase}.log'
            shell = spawn(['plasmashell', '--no-respawn'], log.name)
            if phase == 'fresh':
                def desktop_ready():
                    r=subprocess.run(['qdbus6','org.kde.plasmashell','/PlasmaShell','org.kde.PlasmaShell.evaluateScript',
                        'print(desktops().length>0 && panels().some(p=>p.widgetIds.length>0));'],capture_output=True,text=True)
                    return r.returncode==0 and r.stdout.strip()=='true'
                wait_for(desktop_ready)
                def panel():
                    result = subprocess.run(['qdbus6', 'org.kde.plasmashell', '/PlasmaShell',
                        'org.kde.PlasmaShell.evaluateScript',
                        f'panels().forEach(p => p.remove()); var p=new Panel; p.location="{args.panel_edge}"; p.height=48; '
                        'var w=p.addWidget("org.openpowermenu.start"); w.writeConfig("opmDefaultShortcutTried",true);'],
                        capture_output=True)
                    return result.returncode == 0
                wait_for(panel)
            if args.platform == 'xcb':
                def panel_ready():
                    states=read_states(log)
                    if not states: return None
                    state=states[-1]
                    # Use the latest geometry and a painted window. Earlier
                    # animation samples can already have plausible coordinates.
                    return state if state['button'] and state['area']>0 and state['panelPainted'] and state['panelVisible'] else None
                state = wait_for(panel_ready)
                x,y=map(round,state['button'])
                # The normal panel MouseArea handles these real pointer events.
                for opening in range(2):
                    print(json.dumps({'time':time.time()*1000,'pointer_click':[x,y],'opening':opening}),flush=True)
                    subprocess.run(['xdotool','mousemove',str(x),str(y)],check=True)
                    time.sleep(.1)
                    subprocess.run(['xdotool','click','3'],check=True)
                    wait_for(lambda: sum(s['event']=='visibility' and s['window'] and s['window'][4] for s in read_states(log)) > opening)
                    wait_for(lambda: read_states(log)[-1]['popupPainted'])
                    if opening == 0:
                        subprocess.run(['xdotool','click','3'],check=True)
                        wait_for(lambda: not read_states(log)[-1]['open'] and
                            not (read_states(log)[-1]['window'] and read_states(log)[-1]['window'][4]))
            else:
                wait_for(lambda: sum(s['event']=='visibility' and s['window'] and s['window'][4] for s in read_states(log)) >= 2, timeout=25)
            time.sleep(.15) # Observation after exposure; never controls the production opening.
            states = read_states(log)
            first = [s for s in states if s['event']=='visibility' and s['window'] and s['window'][4]]
            assert len(first) == 2, first
            frames=[state for state in states if state['event']=='frame']
            assert len(frames)>=2, states
            for state in states:
                pref=state.get('heightPreference')
                if pref and pref['mode']=='custom':
                    assert pref['height']==int(os.environ['OPM_CUSTOM_HEIGHT']), state
                    if state['preferred'] is not None:
                        assert state['preferred']<=pref['height'], state
            for frame in frames:
                assert frame['actual']==frame['preferred'], frame
            for state in first:
                assert state['entries']==12 and not state['fetching'], state
                assert state['density']==os.environ['OPM_DENSITY'] and state['icons']==os.environ['OPM_ICON_SIZE'], state
                assert state['mode']==os.environ['OPM_HEIGHT_MODE'] and state['saved']==int(os.environ['OPM_CUSTOM_HEIGHT']), state
                assert state['preferred']==state['min']==state['max'], state
                assert abs(state['window'][3]-state['preferred']-state['padding']) <= 2, state
                assert state['window'][3] <= state['area'], state
            (case/f'{phase}-states.json').write_text(json.dumps(states,indent=2))
            if args.platform=='xcb':
                x,y=map(round,states[-1]['firstRow'])
                subprocess.run(['xdotool','mousemove',str(x),str(y)],check=True)
                shown=wait_for(lambda: next((s for s in reversed(read_states(log)) if s['flyout'] and s['flyout']['visible']),None))
                assert shown['flyout']['appearance']==os.environ['OPM_APPEARANCE'], shown
                assert shown['window'][3]==first[-1]['window'][3], shown
                if os.environ['OPM_APPEARANCE']=='aero-light':
                    assert shown['flyout']['text']=='#24394b' and shown['flyout']['surface']=='#eaf1f7', shown
                elif os.environ['OPM_APPEARANCE']=='aero':
                    assert shown['flyout']['text']=='#eff3f8' and shown['flyout']['surface']=='#27313d', shown
                (case/f'{phase}-states.json').write_text(json.dumps(read_states(log),indent=2))
                code='from PySide6.QtGui import QGuiApplication; a=QGuiApplication([]); assert a.primaryScreen().grabWindow(0).save('+repr(str(case/f'{phase}.png'))+')'
                subprocess.run([sys.executable,'-c',code],check=True)
            stop(shell)
            wait_for(lambda: subprocess.run(['qdbus6','org.kde.plasmashell','/PlasmaShell'],capture_output=True).returncode != 0)
        requests=[json.loads(line)['request'] for line in (case/'backend.jsonl').read_text().splitlines() if '"request"' in line]
        assert set(requests) <= {'GetIntegration','GetMenu','PowerCapabilitiesPending'}, requests
        print('PASS',case.name,flush=True)
    finally:
        for p in reversed(processes): stop(p)
        for f in files: f.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='work/plasma-startup')
    parser.add_argument('--only')
    parser.add_argument('--session',action='store_true')
    parser.add_argument('--backend',action='store_true')
    parser.add_argument('--platform',choices=['xcb','wayland'],default='xcb')
    parser.add_argument('--panel-edge',choices=['bottom','top','left','right'],default='bottom')
    parser.add_argument('--width',type=int,default=1280)
    parser.add_argument('--height',type=int,default=800)
    parser.add_argument('--scale',type=float,default=1)
    parser.add_argument('--outputs',type=int,default=1)
    args=parser.parse_args()
    if args.backend: return backend()
    if args.session: return session(args)
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    # Delays alter reply order, never readiness correctness. Third case is warm.
    for platform in ['xcb','wayland']:
        for name,mode,density,theme,menu_delay,pref_delay,width,height,scale,outputs,edge in [
            ('slow-menu','auto','standard','native',1400,50,1280,800,1,1,args.panel_edge),
            ('slow-preferences','custom','comfortable','aero-light',50,5600,1024,640,1,1,args.panel_edge),
            ('ready','auto','compact','aero',0,0,1600,1000,1.25,2,args.panel_edge),
            ('ready-left','auto','compact','aero',0,0,1600,1000,1.25,2,'left')]:
            if args.only and args.only!=f'{platform}-{name}': continue
            case=output/f'{platform}-{name}'
            case.mkdir() # Refuse to overwrite evidence or reuse an unknown profile.
            for key in ['config','data','cache','state','runtime']: (case/key).mkdir(mode=0o700)
            instrument(case,platform)
            runtime=tempfile.TemporaryDirectory(prefix='opm-plasma-')
            (case/'runtime-path.txt').write_text(runtime.name)
            env={**os.environ,'XDG_CONFIG_HOME':str(case/'config'),'XDG_DATA_HOME':str(case/'data'),
                 'XDG_CACHE_HOME':str(case/'cache'),'XDG_STATE_HOME':str(case/'state'),'XDG_RUNTIME_DIR':runtime.name,
                 'DISPLAY':'','WAYLAND_DISPLAY':'opm-startup-test','QT_QPA_PLATFORM':platform,
                 'QT_QUICK_BACKEND':'software','KWIN_COMPOSE':'Q','KDE_FULL_SESSION':'true','KDE_SESSION_VERSION':'6',
                 'OPM_MENU_DELAY':str(menu_delay),'OPM_PREF_DELAY':str(pref_delay),
                 'OPM_ICON_SIZE':'standard' if name=='slow-menu' else 'large',
                 'OPM_CUSTOM_HEIGHT':'600' if name=='slow-menu' else '460',
                 'OPM_HEIGHT_MODE':mode,'OPM_DENSITY':density,'OPM_APPEARANCE':theme}
            with (case/'session.log').open('w') as log:
                process=subprocess.Popen(['dbus-run-session','--',sys.executable,str(SCRIPT),'--session','--output',str(case),
                    '--platform',platform,'--panel-edge',edge,'--width',str(width),'--height',str(height),'--scale',str(scale),'--outputs',str(outputs)],
                    env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:
                    result=process.wait(timeout=90)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGTERM)
                    process.wait(timeout=10)
                    raise
            runtime.cleanup()
            if result != 0:
                # Failed Docker RUN layers are not downloadable artifacts. Keep
                # useful fixture diagnostics in the CI log itself.
                for filename in ['session.log','kwin.log','backend.jsonl']:
                    path=case/filename
                    if path.exists():
                        print(f'{case.name}/{filename}:',flush=True)
                        print('\n'.join(path.read_text(errors='replace').splitlines()[-40:]),flush=True)
                for phase in ['fresh','shell-restart']:
                    print(phase,json.dumps(read_states(case/f'{phase}.log')[-12:]),flush=True)
            assert result==0, f'{case}: see diagnostics above and session.log'
            print('PASS',case.name,flush=True)


if __name__=='__main__':
    os.umask(0o077)
    main()
