#!/usr/bin/env python3
"""X11 popup crossing regression in a disposable Plasma profile/display/bus.

Requires the editor.Dockerfile build dependencies plus xterm. No session restart,
existing panel changes, global shortcut assignment or action execution. Run with
--output NEW_DIR and optionally --standalone /path/to/open-power-menu-standalone.
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from plasma_startup import wait_for, install_test_input_module

ENTRIES = [
    {'kind': 'command', 'key': 'enabled', 'title': 'Enabled', 'enabled': True},
    {'kind': 'command', 'key': 'disabled', 'title': 'Disabled', 'enabled': False},
    {'kind': 'separator'},
    {'kind': 'command', 'key': 'search', 'title': 'Search', 'enabled': True},
    {'kind': 'command', 'key': 'run', 'title': 'Run', 'enabled': True},
    {'kind': 'submenu', 'key': 'flyout', 'title': 'Flyout', 'enabled': True,
     'items': [{'kind': 'command', 'key': 'child', 'title': 'Child', 'enabled': True},
               {'kind': 'command', 'key': 'unavailable', 'title': 'Unavailable', 'enabled': False},
               {'kind': 'separator'}]},
]


def backend(hidden):
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtDBus import QDBusConnection, QDBusVirtualObject
    app = QCoreApplication([])
    bus = QDBusConnection.sessionBus()
    class Backend(QDBusVirtualObject):
        def introspect(self, path):
            return ''
        def handleMessage(self, msg, connection):
            name = msg.member()
            print(name, flush=True)
            values = {'GetMenu': json.dumps(ENTRIES + ([{'kind':'command','key':'desktop','title':'Desktop','enabled':True}] if os.environ.get('OPM_DISMISSAL_REGRESSION') else [])), 'PowerCapabilitiesPending': False,
                      'GetIntegration': json.dumps({'auto_close_on_pointer_leave': False,
                          'hide_original_launcher': hidden, 'launcher_applet_id': 3})}
            if name not in values:
                connection.send(msg.createErrorReply('org.test.Refused', 'No actions in this fixture'))
            else:
                connection.send(msg.createReply([values[name]]))
            return True
    service = Backend()
    assert bus.registerService('org.openpowermenu.Service')
    assert bus.registerVirtualObject('/OpenPowerMenu', service)
    app.exec()


def traces(path):
    result = []
    for line in path.read_text(errors='replace').splitlines():
        if 'OPM_POPUP_TRACE ' in line:
            try:
                result.append(json.loads(line.split('OPM_POPUP_TRACE ', 1)[1]))
            except json.JSONDecodeError:
                pass  # a concurrent writer may not have finished the final line
    return result


def prepare(case, diagnostics=True):
    for name in ('config', 'data', 'cache', 'state', 'runtime'):
        (case/name).mkdir(mode=0o700)
    widget = case/'data/plasma/plasmoids/org.openpowermenu.start'
    shutil.copytree(ROOT/'plasmoid', widget)
    install_test_input_module(widget)
    path = widget/'contents/ui/main.qml'
    source = path.read_text().replace(
        'Qt.callLater(() => root.initializeDefaultShortcut());',
        'popupTrace.record("fixture-ready");')
    # Read-only coordinates in the isolated copy; product traces have no timers.
    source = source.replace('activeIndex: activeIndex};', '''activeIndex: activeIndex,
                rows: Array.from({length:normalRows.count}, (_, i) => {
                    const row=normalRows.itemAt(i), p=row.mapToGlobal(row.width/2,row.height/2);
                    return {kind:row.entry.kind,key:row.entry.key,point:[p.x,p.y]};
                })};''')
    source = source.replace('widget: Plasmoid.id, platform:', '''button: root.compactRepresentationItem ?
            root.compactRepresentationItem.mapToGlobal(root.compactRepresentationItem.width/2,
                root.compactRepresentationItem.height/2) : null,
            widget: Plasmoid.id, platform:''')
    source = source.replace('    property var menuEntries: []', '''    Timer {
        interval: 100; repeat: true; running: true
        onTriggered: console.info("OPM_POPUP_TRACE", JSON.stringify({
            callback:"fixture-sample", state:root.popupTraceState()}))
    }
    property var menuEntries: []''')
    path.write_text(source)
    # Seed a private panel before the first shell start; never rewrite a live panel.
    (case/'config/plasma-org.kde.plasma.desktop-appletsrc').write_text('''[Containments][1]
activityId=
formfactor=0
lastScreen=0
location=0
plugin=org.kde.plasma.folder
wallpaperplugin=org.kde.image

[Containments][2]
activityId=
formfactor=2
lastScreen=0
location=4
plugin=org.kde.panel

[Containments][2][General]
AppletOrder=3;4

[Containments][2][Applets][3]
plugin=org.kde.plasma.kickoff

[Containments][2][Applets][4]
plugin=org.openpowermenu.start

[Containments][2][Applets][4][Configuration][General]
opmDefaultShortcutTried=true
popupDiagnostics=true
'''.replace('popupDiagnostics=true', 'popupDiagnostics='+str(diagnostics).lower()))


def session(args):
    case = Path(args.output)
    processes, files = [], []
    def spawn(command, name):
        out = (case/name).open('w'); files.append(out)
        p = subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT)
        processes.append(p)
        return p
    def command(*args):
        return subprocess.check_output(args, text=True).strip()
    def move(point):
        command('xdotool', 'mousemove', *[str(round(v*args.scale)) for v in point])
        time.sleep(.3)
        print(json.dumps({'time_ms': time.time()*1000, 'pointer': point,
            'active': command('xprop', '-root', '_NET_ACTIVE_WINDOW')}), flush=True)
    log = case/'plasma.log'
    def state():
        records = traces(log)
        return records[-1]['state'] if records else None
    def assert_open(label):
        s = state()
        assert s['expanded'] and s['popup']['window']['visible'], (label, s)
        assert not s['autoClose'] and not s['popup']['dismissal']['pending'], s
        assert s['hideOriginalLauncher'] == args.hidden and s['maskActive'] == args.hidden, s
    try:
        read_fd, write_fd = os.pipe()
        out = (case/'display.log').open('w'); files.append(out)
        p = subprocess.Popen(['Xvfb', '-displayfd', str(write_fd), '-screen', '0', f'{round(1280*args.scale)}x{round(800*args.scale)}x24', '-nolisten', 'tcp'],
                             stdout=out, stderr=subprocess.STDOUT, pass_fds=(write_fd,))
        processes.append(p); os.close(write_fd)
        assert select.select([read_fd], [], [], 10)[0]
        os.environ['DISPLAY'] = ':'+os.read(read_fd, 64).decode().strip(); os.close(read_fd)
        command('dbus-update-activation-environment', 'DISPLAY')
        spawn(['kwin_x11'], 'kwin.log')
        if args.dismissal:
            spawn(['/usr/lib/x86_64-linux-gnu/libexec/kglobalacceld'], 'shortcuts.log')
        spawn([sys.executable, __file__, '--backend'] + (['--hidden'] if args.hidden else []), 'backend.log')
        shell = spawn(['plasmashell', '--no-respawn'], 'plasma.log')
        wait_for(lambda: log.exists() and state() and state().get('button'), timeout=30)
        background = spawn(['xterm', '-title', 'OPM background application', '-geometry', '100x30+150+80'], 'application.log')
        def background_window():
            assert background.poll() is None, (case/'application.log').read_text()
            # Ubuntu's interactive shell rewrites the title after xterm maps.
            # Match the process we launched, independently of shell prompt timing.
            return subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(background.pid)],
                                  capture_output=True, text=True).stdout.strip()
        app_id = wait_for(background_window)
        if args.dismissal:
            from plasma_dismissal import exercise
            exercise(args, case, spawn, command, move, state, log, shell, app_id)
            return
        for opening in range(3):
            command('xdotool', 'windowactivate', '--sync', app_id)
            assert command('xdotool', 'getactivewindow') == app_id
            button = state()['button']
            move([button['x'], button['y']]); command('xdotool', 'click', '3')
            wait_for(lambda: state()['expanded'] and state()['popup'] and len(state()['popup'].get('rows', [])) == 6)
            time.sleep(.5)
            rows = state()['popup']['rows']
            for index in (0, 1, 2, 3, 4, 2, 1, 0, 5):
                move(rows[index]['point']); assert_open(f'opening {opening}, row {index}')
            wait_for(lambda: state()['popup']['flyout']['window']['visible'])
            fw = state()['popup']['flyout']['window']['geometry']
            for fraction in (.25, .55, .85):
                move([fw[0]+fw[2]/2, fw[1]+fw[3]*fraction]); assert_open('flyout')
            with (case/f'x11-windows-{opening}.log').open('w') as native_log:
                native_log.write(command('xprop', '-root', '_NET_ACTIVE_WINDOW')+'\n')
                windows = {}
                for wid in command('xdotool', 'search', '--onlyvisible', '--pid', str(shell.pid)).splitlines():
                    windows[wid] = command('xprop', '-id', wid, 'WM_TRANSIENT_FOR',
                        'WM_HINTS', 'WM_PROTOCOLS', '_NET_WM_WINDOW_TYPE')
                    native_log.write(wid+'\n'+windows[wid]+'\n')
                parent_id = next(wid for wid, props in windows.items()
                                 if '_KDE_NET_WM_WINDOW_TYPE_APPLET_POPUP' in props)
                child = next(props for props in windows.values() if '_NET_WM_WINDOW_TYPE_UTILITY' in props)
                assert 'WM_TRANSIENT_FOR(WINDOW): window id # '+hex(int(parent_id)) in child, child
            for index in (1, 2, (0, 3, 4)[opening], 4, 3, 2, 1, 0):
                move(rows[index]['point']); assert_open(f'return row {index}')
            # Hovering outside must not dismiss; only the intentional click does.
            move([1000, 100]); assert_open('outside without click')
            command('xdotool', 'click', '1')
            wait_for(lambda: not state()['expanded'])
            if not args.diagnostics_off:
                latest = [r for r in traces(log) if r['callback'] == 'root.expandedChanged'][-1]
                assert latest['details']['origin'] == 'external-to-opm', latest
        # Keyboard-opened flyouts still accept focus; Left/Escape close only
        # the child/parent requested, without activating any command.
        command('xdotool', 'windowactivate', '--sync', app_id)
        button = state()['button']; move([button['x'], button['y']])
        command('xdotool', 'click', '3'); wait_for(lambda: state()['expanded'])
        command('xdotool', 'key', 'Up', 'Right')
        wait_for(lambda: state()['popup']['flyout']['window']['visible'])
        assert not state()['popup']['flyout']['window']['flags'] & 0x200000
        command('xdotool', 'key', 'Left'); time.sleep(.3); assert_open('keyboard return')
        command('xdotool', 'key', 'Escape'); wait_for(lambda: not state()['expanded'])
        if args.diagnostics_off:
            assert all(r['callback'] == 'fixture-sample' for r in traces(log))
        if args.standalone:
            # Independent native QMenu on the same WM with the same active xterm.
            cfg = {'auto_close_on_pointer_leave': False, 'show_unavailable': True,
                   'menu': [{'label': 'Enabled', 'command': ['/bin/true']},
                            {'label': 'Disabled', 'command': ['/opm-unavailable']},
                            {'separator': True},
                            {'label': 'Search', 'command': ['/bin/true']},
                            {'label': 'Run', 'command': ['/bin/true']},
                            {'submenu': 'Flyout', 'items': [{'label': 'Child', 'command': ['/bin/true']}]}]}
            (case/'standalone.json').write_text(json.dumps(cfg))
            command('xdotool', 'windowactivate', '--sync', app_id)
            move([400, 400])
            native = spawn([args.standalone, '--config', str(case/'standalone.json'), '--diagnose-launch'], 'standalone.log')
            menu_id = wait_for(lambda: subprocess.run(['xdotool', 'search', '--onlyvisible', '--name', '^Open Power Menu$'],
                              capture_output=True, text=True).stdout.strip())
            geom = dict(line.split('=', 1) for line in command('xdotool', 'getwindowgeometry', '--shell', menu_id).splitlines())
            x, y, w, h = [int(geom[k]) for k in ('X', 'Y', 'WIDTH', 'HEIGHT')]
            for cy in list(range(y+5, y+h-5, 4)) + list(range(y+h-5, y+4, -4)):
                move([x+w/2, cy]); assert native.poll() is None, 'Native collapsed during traversal'
            move([1000, 100]); assert native.poll() is None
            command('xdotool', 'click', '1'); native.wait(timeout=5)
            assert native.returncode == 0
        requests = (case/'backend.log').read_text().splitlines()
        assert set(requests) <= {'GetMenu', 'GetIntegration', 'PowerCapabilitiesPending'}, requests
        print('PASS X11 application + crossings + outside click; launcher hidden:', args.hidden, flush=True)
    finally:
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
                try: p.wait(timeout=5)
                except subprocess.TimeoutExpired: p.kill(); p.wait()
        for f in files: f.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='work/plasma-popup')
    parser.add_argument('--session', action='store_true')
    parser.add_argument('--backend', action='store_true')
    parser.add_argument('--hidden', action='store_true')
    parser.add_argument('--standalone')
    parser.add_argument('--diagnostics-off', action='store_true')
    parser.add_argument('--scale',type=float,default=1)
    parser.add_argument('--dismissal', action='store_true', help='Run root/flyout dismissal lifecycle checks')
    args = parser.parse_args()
    if args.backend: return backend(args.hidden)
    if args.session: return session(args)
    output = Path(args.output).resolve(); output.mkdir(parents=True)
    for hidden in (False, True):
        case = output/('hidden' if hidden else 'visible'); case.mkdir(); prepare(case, diagnostics=not args.diagnostics_off)
        if args.dismissal:
            # Private seat only: keep KWin compositing and slide/blur effects on.
            (case/'config/plasmarc').write_text('[Theme]\nname=breeze-dark\n')
            (case/'config/kwinrc').write_text('[Compositing]\nEnabled=true\nBackend=OpenGL\nGLCore=true\n[Plugins]\nslidingpopupsEnabled=true\nblurEnabled=true\ncontrastEnabled=true\n')
        with tempfile.TemporaryDirectory(prefix='opm-popup-') as runtime:
            env = {**os.environ, 'XDG_RUNTIME_DIR': runtime, 'DISPLAY': '', 'WAYLAND_DISPLAY': '',
                   'QT_FORCE_STDERR_LOGGING': '1',
                   'QT_QPA_PLATFORM': 'xcb', 'QT_SCALE_FACTOR': str(args.scale), 'QT_QUICK_BACKEND': 'software', 'KDE_FULL_SESSION': 'true',
                   'KDE_SESSION_VERSION': '6'}
            if args.dismissal:
                env['OPM_DISMISSAL_REGRESSION'] = '1'
                env['KWIN_EFFECTS_FORCE_ANIMATIONS'] = '1'
            env.update({f'XDG_{key.upper()}_HOME': str(case/key) for key in ('config', 'data', 'cache', 'state')})
            with (case/'session.log').open('w') as log:
                run = subprocess.run(['dbus-run-session', '--', sys.executable, __file__, '--session', '--output', str(case), '--scale', str(args.scale)]
                    + (['--hidden'] if hidden else []) + (['--dismissal'] if args.dismissal else []) + (['--diagnostics-off'] if args.diagnostics_off else []) + (['--standalone', args.standalone] if args.standalone else []),
                    env=env, stdout=log, stderr=subprocess.STDOUT, timeout=240)
            assert run.returncode == 0, (case/'session.log').read_text()
        print('PASS', case, flush=True)


if __name__ == '__main__':
    main()
