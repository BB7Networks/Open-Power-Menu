#!/usr/bin/env python3
"""Expose bounded Docker test failure details in GitHub's check annotations."""
from pathlib import Path
import re
import sys

for argument in sys.argv[1:]:
    path = Path(argument)
    if not path.is_file():
        continue
    lines = [line for line in path.read_text(errors='replace').splitlines() if 'OPM_POPUP_TRACE' not in line]
    errors = [line for line in lines if re.search(r'error:|FAIL!|Exception|AssertionError|not found|failed to|^FAIL:', line, re.I)]
    for title, message in [('failures', '\n'.join(errors)[-3000:]), ('final output', '\n'.join(lines[-40:])[-3000:])]:
        message = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print('::error title='+path.name+' '+title+'::'+message)
