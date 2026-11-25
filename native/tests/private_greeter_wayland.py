"""Observe real Wayland greeter windows and cancel on the private KWin seat."""
import json
import os
from pathlib import Path
import socket
import struct
import subprocess


def observe(case):
    script = case/'observe-greeter.js'
    script.write_text('''
function report(event, window) {
    if (String(window.resourceClass).indexOf("ksmserver-logout-greeter") < 0) return;
    const g=window.frameGeometry;
    print("OPM_GREETER_WINDOW "+JSON.stringify({event:event,id:String(window.internalId),
        caption:window.caption,resourceClass:String(window.resourceClass),
        geometry:[g.x,g.y,g.width,g.height],visible:event!=="removed",
        windowType:String(window),readyForPainting:window.readyForPainting}));
}
workspace.windowAdded.connect(window=>report("added",window));
workspace.windowRemoved.connect(window=>report("removed",window));
workspace.windowList().forEach(window=>report("existing",window));
''')
    result=subprocess.check_output(['qdbus6','org.kde.KWin','/Scripting',
        'org.kde.kwin.Scripting.loadScript',str(script),'opm-private-greeter-observer'],text=True).strip()
    assert result.lstrip('-').isdigit() and int(result)>=0, result
    subprocess.run(['qdbus6','org.kde.KWin','/Scripting','org.kde.kwin.Scripting.start'],check=True)


def windows(case):
    live={}
    path=case/'kwin.log'
    if not path.is_file():return []
    for line in path.read_text(errors='replace').splitlines():
        if 'OPM_GREETER_WINDOW ' not in line: continue
        try: row=json.loads(line.split('OPM_GREETER_WINDOW ',1)[1])
        except ValueError: continue
        if row['visible']: live[row['id']]=row
        else: live.pop(row['id'],None)
    return list(live.values())


def escape():
    # KWin fake-input is limited to a freshly allocated fixture socket. No
    # global settings, host compositor or production input code is touched.
    runtime=Path(os.environ['XDG_RUNTIME_DIR'])
    assert runtime.parent==Path('/tmp') and runtime.name.startswith('opm-greeter-')
    assert runtime.stat().st_uid==os.getuid() and runtime.stat().st_mode & 0o077==0
    assert (runtime/'.opm-private-greeter').read_text()=='private mocked greeter\n'
    assert os.environ['WAYLAND_DISPLAY']=='opm-greeter-test'
    def number(value): return struct.pack('=I',value)
    def string(value):
        data=value.encode()+b'\0'
        return number(len(data))+data+b'\0'*((-len(data))%4)
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
        connection.settimeout(3); connection.connect(str(runtime/'opm-greeter-test'))
        def send(obj,opcode,data=b''):
            connection.sendall(struct.pack('=II',obj,((len(data)+8)<<16)|opcode)+data)
        def read(length):
            data=b''
            while len(data)<length:
                piece=connection.recv(length-len(data))
                if not piece: raise RuntimeError('Private compositor disconnected')
                data+=piece
            return data
        available=[]
        def sync(callback):
            send(1,0,number(callback))
            while True:
                obj,header=struct.unpack('=II',read(8)); opcode,length=header&65535,header>>16
                assert 8<=length<=65536
                data=read(length-8)
                if obj==1 and opcode==0: raise RuntimeError('Private Wayland protocol error')
                if obj==2 and opcode==0:
                    name,size=struct.unpack('=II',data[:8])
                    interface=data[8:8+size-1].decode()
                    version=struct.unpack_from('=I',data,8+((size+3)//4)*4)[0]
                    available.append((name,interface,version))
                if obj==callback and opcode==0:return
        send(1,1,number(2));sync(3)
        name,interface,version=next(row for row in available if row[1]=='org_kde_kwin_fake_input')
        assert version>=4
        send(2,0,number(name)+string(interface)+number(4)+number(4))
        send(4,0,string('OPM private greeter test')+string('Cancel mock-only confirmation'))
        send(4,10,number(1)+number(1));send(4,10,number(1)+number(0)) # evdev Escape
        sync(5)
