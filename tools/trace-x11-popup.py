#!/usr/bin/env python3
"""Observe plasmashell X11 windows without creating, mapping or activating any.

Run before reproducing: python3 tools/trace-x11-popup.py --seconds 45 > x11.jsonl
Requires xdotool, xprop, xwininfo, xev and stdbuf. All X11 operations are reads or
Structure/Expose event subscriptions. No focus requests, repaint requests,
window destruction, screenshots, shell restarts or configuration writes.
"""
import argparse
from datetime import datetime, timezone
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time


def read(*command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=3)
    return result.returncode, result.stdout


def emit(event, **details):
    print(json.dumps({'time':datetime.now(timezone.utc).isoformat(),
        'time_ms':time.time()*1000, 'event':event, **details}), flush=True)


def window_state(wid):
    code, info = read('xwininfo','-id',wid)
    if code: return {'map':'destroyed-or-unavailable'}
    state = re.search(r'Map State: (\S+)', info)
    geometry = {}
    for name, pattern in [('x',r'Absolute upper-left X:\s+(-?\d+)'),
                          ('y',r'Absolute upper-left Y:\s+(-?\d+)'),
                          ('width',r'Width:\s+(\d+)'),('height',r'Height:\s+(\d+)')]:
        value = re.search(pattern,info)
        if value: geometry[name]=int(value[1])
    return {'map':state[1] if state else 'unknown','geometry':geometry}


def monitor(pid, seconds):
    events=queue.Queue(); observers={}; known={}; previous={}; prior_root=None
    def forward(wid, proc):
        for line in proc.stdout:
            events.put((wid,line.rstrip(),time.time()*1000))
    deadline=time.monotonic()+seconds
    try:
        while time.monotonic()<deadline:
            _, ids=read('xdotool','search','--pid',str(pid))
            for wid in ids.splitlines():
                _, props=read('xprop','-id',wid,'_NET_WM_PID','_NET_WM_WINDOW_TYPE',
                             'WM_TRANSIENT_FOR','_KDE_SLIDE','_NET_WM_WINDOW_OPACITY')
                if not any(kind in props for kind in ('APPLET_POPUP','_UTILITY','_DOCK','_NORMAL')): continue
                if wid in known:
                    if props!=known[wid]:
                        emit('window-properties',window=wid,properties=props)
                        known[wid]=props
                    continue
                known[wid]=props
                emit('window-observed',window=wid,properties=props,state=window_state(wid))
                proc=subprocess.Popen(['stdbuf','-oL','xev','-1','-id',wid,'-event','structure','-event','expose'],
                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                observers[wid]=proc
                threading.Thread(target=forward,args=(wid,proc),daemon=True).start()
            for wid in known:
                state=window_state(wid)
                if state!=previous.get(wid):
                    emit('window-state',window=wid,state=state); previous[wid]=state
            _, root=read('xprop','-root','_NET_ACTIVE_WINDOW','_NET_CLIENT_LIST_STACKING')
            if root!=prior_root:
                emit('root-properties',properties=root);prior_root=root
            while not events.empty():
                wid,line,observed=events.get_nowait()
                emit('xevent',window=wid,observed_ms=observed,message=line)
            time.sleep(.1)
    finally:
        for proc in observers.values():
            if proc.poll() is None: proc.terminate()
        for proc in observers.values():
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        emit('capture-ended')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid',type=int)
    parser.add_argument('--seconds',type=float,default=45)
    args=parser.parse_args()
    if not os.environ.get('DISPLAY'): parser.error('An X11 DISPLAY is required')
    if not 0<args.seconds<=600: parser.error('--seconds must be between 0 and 600')
    for tool in ('xdotool','xprop','xwininfo','xev','stdbuf','pgrep'):
        if not shutil.which(tool): parser.error('Missing tool: '+tool)
    pid=args.pid
    if pid is None:
        _, text=read('pgrep','-u',str(os.getuid()),'-x','plasmashell')
        ids=text.splitlines()
        if len(ids)!=1: parser.error('Use --pid to select exactly one plasmashell process')
        pid=int(ids[0])
    emit('capture-started',pid=pid,display=os.environ['DISPLAY'])
    try: monitor(pid,args.seconds)
    except KeyboardInterrupt: pass


if __name__=='__main__': main()
