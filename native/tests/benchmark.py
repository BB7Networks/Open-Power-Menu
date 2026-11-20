"""Developer benchmark: run on a private bus with system PySide6 as test tooling.

Reports observations, never asserts a speedup. Native processes do not load
Python. GUI rendering and physical menu activation are not timing measurements.
"""
import argparse
from contextlib import contextmanager
import json
import hashlib
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

from PySide6.QtCore import QCoreApplication, qVersion
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

parser = argparse.ArgumentParser()
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--editor', type=Path, required=True)
parser.add_argument('--legacy-root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--native-revision', default='unspecified')
parser.add_argument('--baseline-revision', default='unspecified')
args = parser.parse_args()
sys.path.insert(0, str(args.legacy_root))
from openpowermenu.core import DEFAULT_CONFIG, COMMANDS

app = QCoreApplication([])
if 'DBUS_SESSION_BUS_ADDRESS' not in os.environ:
    raise SystemExit('Run this benchmark with dbus-run-session, never on a desktop bus')


def distribution(values):
    ordered = sorted(values)
    return {'median_ms': round(statistics.median(values), 3),
            'p95_ms': round(ordered[min(len(values) - 1, int(len(values) * .95))], 3),
            'samples': len(values)}


def memory(pid):
    values = {}
    for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
        parts = line.split()
        if parts[0] in ('Rss:', 'Pss:', 'Private_Clean:', 'Private_Dirty:'):
            values[parts[0][:-1] + '_KiB'] = int(parts[1])
    return values


def mapped_memory(pid):
    groups = {}
    group = 'anonymous'
    for line in Path(f'/proc/{pid}/smaps').read_text().splitlines():
        parts = line.split()
        if '-' in parts[0] and len(parts) >= 5:
            path = ' '.join(parts[5:])
            if not path or path.startswith('['):
                group = 'anonymous'
            elif any(name in path for name in ('libQt6Qml', 'libQt6Quick', 'libKF6', '/qt6/qml/')):
                group = 'Qt_Quick_Qml_KDE_files'
            elif any(name in path for name in ('libpython', '/PySide6/', '/shiboken6/')):
                group = 'Python_PySide_files'
            else:
                group = 'other_files'
        elif parts[0] in ('Rss:', 'Pss:'):
            category = groups.setdefault(group, {'Rss_KiB': 0, 'Pss_KiB': 0})
            category[parts[0][:-1] + '_KiB'] += int(parts[1])
    return groups


with tempfile.TemporaryDirectory(prefix='opm-benchmark-') as directory:
    root = Path(directory)
    tools = root / 'tools'
    tools.mkdir()
    for spec in COMMANDS.values():
        for candidate in spec['commands']:
            program = (candidate['argv'] if isinstance(candidate, dict) else candidate)[0]
            if '/' in program:
                continue
            path = tools / program
            path.write_text('#!/bin/sh\nexit 0\n')
            path.chmod(0o755)
    (tools / 'qdbus6').write_text('#!/bin/sh\nprintf "Show Desktop\\n"\n')
    (tools / 'kcmshell6').write_text('#!/bin/sh\nprintf "kcm_printer_manager\\nkcm_powerdevilprofilesconfig\\n"\n')
    env = {**os.environ, 'XDG_CONFIG_HOME': str(root / 'config'),
           'XDG_DATA_HOME': str(root / 'data'), 'XDG_CACHE_HOME': str(root / 'cache'),
           'XDG_CURRENT_DESKTOP': 'KDE', 'XDG_MENU_PREFIX': 'plasma-',
           'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
           'PATH': str(tools) + os.pathsep + os.defpath}
    config = root / 'config/open-power-menu/menu.json'
    config.parent.mkdir(parents=True)
    env['XDG_RUNTIME_DIR'] = str(root / 'runtime')
    Path(env['XDG_RUNTIME_DIR']).mkdir(mode=0o700)
    legacy = [sys.executable, str(args.legacy_root / 'run.py')]
    native = [str(args.native)]

    @contextmanager
    def child(command):
        with (root / 'process.log').open('wb') as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=log)
            try:
                yield process
            finally:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=5)

    result = {'environment': {'platform': platform.platform(), 'qt': qVersion(),
                             'python_test_client': platform.python_version(),
                             'legacy_version': subprocess.check_output(legacy + ['--version'], env=env, text=True).strip(),
                             'native_version': subprocess.check_output(native + ['--version'], text=True).strip()},
              'method': 'Same container, private D-Bus, fake availability tools, software rendering; warm filesystem caches. Process RSS/PSS, not total desktop memory.',
              'source_revisions': {'native': args.native_revision, 'legacy': args.baseline_revision},
              'binary_sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in (args.native, args.editor)},
              'configurations': {}}
    custom = {**DEFAULT_CONFIG, 'menu': [
        {'submenu': f'Group {group}', 'items': [
            {'label': f'Command {group}/{index}', 'command': ['true', 'argument with spaces'],
             'metadata': {'preserved': True}} for index in range(100)]}
        for group in range(2)]}
    for label, contents in [('default', DEFAULT_CONFIG), ('custom_200_commands', custom)]:
        config.write_text(json.dumps(contents))
        report = {}
        for name, command, bus in [('legacy_1.0.1', legacy, 'org.openpowermenu.Service'),
                                    ('native_2.0_dev', native, 'org.openpowermenu.NativePreview')]:
            fresh = []
            for _ in range(25):
                start = time.perf_counter_ns()
                subprocess.run(command + ['--widget-menu-json'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
                fresh.append((time.perf_counter_ns() - start) / 1e6)
            start = time.perf_counter_ns()
            with child(command + ['--service']) as server:
                deadline = time.monotonic() + 10
                while True:
                    interface = QDBusInterface(bus, '/OpenPowerMenu', 'org.openpowermenu.Service', QDBusConnection.sessionBus())
                    reply = interface.call('Ping')
                    if reply.type() != QDBusMessage.ErrorMessage:
                        break
                    if server.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError((root / 'process.log').read_text())
                    time.sleep(.005)
                startup = (time.perf_counter_ns() - start) / 1e6
                for _ in range(5):
                    interface.call('GetMenu')
                warm = []
                for _ in range(200):
                    begin = time.perf_counter_ns()
                    reply = interface.call('GetMenu')
                    warm.append((time.perf_counter_ns() - begin) / 1e6)
                    if reply.type() == QDBusMessage.ErrorMessage:
                        raise RuntimeError(reply.errorMessage())
                idle_memory = memory(server.pid)
            editor_command = legacy + ['--edit'] if name.startswith('legacy') else [str(args.editor)]
            with child(editor_command) as editor:
                time.sleep(2)
                if editor.poll() is not None:
                    raise RuntimeError((root / 'process.log').read_text())
                editor_memory = memory(editor.pid)
                editor_mappings = mapped_memory(editor.pid)
            report[name] = {'fresh_cli_process': distribution(fresh),
                            'service_ready_ms_single_observation': round(startup, 3),
                            'warm_GetMenu_roundtrip': distribution(warm),
                            'backend_memory': idle_memory, 'editor_memory_after_2s': editor_memory,
                            'editor_mapped_memory_after_2s': editor_mappings}
        result['configurations'][label] = report
    result['program_payload_bytes'] = {
        'native_backend': args.native.stat().st_size,
        'native_editor': args.editor.stat().st_size,
        'legacy_python_sources': sum(path.stat().st_size for path in (args.legacy_root / 'openpowermenu').glob('*.py')) + (args.legacy_root / 'run.py').stat().st_size}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
