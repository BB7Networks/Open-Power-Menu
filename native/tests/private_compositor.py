"""Require actual compositing on the fixture's private session bus."""
import argparse
import os
import re
import subprocess
import time


def active(process=None):
    if process is not None:
        assert process.poll() is None, 'Private KWin exited before/during qualification'
    # Use the standard property API. Calling a property as a method is not
    # portable between qdbus/Qt versions and can leave a broken seat unnoticed.
    reply=subprocess.run(['dbus-send','--session','--print-reply','--reply-timeout=1000',
        '--dest=org.kde.KWin','/Compositor','org.freedesktop.DBus.Properties.Get',
        'string:org.kde.kwin.Compositing','string:active'],capture_output=True,text=True,timeout=2)
    return reply.returncode==0 and re.search(r'variant\s+boolean true\b',reply.stdout) is not None


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid',type=int,required=True)
    args=parser.parse_args()
    until=time.monotonic()+15
    while time.monotonic()<until:
        os.kill(args.pid,0)
        if active():break
        time.sleep(.025)
    else:raise AssertionError('Private KWin did not establish compositing')
