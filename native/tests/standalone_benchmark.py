"""Warm-cache standalone measurements in a private X11 session (no power actions).

Run with dbus-run-session -- xvfb-run -a python3 this-file --help.
The first diagnostic reporting exposure is an observed upper bound, not a
photodiode/cold-boot measurement. Raw samples and dependency lists are retained.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import selectors
import statistics
import subprocess
import sys
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--legacy-root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--native-revision', default='unspecified')
args = parser.parse_args()
sys.path.insert(0, str(args.legacy_root))
from openpowermenu.core import DEFAULT_CONFIG, COMMANDS


def memory(pid):
    return {parts[0].rstrip(':'): int(parts[1])
            for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines()
            if (parts := line.split())[0] in ('Rss:', 'Pss:')}


def distribution(samples):
    return {'median_ms': round(statistics.median(samples), 3),
            'p95_ms': round(sorted(samples)[int(len(samples) * .95)], 3),
            'samples_ms': [round(value, 3) for value in samples]}


with tempfile.TemporaryDirectory(prefix='opm-standalone-bench-') as temp:
    root = Path(temp)
    tools = root / 'tools'
    tools.mkdir()
    for spec in COMMANDS.values():
        for candidate in spec['commands']:
            program = (candidate['argv'] if isinstance(candidate, dict) else candidate)[0]
            if '/' not in program:
                path = tools / program
                path.write_text('#!/bin/sh\nexit 0\n')
                path.chmod(0o755)
    for name, output in [('qdbus6', 'Show Desktop'), ('kcmshell6', 'kcm_printer_manager\\nkcm_powerdevilprofilesconfig')]:
        path = tools / name
        path.write_text(f'#!/bin/sh\nprintf "{output}\\n"\n')
        path.chmod(0o755)
    config = root / 'config/open-power-menu/menu.json'
    config.parent.mkdir(parents=True)
    env = {**os.environ, 'XDG_CONFIG_HOME': str(root / 'config'),
           'XDG_DATA_HOME': str(root / 'data'), 'XDG_CACHE_HOME': str(root / 'cache'),
           'QT_QPA_PLATFORM': 'xcb', 'XDG_CURRENT_DESKTOP': 'KDE',
           'PATH': str(tools) + ':' + os.defpath}
    runtimes = {'legacy': [sys.executable, str(args.legacy_root / 'run.py')],
                'native': [str(args.native.resolve())]}
    result = {'platform': platform.platform(), 'method': 'Xvfb X11; warm caches; private D-Bus; harmless availability fixtures; first exposed diagnostic; memory after 2 seconds',
              'native_source_revision': args.native_revision,
              'native_sha256': hashlib.sha256(args.native.read_bytes()).hexdigest(),
              'baseline': '3405848 (released 1.0.1)', 'cases': {}}
    for case in ('default', '200-commands'):
        cfg = dict(DEFAULT_CONFIG)
        if case != 'default':
            cfg['menu'] = [{'label': f'Command {i}', 'command': ['/bin/true', f'argument {i}']}
                           for i in range(200)]
        config.write_text(json.dumps(cfg))
        measurements = {}
        for label, command in runtimes.items():
            latencies = []
            memories = []
            cli = []
            for run in range(16):  # first discarded as warmup
                started = time.perf_counter()
                completed = subprocess.run([*command, '--check'], env=env, capture_output=True, check=True)
                cli_ms = (time.perf_counter() - started) * 1000
                started = time.perf_counter()
                process = subprocess.Popen([*command, '--diagnose-launch'], env=env,
                                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                try:
                    selector = selectors.DefaultSelector()
                    selector.register(process.stdout, selectors.EVENT_READ)
                    exposed = None
                    data = b''
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline and exposed is None:
                        if not selector.select(.1):
                            continue
                        chunk = os.read(process.stdout.fileno(), 65536)
                        if not chunk:
                            raise RuntimeError(f'{label} exited before exposure')
                        data += chunk
                        while b'\n' in data:
                            line, data = data.split(b'\n', 1)
                            if line.startswith(b'OPM_LAUNCH '):
                                state = json.loads(line[11:])
                                if state.get('visible') and state.get('exposed'):
                                    exposed = (time.perf_counter() - started) * 1000
                                    break
                    if exposed is None:
                        raise RuntimeError(f'{label} did not report exposure')
                    if run:
                        latencies.append(exposed)
                        cli.append(cli_ms)
                    if run in (1, 2, 3):
                        time.sleep(2)
                        memories.append(memory(process.pid))
                finally:
                    selector.close()
                    process.terminate()
                    process.wait(timeout=5)
            measurements[label] = {'exposure': distribution(latencies), 'check_process': distribution(cli),
                                   'memory_KiB': memories,
                                   'median_RSS_KiB': statistics.median(m['Rss'] for m in memories),
                                   'median_PSS_KiB': statistics.median(m['Pss'] for m in memories)}
        result['cases'][case] = measurements
    result['native_ldd'] = subprocess.check_output(['ldd', str(args.native.resolve())], text=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['cases'], indent=2))
