#!/usr/bin/env python3
"""Record an actual EZ check/confirmation/install in a new disposable profile.

Run inside the offline capture container. It never targets the caller's HOME.
No menu action is invoked. Both D-Bus addresses point to the private bus.
"""
import argparse
import hashlib
import json
import os
import select
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--session',action='store_true')
    args=p.parse_args();os.umask(0o022)
    args.output=args.output.resolve();args.bundle=args.bundle.resolve()
    if not args.session:
        args.output.mkdir(parents=True,exist_ok=False)
        env=dict(os.environ)
        for key,name in {'HOME':'home','XDG_CONFIG_HOME':'config','XDG_DATA_HOME':'data',
            'XDG_CACHE_HOME':'cache','XDG_STATE_HOME':'state','XDG_RUNTIME_DIR':'runtime','XDG_BIN_HOME':'bin'}.items():
            (args.output/name).mkdir(mode=0o700);env[key]=str(args.output/name)
        env.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_CURRENT_DESKTOP='KDE',
                   QT_QUICK_CONTROLS_STYLE='org.kde.desktop',QT_QPA_PLATFORMTHEME='kde',
                   XDG_MENU_PREFIX='plasma-',LANG='C.UTF-8',LC_ALL='C.UTF-8')
        env.pop('DISPLAY',None);env.pop('WAYLAND_DISPLAY',None)
        subprocess.run(['dbus-run-session','--',sys.executable,str(Path(__file__).resolve()),'--session',
            '--bundle',str(args.bundle),'--output',str(args.output)],env=env,check=True)
        return
    os.environ['DBUS_SYSTEM_BUS_ADDRESS']=os.environ['DBUS_SESSION_BUS_ADDRESS']
    subprocess.run(['dbus-update-activation-environment','DBUS_SYSTEM_BUS_ADDRESS'],check=True)
    root=Path(__file__).resolve().parents[2]
    archive=Path(subprocess.check_output([sys.executable,str(root/'native/packaging/prepare-ez.py'),
        '--bundle',str(args.bundle),'--output',str(args.output/'archive')],text=True).strip())
    with zipfile.ZipFile(archive) as z:
        z.extractall(args.output/'extracted')
        for member in z.infolist():
            (args.output/'extracted'/member.filename).chmod((member.external_attr>>16)&0o777)
    folder=args.output/'extracted'/archive.stem
    # PTY via script(1) records the real interactive prompt and the typed y.
    commands=[['sha256sum','-c',archive.name+'.sha256'],['bash','install.sh','--check'],
              ['script','--quiet','--return','--command','bash install.sh','/dev/null']]
    records=[]
    with (args.output/'transcript.txt').open('w') as transcript:
        for index,command in enumerate(commands):
            display='sha256sum -c '+archive.name+'.sha256' if index==0 else 'bash install.sh'+(' --check' if index==1 else '')
            transcript.write('$ '+display+'\n');transcript.flush()
            if index==2:
                process=subprocess.Popen(command,cwd=folder,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                data=b'';approved=False;deadline=time.monotonic()+90
                while time.monotonic()<deadline:
                    if select.select([process.stdout],[],[],.2)[0]:
                        chunk=os.read(process.stdout.fileno(),8192)
                        if not chunk:break
                        data+=chunk
                        if not approved and b'Proceed with install? [y/N]:' in data:
                            process.stdin.write(b'y\n');process.stdin.flush();approved=True
                if process.poll() is None:
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill();raise RuntimeError('Interactive installer did not complete')
                result_text=data.decode();status=process.returncode
                assert approved, 'No actual confirmation prompt was observed'
            else:
                result=subprocess.run(command,cwd=archive.parent if index==0 else folder,
                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                result_text=result.stdout;status=result.returncode
            transcript.write(result_text.replace('\r\n','\n'));transcript.write('\n');transcript.flush()
            records.append({'command':display,'exit_code':status})
            if status:raise RuntimeError('EZ capture failed; inspect transcript')
    manifest=json.loads((args.bundle/'bundle.json').read_text())
    (args.output/'provenance.json').write_text(json.dumps({'source_commit':manifest['source_commit'],
        'version':manifest['version'],'os':manifest['os'],'os_version':manifest['os_version'],
        'archive':archive.name,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'operations':records,'power_actions_invoked':0,'environment':'Disposable profile; private session/system bus; offline container'},indent=2)+'\n')


if __name__=='__main__':main()
