"""Read-only power responsiveness experiment on an owned, private D-Bus.

Requires PySide6 as test tooling. Fake services accept only capability reads;
no power action can run. Reports observations rather than speed thresholds.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time


def fixture(mode, delay):
    from PySide6.QtCore import QCoreApplication, QTimer
    from PySide6.QtDBus import QDBusConnection, QDBusVirtualObject

    class Capabilities(QDBusVirtualObject):
        def introspect(self, path):
            return ''

        def handleMessage(self, message, connection):
            if message.member() not in ('CanSuspend', 'CanHibernate', 'HasInhibit'):
                connection.send(message.createErrorReply('org.test.Refused', 'Only capability reads permitted'))
                return True
            value = (False if message.member() == 'HasInhibit' else
                     'yes' if message.interface().endswith('.Manager') else True)
            if mode != 'unresponsive':
                QTimer.singleShot(delay, lambda: connection.send(message.createReply(value)))
            return True

    app = QCoreApplication([])
    bus = QDBusConnection.sessionBus()
    fake = Capabilities()
    assert bus.registerService('org.freedesktop.PowerManagement')
    assert bus.registerService('org.freedesktop.login1')
    for path in ('/org/freedesktop/PowerManagement', '/org/freedesktop/PowerManagement/Inhibit', '/org/freedesktop/login1'):
        assert bus.registerVirtualObject(path, fake)
    print('ready', flush=True)
    app.exec()


def benchmark(binary, output):
    reports = []
    with tempfile.TemporaryDirectory(prefix='opm-power-latency-') as directory:
        root = Path(directory)
        env = dict(os.environ)
        for key in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_RUNTIME_DIR'):
            path = root / key
            path.mkdir(mode=0o700)
            env[key] = str(path)
        bus = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address=1'],
                               stdout=subprocess.PIPE, text=True, env=env)
        try:
            address = bus.stdout.readline().strip()
            env.update(DBUS_SESSION_BUS_ADDRESS=address, DBUS_SYSTEM_BUS_ADDRESS=address)
            config = root / 'menu.json'
            config.write_text(json.dumps({'show_unavailable': True, 'menu': [{'action': 'sleep'}, {'action': 'hibernate'}]}))
            for mode, delay in [('healthy', 0), ('slow', 300), ('missing', 0), ('unresponsive', 0)]:
                fake = server = None
                try:
                    if mode != 'missing':
                        fake = subprocess.Popen([sys.executable, __file__, '--fixture', mode, str(delay)],
                                                env=env, stdout=subprocess.PIPE, text=True)
                        if fake.stdout.readline().strip() != 'ready':
                            raise RuntimeError('Capability fixture did not start')
                    server = subprocess.Popen([str(binary), '--config', str(config), '--service'],
                                              env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    def call(method):
                        return subprocess.run([str(binary), '--call', method], env=env,
                                              capture_output=True, text=True, timeout=15, check=True).stdout

                    deadline = time.monotonic() + 5
                    while True:
                        try:
                            call('Ping')
                            break
                        except subprocess.CalledProcessError:
                            if server.poll() is not None or time.monotonic() > deadline:
                                raise RuntimeError('Backend did not start')
                            time.sleep(.01)
                    timings = []
                    for _ in range(3):
                        start = time.monotonic_ns()
                        menu = json.loads(call('GetMenu'))
                        timings.append(round((time.monotonic_ns() - start) / 1e6, 3))
                    # Let the asynchronous generation settle, then inspect policy.
                    time.sleep(1.7)
                    settled = json.loads(call('GetMenu'))
                    expected = mode in ('healthy', 'slow')
                    if any(item['enabled'] != expected for item in settled):
                        raise RuntimeError(f'{mode}: unexpected capability result: {settled}')
                    reports.append({'mode': mode, 'per_reply_delay_ms': delay,
                                    'GetMenu_roundtrip_ms': timings,
                                    'median_ms': statistics.median(timings),
                                    'initial_presentation': menu, 'settled_presentation': settled})
                finally:
                    for process in (server, fake):
                        if process is not None:
                            process.terminate()
                            process.wait(timeout=5)
                            if process.stdout:
                                process.stdout.close()
        finally:
            bus.terminate()
            bus.wait(timeout=5)
            bus.stdout.close()
    result = {'binary': str(binary), 'method': 'Three GetMenu round trips per service scenario, including fresh CLI IPC client overhead; private session/system fixture bus; no power actions.', 'scenarios': reports}
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps([{key: row[key] for key in ('mode', 'GetMenu_roundtrip_ms')} for row in reports], indent=2))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--fixture':
        fixture(sys.argv[2], int(sys.argv[3]))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--binary', type=Path, required=True)
        parser.add_argument('--output', type=Path, required=True)
        args = parser.parse_args()
        benchmark(args.binary.resolve(), args.output)
