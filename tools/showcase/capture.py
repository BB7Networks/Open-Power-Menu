#!/usr/bin/env python3
"""Capture the unmodified native 2.1 widget in a private Plasma/X11 seat.

Requires the native editor.Dockerfile dependencies and a sealed native bundle.
All final power endpoints are private mocks; this never uses a working profile.
Screenshots are actual QScreen pixels. Only cropping and lossless encoding follow.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = '4e11393c4d289c453044130d79dc54a23049c32c'
WIDTH, HEIGHT = 1600, 1000


def wait_for(check, timeout=30):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        value=check()
        if value: return value
        time.sleep(.1)
    raise RuntimeError('Capture condition did not become ready')


def run(*args, **kwargs):
    return subprocess.check_output(list(map(str,args)),text=True,**kwargs).strip()


def menu_config(bundle, profile='customized'):
    config=json.loads(run(bundle/'app/bin/open-power-menu-standalone','--default-config'))
    if profile=='default':return config
    config.update(launcher_applet_id=3,hide_original_launcher=True,button_icon_mode='custom',
                  button_icon='open-power-menu',power_confirmation='always')
    group=next(row for row in config['menu'] if 'submenu' in row and row.get('access_key')=='U')
    config['menu']=[{'action':key} for key in ('applications','power','system','network')]+[
        {'separator':True},*({'action':key} for key in ('terminal','monitor','files','settings','run')),
        {'separator':True},
        {'submenu':'Remote & Work','icon':'network-server','access_key':'A','items':[
            {'action':'remote'}, {'action':'network_locations'},
            {'submenu':'Tools','icon':'applications-system','items':[
                {'action':'hardware'},{'action':'logs'},{'action':'disks'}]}]},
        group,{'action':'show_desktop'}]
    return config


def panel_config(position, diagnostics):
    order={'left':'3;4;5','center':'5;3;4;6','right':'5;3;4'}[position]
    text=f'''[Containments][1]
activityId=
formfactor=0
lastScreen=0
location=0
plugin=org.kde.plasma.folder
wallpaperplugin=org.kde.image

[Containments][1][Wallpaper][org.kde.image][General]
Image=file:///usr/share/wallpapers/Next/contents/images/1920x1080.png

[Containments][2]
activityId=
formfactor=2
lastScreen=0
location=4
plugin=org.kde.panel

[Containments][2][General]
AppletOrder={order}

[Containments][2][Applets][3]
plugin=org.kde.plasma.kickoff

[Containments][2][Applets][3][Configuration][General]
favorites=org.kde.dolphin.desktop,org.kde.konsole.desktop,systemsettings.desktop,org.kde.discover.desktop,org.kde.kinfocenter.desktop

[Containments][2][Applets][4]
plugin=org.openpowermenu.start

[Containments][2][Applets][4][Configuration][General]
popupDiagnostics={str(diagnostics).lower()}

[Containments][2][Applets][5]
plugin=org.kde.plasma.panelspacer
'''
    if position=='center':
        text+='\n[Containments][2][Applets][6]\nplugin=org.kde.plasma.panelspacer\n'
    return text


def setup(args):
    case=args.output.resolve()
    case.mkdir(parents=True,exist_ok=False)
    for name in ('home','config','data','cache','state','runtime','bin'):
        (case/name).mkdir(mode=0o700)
    (case/'home/Desktop').mkdir()
    (case/'home/Network Locations').mkdir()
    scheme=args.scheme
    colors=Path('/usr/share/color-schemes')/(scheme+'.colors')
    (case/'config/kdeglobals').write_text(colors.read_text()+
        '\n[KDE]\nLookAndFeelPackage=org.kde.breeze.desktop\nwidgetStyle=Breeze\n'
        '\n[Icons]\nTheme=breeze'+('-dark' if scheme=='BreezeDark' else '')+'\n')
    # kconf_update syntax is deliberately left to KDE's actual config tool.
    env={**os.environ,**{key:str(case/value) for key,value in {
        'HOME':'home','XDG_CONFIG_HOME':'config','XDG_DATA_HOME':'data',
        'XDG_CACHE_HOME':'cache','XDG_STATE_HOME':'state','XDG_RUNTIME_DIR':'runtime','XDG_BIN_HOME':'bin'}.items()},
        'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','XDG_CURRENT_DESKTOP':'KDE','XDG_SESSION_TYPE':'x11',
        'XDG_MENU_PREFIX':'plasma-',
        'QT_QPA_PLATFORM':'xcb','QT_QUICK_BACKEND':'software','QT_QUICK_CONTROLS_STYLE':'org.kde.desktop',
        'QT_QPA_PLATFORMTHEME':'kde','QT_SCALE_FACTOR':'1','QT_AUTO_SCREEN_SCALE_FACTOR':'0',
        'LIBGL_ALWAYS_SOFTWARE':'1','KWIN_COMPOSE':'Q','OPM_POWER_RECORD':str(case/'power-requests.jsonl')}
    env['PATH']=str(case/'bin')+':'+env['PATH']
    env.pop('DISPLAY',None);env.pop('WAYLAND_DISPLAY',None)
    (case/'config/plasma-org.kde.plasma.desktop-appletsrc').write_text(panel_config(args.position,True))
    (case/'config/plasmashellrc').write_text('[PlasmaViews][Panel 2]\nthickness=48\nalignment=0\nfloating=0\n')
    (case/'config/ksmserverrc').write_text('[General]\nconfirmLogout=true\n')
    (case/'bin/loginctl').write_text('#!/bin/sh\nprintf \'%s\\n\' \'{"member":"Lock","mock":true}\' >> "$OPM_POWER_RECORD"\n')
    (case/'bin/loginctl').chmod(0o755)
    config=menu_config(args.bundle,args.profile)
    config.update(json.loads(args.preferences))
    (case/'config/open-power-menu').mkdir()
    (case/'config/open-power-menu/menu.json').write_text(json.dumps(config,indent=2)+'\n')
    run('kwriteconfig6','--file','kdeglobals','--group','General','--key','font','Noto Sans,10,-1,5,50,0,0,0,0,0',env=env)
    run('kwriteconfig6','--file','kdeglobals','--group','General','--key','ColorScheme',scheme,env=env)
    subprocess.run(['dbus-run-session','--',sys.executable,str(Path(__file__).resolve()),
                    '--session','--bundle',str(args.bundle.resolve()),'--output',str(case),
                    '--position',args.position,'--scheme',scheme,'--view',args.view,
                    '--preferences',args.preferences,
                    '--profile',args.profile,
                    *(['--editor-driver',str(args.editor_driver.resolve())] if args.editor_driver else [])],env=env,check=True)


def session(args):
    from PySide6.QtGui import QGuiApplication
    case=args.output
    os.environ['DBUS_SYSTEM_BUS_ADDRESS']=os.environ['DBUS_SESSION_BUS_ADDRESS']
    processes=[];logs=[]
    def spawn(command,name,pipe=False):
        output=(case/name).open('w');logs.append(output)
        p=subprocess.Popen(list(map(str,command)),stdout=subprocess.PIPE if pipe else output,stderr=output,text=True)
        processes.append(p);return p
    def dbus(method,*arguments):
        return run('qdbus6','org.openpowermenu.Service','/OpenPowerMenu','org.openpowermenu.Service.'+method,*arguments)
    def trace():
        path=case/'plasma.log'
        if not path.exists(): return None
        with path.open('rb') as log:
            log.seek(max(0,path.stat().st_size-100000));lines=log.read().decode(errors='replace').splitlines()
        for line in reversed(lines):
            if 'OPM_POPUP_TRACE ' in line:
                try:return json.loads(line.split('OPM_POPUP_TRACE ',1)[1])['state']
                except (ValueError,KeyError):pass
        return None
    def xwindows():
        found=subprocess.run(['xdotool','search','--onlyvisible','--pid',str(shell.pid)],capture_output=True,text=True)
        results=[]
        for wid in found.stdout.splitlines():
            prop=run('xprop','-id',wid,'_NET_WM_WINDOW_TYPE')
            geometry=run('xdotool','getwindowgeometry','--shell',wid)
            fields=dict(line.split('=',1) for line in geometry.splitlines() if '=' in line)
            results.append({'id':wid,'type':prop.strip(),'geometry':[int(fields[k]) for k in ('X','Y','WIDTH','HEIGHT')]})
        return results
    try:
        read,write=os.pipe()
        out=(case/'display.log').open('w');logs.append(out)
        p=subprocess.Popen(['Xvfb','-displayfd',str(write),'-screen','0',f'{WIDTH}x{HEIGHT}x24','-dpi','96','-nolisten','tcp'],
                           stdout=out,stderr=out,pass_fds=(write,));processes.append(p);os.close(write)
        assert select.select([read],[],[],10)[0]
        os.environ['DISPLAY']=':'+os.read(read,64).decode().strip();os.close(read)
        # D-Bus-activated production binaries must see the same PRIVATE system
        # bus as direct children. Never let activation fall back to host logind.
        run('dbus-update-activation-environment','DISPLAY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE',
            'QT_QPA_PLATFORM','DBUS_SYSTEM_BUS_ADDRESS','PATH')
        fixture=spawn([sys.executable,ROOT/'native/tests/plasma_keyboard.py','--power-fixture'],'power-mock.log',True)
        assert select.select([fixture.stdout],[],[],10)[0] and fixture.stdout.readline().strip()=='SAFE_FIXTURE_READY'
        shortcuts=shutil.which('kglobalacceld') or '/usr/lib/x86_64-linux-gnu/libexec/kglobalacceld'
        spawn([shortcuts],'shortcuts.log')
        spawn(['kwin_x11'],'kwin.log')
        def shortcuts_ready():
            result=subprocess.run(['qdbus6','org.kde.kglobalaccel','/component/kwin',
                'org.kde.kglobalaccel.Component.shortcutNames'],capture_output=True,text=True)
            return 'Show Desktop' in result.stdout.splitlines()
        wait_for(shortcuts_ready)
        # A real native install in the disposable profile, using the unmodified
        # sealed bundle. No workstation activation/configuration is involved.
        with (case/'installation.txt').open('w') as output:
            subprocess.run(['bash',str(args.bundle/'install.sh')],stdout=output,stderr=subprocess.STDOUT,check=True)
        spawn([args.bundle/'app/bin/open-power-menu-native','--service','--bus-name','org.openpowermenu.Service'],'backend.log')
        wait_for(lambda:subprocess.run(['qdbus6','org.openpowermenu.Service','/OpenPowerMenu','org.openpowermenu.Service.Ping'],capture_output=True).returncode==0)
        (case/'backend-version.txt').write_text(dbus('Ping')+'\n')
        shell=spawn(['plasmashell','--no-respawn'],'plasma.log')
        wait_for(lambda:trace() is not None,45)
        run('qdbus6','org.kde.plasmashell','/PlasmaShell','org.kde.PlasmaShell.evaluateScript',
            'var p=panels()[0]; p.height=48; p.alignment="left"; p.offset=0; p.minimumLength=1600; p.maximumLength=1600; p.floating=false;')
        def discovered():
            entries=json.loads(dbus('GetMenu'))
            return entries if dbus('PowerCapabilitiesPending')=='false' else None
        entries=wait_for(discovered)
        (case/'menu-presented.json').write_text(json.dumps(entries,indent=2)+'\n')
        run('xdotool','key','--clearmodifiers','super+x')
        wait_for(lambda:trace() and trace()['expanded'] and trace()['powerIsOpen'] and not trace()['openingPower'])
        time.sleep(.7)
        win=wait_for(lambda:next((w for w in xwindows() if '_KDE_NET_WM_WINDOW_TYPE_APPLET_POPUP' in w['type']),None))
        popup_x=win['geometry'][0]
        assert {'left':popup_x<150,'center':WIDTH/3<popup_x<WIDTH*2/3,
                'right':popup_x>WIDTH*2/3}[args.position], (args.position,win)
        app=QGuiApplication([])
        captures=[]
        def snap(name='screen'):
            run('xdotool','mousemove',WIDTH-10,10)
            time.sleep(.4)
            image=app.primaryScreen().grabWindow(0).toImage()
            assert image.save(str(case/(name+'.png')))
            captures.append({'name':name,'windows':xwindows(),'state':trace()})
        def keys(*sequence):
            run('xdotool','key','--clearmodifiers','--delay','50',*sequence)
            time.sleep(.25)
        if args.view=='nested':
            keys('a');wait_for(lambda:trace()['popup']['flyout']['window']['visible'])
            keys('Down','Down','Right')
            time.sleep(.5)
        elif args.view=='launcher':
            keys('Escape')
            # Click the actual button, then wait for the selected Kickoff.
            x={'left':28,'center':WIDTH//2,'right':WIDTH-28}[args.position]
            run('xdotool','mousemove',x,HEIGHT-24,'click','1')
            wait_for(lambda:trace()['launcher']['expanded'])
            time.sleep(.5)
        elif args.view=='editing':
            x,y,w,h=win['geometry']
            run('xdotool','mousemove',x+w-91,y+25,'click','1')
            time.sleep(.5);snap('editing-unlocked')
            keys('Down','alt+Down');snap('editing-reordered')
            keys('alt+Right');snap('editing-destination')
            keys('Down','Return');time.sleep(.5)
            snap('editing-submenu')
        elif args.view=='power':
            keys('u');wait_for(lambda:trace()['popup']['flyout']['window']['visible'])
        elif args.view=='configure':
            assert args.editor_driver, 'Build the documentation-only editor driver first'
            keys('Escape')
            with (case/'editor-driver.log').open('w') as output:
                subprocess.run([str(args.editor_driver),str(case/'config/open-power-menu/menu.json'),
                    str(case/'editor')],stdout=output,stderr=subprocess.STDOUT,check=True)
        elif args.view=='standalone':
            keys('Escape')
            spawn([args.bundle/'app/bin/open-power-menu-standalone','--anchor','bottom-left'],'standalone.log')
            time.sleep(1)
        snap()
        record={'source_commit':SOURCE,'version':'2.1.0','session':'X11 / Xvfb + KWin + plasmashell',
            'screen':[WIDTH,HEIGHT],'scale':1,'dpi':96,'scheme':args.scheme,'position':args.position,
            'profile':args.profile,
            'distribution':run('cat','/etc/os-release'),
            'runtime_packages':run('dpkg-query','-W','-f=${Package} ${Version}\n',
                'libqt6core6t64','plasma-workspace','kwin-x11','breeze','fonts-noto-core').splitlines(),
            'settings':json.loads((case/'config/open-power-menu/menu.json').read_text()),
            'windows':xwindows(),'popup':win,'state':trace(),'captures':captures,
            'capture':'QScreen.grabWindow(0); unmodified installed widget',
            'power_requests':(case/'power-requests.jsonl').read_text().splitlines() if (case/'power-requests.jsonl').exists() else []}
        (case/'capture.json').write_text(json.dumps(record,indent=2)+'\n')
        assert not record['power_requests'],record['power_requests']
        print('Captured',case/'screen.png',flush=True)
    finally:
        for p in reversed(processes):
            if p.poll() is None:p.terminate()
        for p in reversed(processes):
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for stream in logs:stream.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--position',choices=('left','center','right'),default='left')
    parser.add_argument('--scheme',choices=('BreezeLight','BreezeDark'),default='BreezeLight')
    parser.add_argument('--preferences',default='{}')
    parser.add_argument('--view',default='menu')
    parser.add_argument('--profile',choices=('default','customized'),default='customized')
    parser.add_argument('--editor-driver',type=Path)
    parser.add_argument('--session',action='store_true')
    args=parser.parse_args();args.bundle=args.bundle.resolve();args.output=args.output.resolve()
    manifest=json.loads((args.bundle/'bundle.json').read_text())
    assert manifest['source_commit']==SOURCE and manifest['version']=='2.1.0'
    os.umask(0o022)
    session(args) if args.session else setup(args)


if __name__=='__main__':main()
