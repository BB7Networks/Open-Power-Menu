#!/usr/bin/env python3
"""Real KDE logout greeter on a private display and an allowlisted private bus.

The bus has NO system service directories. org.kde.Shutdown activates only our
recorder, and logind/PowerManagement are recorders on BOTH private bus addresses.
No installer, host desktop, host service or real power operation is used.
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
from xml.sax.saxutils import escape
from fixture_evidence import Evidence
import private_greeter_wayland
from private_compositor import active as compositor_active

SCRIPT = Path(__file__).resolve()


def wait_for(check, timeout=15):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.025)
    raise AssertionError('Timed out waiting for private greeter fixture')


def recorder(shutdown):
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtDBus import QDBusConnection, QDBusVirtualObject
    app = QCoreApplication([])
    bus = QDBusConnection.sessionBus()
    class Recorder(QDBusVirtualObject):
        def introspect(self, path):
            return ''
        def handleMessage(self, msg, connection):
            member = msg.member()
            if member in ('logoutAndShutdown', 'logoutAndReboot', 'logout', 'Suspend',
                          'Hibernate', 'SuspendWithFlags', 'HibernateWithFlags',
                          'PowerOff', 'Reboot', 'PowerOffWithFlags', 'RebootWithFlags'):
                with open(os.environ['OPM_POWER_RECORD'], 'a') as output:
                    output.write(json.dumps({'time': time.monotonic(), 'member': member,
                                             'interface': msg.interface()})+'\n')
                connection.send(msg.createReply())
            elif member.startswith('Can'):
                connection.send(msg.createReply('yes' if msg.interface() == 'org.freedesktop.login1.Manager' else True))
            elif member == 'HasInhibit':
                connection.send(msg.createReply(False))
            else:
                connection.send(msg.createErrorReply('org.test.Refused', 'Private mock; never forwarded'))
            return True
    mock = Recorder()
    names = ['org.kde.Shutdown'] if shutdown else ['org.freedesktop.login1', 'org.freedesktop.PowerManagement']
    paths = ['/Shutdown'] if shutdown else ['/org/freedesktop/login1', '/org/freedesktop/PowerManagement', '/org/freedesktop/PowerManagement/Inhibit']
    for name in names:
        assert bus.registerService(name), name
    for path in paths:
        assert bus.registerVirtualObject(path, mock), path
    print('SAFE_RECORDER_READY', flush=True)
    app.exec()


def session(args):
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtDBus import QDBusConnection, QDBusMessage
    app = QCoreApplication([])
    os.environ['DBUS_SYSTEM_BUS_ADDRESS'] = os.environ['DBUS_SESSION_BUS_ADDRESS']
    bus = QDBusConnection.sessionBus()
    case = Path(args.output)
    evidence=Evidence(case,args.platform)
    processes, logs = [], []
    def spawn(command, name, env=None):
        log = (case/name).open('w'); logs.append(log)
        child = subprocess.Popen(list(map(str, command)), stdout=log, stderr=log, env=env)
        processes.append(child)
        return child
    def call(member, *values):
        message = QDBusMessage.createMethodCall('org.openpowermenu.Service', '/OpenPowerMenu', 'org.openpowermenu.Service', member)
        message.setArguments(list(values))
        reply = bus.call(message)
        assert reply.type() == QDBusMessage.ReplyMessage, reply.errorMessage()
        return reply.arguments()[0]
    def records():
        path = case/'requests.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    def windows():
        if args.platform=='wayland': return private_greeter_wayland.windows(case)
        result = subprocess.run(['xdotool', 'search', '--onlyvisible', '--class', 'ksmserver-logout-greeter'], capture_output=True, text=True)
        return result.stdout.split()
    try:
        if args.platform=='xcb':
            read, write = os.pipe()
            log = (case/'display.log').open('w'); logs.append(log)
            display = subprocess.Popen(['Xvfb', '-screen', '0', '1280x800x24', '-displayfd', str(write), '-nolisten', 'tcp'], pass_fds=(write,), stdout=log, stderr=log)
            processes.append(display); os.close(write)
            assert select.select([read], [], [], 10)[0]
            os.environ['DISPLAY'] = ':'+os.read(read, 64).decode().strip(); os.close(read)
            spawn(['kwin_x11'], 'kwin.log')
        else:
            binary=case/'kwin_wayland';shutil.copyfile(shutil.which('kwin_wayland'),binary);binary.chmod(0o700)
            compositor=spawn([binary,'--virtual','--width','1280','--height','800','--no-lockscreen',
                   '--no-global-shortcuts','--socket',os.environ['WAYLAND_DISPLAY']],'kwin.log',
                  {**os.environ,'KWIN_WAYLAND_NO_PERMISSION_CHECKS':'1'})
            wait_for(lambda:(Path(os.environ['XDG_RUNTIME_DIR'])/os.environ['WAYLAND_DISPLAY']).is_socket())
            wait_for(lambda:compositor_active(compositor))
        subprocess.run(['dbus-update-activation-environment', 'DISPLAY', 'WAYLAND_DISPLAY', 'DBUS_SYSTEM_BUS_ADDRESS', 'QT_QPA_PLATFORM', 'QT_QUICK_BACKEND', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_RUNTIME_DIR', 'XDG_CURRENT_DESKTOP', 'OPM_POWER_RECORD'], check=True)
        spawn([sys.executable, SCRIPT, '--recorder'], 'policy.log')
        wait_for(lambda: 'SAFE_RECORDER_READY' in (case/'policy.log').read_text())
        wait_for(lambda: bus.interface().isServiceRegistered('org.kde.KWin').value())
        if args.platform=='wayland': private_greeter_wayland.observe(case)
        spawn(['plasmashell', '--no-respawn'], 'plasma.log')
        config = case/'config/open-power-menu/menu.json'; config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text('{"menu":[]}')
        spawn([args.backend, '--service', '--bus-name', 'org.openpowermenu.Service'], 'backend.log')
        wait_for(lambda: bus.interface().isServiceRegistered('org.openpowermenu.Service').value())
        report = []
        defaults = json.loads(subprocess.check_output([args.backend, '--default-config'], text=True))
        modes = ('system', 'always', 'immediate') if 'power_confirmation' in defaults else ('always', 'immediate')
        cases = [(mode, kde, action, mode == 'always' or (mode == 'system' and kde), False)
                 for mode in modes for kde in (False, True) for action in ('shutdown', 'reboot', 'logout')]
        # KDE 6.7 refuses a greeter while Shutdown owns its name. Leave the mock
        # activatable until the countdown case; immediate requests follow it.
        cases = [case for case in cases if case[3]] + [('always', True, 'shutdown', True, True)] + [case for case in cases if not case[3]]
        for mode, kde, action, confirm, countdown in cases:
            evidence.begin(f'{args.platform}-{mode}-{action}-kde{kde}-countdown{countdown}')
            config_value = {'menu': [{'action': action}], 'confirm_power_actions': confirm}
            if 'power_confirmation' in defaults: config_value['power_confirmation'] = mode
            config.write_text(json.dumps(config_value))
            (case/'config/ksmserverrc').write_text('[General]\nconfirmLogout='+str(kde).lower()+'\n')
            def menu():
                rows = json.loads(call('GetMenu'))
                return rows if rows and rows[0].get('enabled') else None
            rows = wait_for(menu)
            integration = json.loads(call('GetIntegration'))
            assert integration['confirm_power_actions'] == confirm
            before = len(records()); began = time.monotonic()
            started = json.loads(call('StartRun', rows[0]['key']))
            def finished():
                app.processEvents()
                result = json.loads(call('RunResult', started['operation']))
                return result if result['state'] == 'finished' else None
            result = wait_for(finished)
            assert result['ok'], result
            if confirm:
                wait_for(windows)
                # Observe native presentation, without requesting focus.
                time.sleep(2)
                assert windows(), 'Greeter disappeared before cancellation'
                assert len(records()) == before, 'Confirmation executed before cancellation'
                if args.platform=='xcb':
                    subprocess.run([sys.executable, SCRIPT, '--screenshot', str(case/(mode+'-'+action+'-kde'+str(kde)+'.png'))], check=True)
                else:
                    # Wayland disallows another client's QScreen.grabWindow.
                    # Retain the compositor's real mapped-window/geometry proof.
                    shown=windows()
                    assert all(w['geometry'][2]>0 and w['geometry'][3]>0 for w in shown), shown
                    evidence.record('native-greeter-visible',windows=shown)
                if countdown:
                    wait_for(lambda: len(records()) == before+1, 40)
                    assert time.monotonic()-began >= 25, 'Stock KDE countdown completed unexpectedly early'
                    assert records()[-1]['member'] == 'logoutAndShutdown'
                else:
                    if args.platform=='xcb': subprocess.run(['xdotool', 'key', 'Escape'], check=True)
                    else: private_greeter_wayland.escape()
                wait_for(lambda: not windows())
                wait_for(lambda: not bus.interface().isServiceRegistered('org.kde.LogoutPrompt').value())
                assert len(records()) == before+int(countdown)
            else:
                wait_for(lambda: len(records()) == before+1)
                assert records()[-1]['member'] == {'shutdown': 'logoutAndShutdown', 'reboot': 'logoutAndReboot', 'logout': 'logout'}[action]
                assert not windows()
            report.append({'platform':args.platform,'action': action, 'mode': mode, 'confirm': confirm, 'kde_confirm': kde,
                           'countdown': countdown, 'elapsed': time.monotonic()-began, 'visible': confirm, 'result': result})
        (case/'results.json').write_text(json.dumps(report, indent=2)+'\n')
        if args.platform=='wayland':assert compositor_active(compositor)
        print('PASS: real greeter, native countdown and private immediate routes:', len(report), 'cases.', flush=True)
    except BaseException:
        evidence.failure(processes,requests=records(),windows=windows())
        raise
    finally:
        evidence.record('teardown-begin')
        for child in reversed(processes):
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired: child.kill(); child.wait()
        for log in logs: log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend'); parser.add_argument('--output')
    parser.add_argument('--platform',choices=['xcb','wayland'],default='xcb')
    parser.add_argument('--session', action='store_true'); parser.add_argument('--recorder', action='store_true')
    parser.add_argument('--shutdown', action='store_true'); parser.add_argument('--screenshot')
    args = parser.parse_args()
    if args.recorder: return recorder(args.shutdown)
    if args.screenshot:
        from PySide6.QtGui import QGuiApplication
        app = QGuiApplication([])
        assert app.primaryScreen().grabWindow(0).save(args.screenshot)
        return
    if args.session: return session(args)
    case = Path(args.output).resolve(); case.mkdir(parents=True)
    for folder in ('config', 'data', 'cache', 'state', 'home', 'services'):
        (case/folder).mkdir()
    greeter = next(line.removeprefix('Exec=') for line in Path('/usr/share/dbus-1/services/org.kde.LogoutPrompt.service').read_text().splitlines() if line.startswith('Exec='))
    (case/'services/org.kde.LogoutPrompt.service').write_text('[D-BUS Service]\nName=org.kde.LogoutPrompt\nExec='+greeter+'\n')
    (case/'services/org.kde.Shutdown.service').write_text('[D-BUS Service]\nName=org.kde.Shutdown\nExec='+sys.executable+' '+str(SCRIPT)+' --recorder --shutdown\n')
    bus_config = case/'bus.conf'
    bus_config.write_text('<busconfig><type>session</type><listen>unix:tmpdir=/tmp</listen><auth>EXTERNAL</auth><servicedir>'+escape(str(case/'services'))+'</servicedir><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
    with tempfile.TemporaryDirectory(prefix='opm-greeter-') as runtime:
        (Path(runtime)/'.opm-private-greeter').write_text('private mocked greeter\n')
        env = {**os.environ, 'HOME': str(case/'home'), 'DISPLAY': '', 'WAYLAND_DISPLAY': 'opm-greeter-test' if args.platform=='wayland' else '', 'XDG_RUNTIME_DIR': runtime,
               'QT_QPA_PLATFORM': args.platform, 'QT_QUICK_BACKEND': 'software', 'QT_FORCE_STDERR_LOGGING': '1',
               'XDG_CURRENT_DESKTOP': 'KDE', 'KDE_FULL_SESSION': 'true', 'KDE_SESSION_VERSION': '6',
               'OPM_POWER_RECORD': str(case/'requests.jsonl')}
        env.pop('KWIN_COMPOSE', None)
        if args.platform=='wayland': env['KWIN_COMPOSE']=os.environ.get('OPM_TEST_KWIN_COMPOSE','Q')
        env.update({f'XDG_{key.upper()}_HOME': str(case/key) for key in ('config', 'data', 'cache', 'state')})
        with (case/'session.log').open('w') as log:
            run = subprocess.run(['dbus-run-session', '--config-file', bus_config, '--', sys.executable, SCRIPT,
                                  '--session', '--platform',args.platform,'--backend', args.backend, '--output', case], env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        if run.returncode:
            print((case/'session.log').read_text(), file=sys.stderr)
            raise AssertionError('Private real-greeter qualification failed: '+str(case))
    print('PASS', case)


if __name__ == '__main__': main()
