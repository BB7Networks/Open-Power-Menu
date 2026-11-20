#!/usr/bin/env python3
"""Expose bounded Docker test failure details in GitHub's check annotations."""
from pathlib import Path
import re
import sys

for argument in sys.argv[1:]:
    path = Path(argument)
    if not path.is_file():
        continue
    # Docker repeats the entire RUN command on failure; it must not crowd the
    # useful Qt/Python assertion and its Actual/Expected context out of the log.
    lines = [line[:600] for line in path.read_text(errors='replace').splitlines()
             if 'OPM_POPUP_TRACE' not in line and len(line) < 1200]
    errors = []
    for index, line in enumerate(lines):
        if re.search(r'error:|FAIL!|Exception|AssertionError|not found|failed to|FAIL:', line, re.I):
            errors.extend(lines[index:index+5])
    for title, message in [('failures', '\n'.join(errors)[-3000:]), ('final output', '\n'.join(lines[-40:])[-3000:])]:
        message = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print('::error title='+path.name+' '+title+'::'+message)
