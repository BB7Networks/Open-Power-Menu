"""Optional real Qt/D-Bus integration; CI installs Qt in a separate job."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

pytest.importorskip('PySide6.QtWidgets', reason='Qt runtime checks run in the Qt CI job')
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('mode', ['backend-term', 'backend-kill', 'backend-idle',
                                 'backend-upgrade', 'backend-reap', 'backend-accounting',
                                 'standalone', 'editor', 'configuration', 'layout'])
def test_runtime(mode):
    if not shutil.which('dbus-run-session'):
        pytest.skip('dbus-run-session is required')
    completed = subprocess.run(
        ['dbus-run-session', '--', sys.executable, str(ROOT / 'tests/qt_runtime_runner.py'), mode],
        cwd=ROOT, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
        capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert f'PASS {mode}' in completed.stdout
