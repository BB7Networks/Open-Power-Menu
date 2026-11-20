#!/usr/bin/env python3
"""Capture the documented comparison matrix; run only in a disposable container.

Two independent seats may run together. Each has its own X server, session and
mock system bus, installer target and unmodified production widget.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

CASES = [
    ('menu-default', {'profile':'default'}),
    ('hero', {'view':'nested'}),
    ('placement-left', {'view':'power'}),
    ('placement-center', {'view':'power','position':'center'}),
    ('placement-right', {'view':'power','position':'right'}),
    ('menu-standard', {}),
    ('hints-hidden', {'preferences':{'show_access_key_hints':False}}),
    ('icons-hidden', {'preferences':{'show_menu_icons':False}}),
    ('icons-small', {'preferences':{'menu_icon_size':'small'}}),
    ('icons-large', {'preferences':{'menu_icon_size':'large'}}),
    ('density-compact', {'preferences':{'menu_density':'compact'}}),
    ('density-comfortable', {'preferences':{'menu_density':'comfortable'}}),
    ('width-narrow', {'preferences':{'menu_width':'narrow'}}),
    ('width-wide', {'preferences':{'menu_width':'wide'}}),
    ('height-custom', {'preferences':{'menu_height_mode':'custom','menu_custom_height':360}}),
    ('native-dark', {'scheme':'BreezeDark'}),
    ('aero-dark', {'preferences':{'appearance':'aero'}}),
    ('aero-light', {'preferences':{'appearance':'aero-light'}}),
    ('launcher-beside', {'preferences':{'hide_original_launcher':False}}),
    ('launcher-adopted-icon', {'preferences':{'button_icon_mode':'launcher'}}),
    ('launcher-applications', {'view':'launcher'}),
    ('editing', {'view':'editing'}),
    ('configure', {'view':'configure'}),
    ('standalone', {'view':'standalone'}),
]


def main():
    os.umask(0o022)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--editor-driver',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--jobs',type=int,choices=(1,2),default=1)
    p.add_argument('--only',nargs='*')
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    selected=[(name,values) for name,values in CASES if not args.only or name in args.only]
    assert selected and (not args.only or len(selected)==len(args.only))
    def capture(case):
        name,values=case
        command=[sys.executable,str(Path(__file__).with_name('capture.py')),
            '--bundle',str(args.bundle),'--editor-driver',str(args.editor_driver),
            '--output',str(args.output/name)]
        for key,value in values.items():
            command += ['--'+key,json.dumps(value) if isinstance(value,dict) else value]
        with (args.output/(name+'.log')).open('w') as log:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        print(name,'PASS' if result.returncode==0 else 'FAIL',flush=True)
        return result.returncode==0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results=list(pool.map(capture,selected))
    if not all(results):raise SystemExit(1)


if __name__=='__main__':main()
