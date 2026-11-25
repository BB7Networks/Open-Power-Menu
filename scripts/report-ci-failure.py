#!/usr/bin/env python3
"""Expose bounded Docker test failure details in GitHub's check annotations."""
from pathlib import Path
import json
import re
import sys

for argument in sys.argv[1:]:
    path = Path(argument)
    if not path.is_file():
        continue
    # Docker repeats the entire RUN command on failure; it must not crowd the
    # useful Qt/Python assertion and its Actual/Expected context out of the log.
    raw = path.read_text(errors='replace').splitlines()
    # Keep the exact inner assertion and fixture state even when its JSON line
    # exceeds Docker/GitHub's ordinary tail limits. Split annotations below the
    # 4 KiB limit; never let a repeated Docker RUN command replace this evidence.
    fixtures = []
    for line in raw:
        if 'OPM_FIXTURE ' not in line:
            continue
        try:
            row = json.loads(line.split('OPM_FIXTURE ', 1)[1])
        except ValueError:
            continue
        fixtures.append(row)
    failures = [row for row in fixtures if row['event'] == 'failure-before-teardown']
    for failure in failures[-2:]:
        details = {key: failure.get(key) for key in ('time_ms','scenario','assertion','focus','processes')}
        state = failure.get('state') or {}
        popup = state.get('popup') or {}
        details['popup'] = {key:popup.get(key) for key in ('window','activeFocus','preferred','padding','flyout')}
        details['requests'] = [row.get('member') for row in failure.get('requests',[])]
        if 'states' in failure:
            details['geometry'] = {phase:[{key:s.get(key) for key in ('time','event','window','preferred','padding','actual','flyout')}
                                         for s in states[-4:]] for phase,states in failure['states'].items()}
        message = json.dumps(details,indent=2)
        for index in range(0,len(message),2800):
            part = message[index:index+2800].replace('%','%25').replace('\r','%0D').replace('\n','%0A')
            print('::error title='+path.name+' fixture evidence '+str(index//2800+1)+'::'+part)
    if failures:
        recent = [row for row in fixtures if row['time_ms']<=failures[-1]['time_ms']][-10:]
        for row in recent:
            if row['event']=='failure-before-teardown':continue
            message=json.dumps(row)[:2800].replace('%','%25').replace('\r','%0D').replace('\n','%0A')
            print('::error title='+path.name+' recent fixture event::'+message)
    lines = [line[:600] for line in raw
             if 'OPM_POPUP_TRACE' not in line and len(line) < 1200]
    errors = []
    for index, line in enumerate(lines):
        if re.search(r'error:|FAIL!|Exception|AssertionError|not found|failed to|FAIL:', line, re.I):
            errors.extend(lines[index:index+5])
    for title, message in [('failures', '\n'.join(errors)[-3000:]), ('final output', '\n'.join(lines[-40:])[-3000:])]:
        message = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print('::error title='+path.name+' '+title+'::'+message)
