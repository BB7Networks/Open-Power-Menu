"""Bounded, timestamped evidence from disposable fixtures, before teardown."""
import json
from pathlib import Path
import subprocess
import time
import traceback


def tail(path, limit=6000):
    path = Path(path)
    if not path.is_file():
        return ''
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size-limit))
        return stream.read().decode(errors='replace')


class Evidence:
    def __init__(self, case, platform):
        self.case, self.platform = Path(case), platform
        self.scenario = 'startup'

    def record(self, event, **values):
        row = {'time_ms': round(time.time()*1000), 'scenario': self.scenario,
               'event': event, **values}
        line = json.dumps(row, separators=(',', ':'))
        with (self.case/'events.jsonl').open('a') as stream:
            stream.write(line+'\n')
        print('OPM_FIXTURE '+line, flush=True)
        return row

    def begin(self, scenario):
        self.scenario = scenario
        self.record('scenario')

    def focus(self):
        if self.platform != 'xcb':
            return None
        def read(*args):
            try:
                reply = subprocess.run(args, capture_output=True, text=True, timeout=2)
                return (reply.stdout+reply.stderr).strip()[:1800]
            except subprocess.TimeoutExpired:
                return 'read-only focus query timed out'
        window = read('xdotool', 'getwindowfocus')
        return {'window': window,
                'properties': read('xprop', '-id', window, 'WM_CLASS', '_NET_WM_NAME', '_NET_WM_PID', '_NET_WM_WINDOW_TYPE') if window.isdigit() else None,
                'active': read('xprop', '-root', '_NET_ACTIVE_WINDOW')}

    def failure(self, processes, **values):
        # Called in except, BEFORE any process is terminated. A later XIO
        # message must not be confused with the original assertion's cause.
        input_events=[]
        for line in tail(self.case/'xinput.jsonl').splitlines():
            try:input_events.append(json.loads(line))
            except ValueError:pass # The bounded tail may start inside a record.
        row = self.record('failure-before-teardown', assertion=traceback.format_exc(),
                          processes=[{'pid': p.pid, 'command': str(p.args[0]), 'returncode': p.poll()} for p in processes],
                          focus=self.focus(), input_events=input_events[-20:], **values)
        (self.case/'failure.json').write_text(json.dumps(row, indent=2)+'\n')
        for name in ('xinput.jsonl', 'requests.jsonl', 'kwin.log', 'display.log', 'shortcuts.log'):
            content = tail(self.case/name)
            if content:
                print('OPM_EVIDENCE '+name+'\n'+content, flush=True)
