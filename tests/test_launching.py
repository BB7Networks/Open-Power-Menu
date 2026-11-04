"""Real subprocess checks without Qt or desktop dependencies."""
import json
import os
from pathlib import Path
import sys
import time

import pytest

from openpowermenu.launching import launch_detached, reap_children


def test_detached_session_argv_descriptors_and_reaping(tmp_path):
    output = tmp_path / 'result.json'
    descriptor = os.open(tmp_path / 'private-descriptor', os.O_CREAT | os.O_RDWR, 0o600)
    os.set_inheritable(descriptor, True)
    literal = 'spaces ; $(touch SHOULD_NOT_EXIST) "quoted"'
    code = '''import json, os, pathlib, sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({
 'pid':os.getpid(), 'ppid':os.getppid(), 'sid':os.getsid(0), 'pgid':os.getpgrp(),
 'arg':sys.argv[2], 'fds':[os.readlink('/proc/self/fd/'+f) for f in os.listdir('/proc/self/fd') if os.path.exists('/proc/self/fd/'+f)]}))'''
    try:
        child = launch_detached([sys.executable, '-c', code, str(output), literal])
        deadline = time.monotonic() + 5
        while reap_children() and time.monotonic() < deadline:
            time.sleep(.01)
        assert child.returncode == 0
        assert not Path(f'/proc/{child.pid}').exists()
        result = json.loads(output.read_text())
        assert result['pid'] == result['sid'] == result['pgid'] == child.pid
        assert result['ppid'] == os.getpid()  # setsid does not remove ancestry
        assert result['arg'] == literal
        assert not any('private-descriptor' in fd for fd in result['fds'])
        assert result['fds'].count('/dev/null') >= 3
    finally:
        os.close(descriptor)


def test_failed_launch_is_reported_and_does_not_register_child():
    with pytest.raises(FileNotFoundError):
        launch_detached(['/definitely/not/an/opm/executable'])
    assert not reap_children()
