"""Real disposable user installs and private D-Bus activation, including 1.0.1.
Python is test tooling only; the final runtime image excludes it entirely.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import unittest

parser = argparse.ArgumentParser()
parser.add_argument('--bundle', type=Path, required=True)
parser.add_argument('--legacy', type=Path, required=True)
args, remaining = parser.parse_known_args()
BUNDLE = args.bundle.resolve()
os.umask(0o077)
INSTALLER = BUNDLE / 'app/bin/open-power-menu-install'

class Packaging(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=('opm-legacy-' if 'legacy_upgrade' in self._testMethodName else 'opm package '))
        self.root = Path(self.temp.name)
        self.env = {**os.environ, 'XDG_DATA_HOME': str(self.root/'data'),
                    'XDG_CONFIG_HOME': str(self.root/'config'), 'XDG_BIN_HOME': str(self.root/'bin'),
                    'XDG_CACHE_HOME': str(self.root/'cache'), 'XDG_RUNTIME_DIR': str(self.root/'runtime'),
                    'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software'}
        for key in ('XDG_DATA_HOME','XDG_CONFIG_HOME','XDG_BIN_HOME','XDG_CACHE_HOME','XDG_RUNTIME_DIR'):
            Path(self.env[key]).mkdir(mode=0o700)
        self.bus = subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],env=self.env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        self.env['DBUS_SESSION_BUS_ADDRESS'] = self.bus.stdout.readline().strip()
        self.data = Path(self.env['XDG_DATA_HOME'])
        self.app = self.data/'open-power-menu'
        self.config = Path(self.env['XDG_CONFIG_HOME'])
        (self.config/'open-power-menu').mkdir()
        self.personal = {'menu':[], 'launcher_applet_id':77, 'hide_original_launcher':True, 'unknown_metadata':{'keep':42}}
        (self.config/'open-power-menu/menu.json').write_text(json.dumps(self.personal))
        (self.config/'kglobalshortcutsrc').write_text('[Plasma]\nactivate widget 77=none,Meta+X,Disabled by user\n')
        (self.config/'plasma-org.kde.plasma.desktop-appletsrc').write_text('[Containments][1][Applets][77]\nplugin=org.openpowermenu.start\n[Containments][1][Applets][77][Configuration][General]\nopmDefaultShortcutTried=true\n')
        (self.config/'open-power-menu/menu.json.bak-user').write_text('personal recovery')
        self.original = self.settings()
    def settings(self):
        return {str(p.relative_to(self.config)):p.read_bytes() for p in self.config.rglob('*') if p.is_file()}
    def invoke(self,*arguments,ok=True,extra=None):
        p = subprocess.run([str(INSTALLER),*map(str,arguments)],env={**self.env,**(extra or {})},capture_output=True,text=True,timeout=40)
        if ok:self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        else:self.assertNotEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertEqual(self.original,self.settings(),'Personal state changed')
        return p
    def install(self,**kwargs):return self.invoke('--install',BUNDLE,**kwargs)
    def pid(self):
        p=subprocess.run(['busctl','--user','call','org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetConnectionUnixProcessID','s','org.openpowermenu.Service'],env=self.env,capture_output=True,text=True)
        return int(p.stdout.split()[1]) if p.returncode==0 else None
    def tearDown(self):
        pid=self.pid()
        if pid:
            try:os.kill(pid,signal.SIGTERM)
            except ProcessLookupError:pass
        self.bus.terminate();self.bus.wait(timeout=5);self.bus.stdout.close();self.temp.cleanup()
    def test_clean_reinstall_and_uninstall(self):
        self.install();self.assertTrue((self.app/'bin/open-power-menu-editor').is_file())
        self.assertNotIn('python',(self.data/'dbus-1/services/org.openpowermenu.Service.service').read_text())
        first=self.pid();self.install();self.assertNotEqual(first,self.pid())
        self.invoke('--uninstall',ok=False) # panel must relinquish launcher mask first
        (self.config/'plasma-org.kde.plasma.desktop-appletsrc').write_text('[Containments]\n')
        self.original=self.settings();self.invoke('--uninstall')
        self.assertFalse(self.app.exists());self.assertTrue((self.data/'open-power-menu-recovery/native-installs').exists())
        self.invoke('--rollback');self.assertTrue(self.app.exists())
    def test_legacy_upgrade_and_rollback(self):
        # Execute the actual released installer against the disposable profile.
        p=subprocess.run(['bash',str(args.legacy.resolve()/'scripts/install-core.sh')],env=self.env,capture_output=True,text=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stderr)
        legacy_bytes=(self.app/'run.py').read_bytes()
        recovery=self.data/'open-power-menu-recovery/widget-backups/manual';recovery.mkdir(parents=True);(recovery/'keep').write_text('history')
        embedded=self.app/'widget-backups';embedded.mkdir(exist_ok=True);(embedded/'keep').write_text('older history')
        # Start actual legacy Python service through its installed activation file.
        subprocess.run(['busctl','--user','call','org.openpowermenu.Service','/OpenPowerMenu','org.openpowermenu.Service','Ping'],env=self.env,check=True,stdout=subprocess.DEVNULL)
        old_pid=self.pid();upgrade=self.install();self.assertNotEqual(old_pid,self.pid())
        # The optional review is read-only and one-time even on an unattended upgrade.
        state=self.data/'open-power-menu-recovery/dependency-review/native-2.1.json'
        self.assertTrue(state.exists(), upgrade.stdout + upgrade.stderr)
        self.assertTrue(json.loads(state.read_text())['shown'])
        # A missing legacy runtime must stop rollback before replacing native files.
        tools=self.root/'missing-runtime';tools.mkdir()
        fake=tools/'python3';fake.write_text('#!/bin/sh\nexit 1\n');fake.chmod(0o700)
        failed=self.invoke('--rollback',ok=False,extra={'PATH':str(tools)+os.pathsep+os.environ['PATH']})
        self.assertIn('restore the runtime first',failed.stdout)
        self.assertTrue((self.app/'bin/open-power-menu-native').exists())
        self.assertFalse((self.data/'open-power-menu-recovery/native-installs/active.json').exists())
        self.invoke('--rollback')
        self.assertEqual((self.app/'run.py').read_bytes(),legacy_bytes)
        self.assertEqual((embedded/'keep').read_text(),'older history');self.assertEqual((recovery/'keep').read_text(),'history')
        self.assertEqual(self.original,self.settings())
    def test_interrupted_and_partial_failure(self):
        self.install();before=(self.data/'dbus-1/services/org.openpowermenu.Service.service').read_bytes()
        for fault,index in [('OPM_INSTALL_CRASH_AFTER','2'),('OPM_INSTALL_CRASH_GAP','0')]:
            p=self.install(ok=False,extra={fault:index});self.assertEqual(p.returncode,86)
            self.invoke('--recover');self.invoke('--recover');self.assertIsNotNone(self.pid())
        self.assertEqual((self.data/'dbus-1/services/org.openpowermenu.Service.service').read_bytes(),before)
        self.install(ok=False,extra={'OPM_INSTALL_FAIL_AFTER':'4'})
        self.assertFalse((self.data/'open-power-menu-recovery/native-installs/active.json').exists())
        self.install()
    def test_dependency_and_architecture_refusal(self):
        self.install();pid=self.pid()
        for kind in ('dependency','architecture','distribution'):
            bundle=self.root/kind;shutil.copytree(BUNDLE,bundle)
            spec=json.loads((bundle/'bundle.json').read_text())
            if kind!='dependency':
                spec['cpu' if kind=='architecture' else 'os']='unsupported';(bundle/'bundle.json').write_text(json.dumps(spec))
            else:
                executable=bundle/'app/bin/open-power-menu-editor';executable.write_text('#!/missing/interpreter\n')
                (bundle/'bundle.json').unlink()
                subprocess.run([str(INSTALLER),'--seal-bundle',str(bundle)],check=True,env=self.env)
            self.invoke('--install',bundle,ok=False)
            self.assertEqual(self.pid(),pid)
    def test_collision_symlink_and_modified_receipt(self):
        launcher=Path(self.env['XDG_BIN_HOME'])/'open-power-menu';launcher.write_text('unrelated')
        self.install(ok=False);self.assertEqual(launcher.read_text(),'unrelated');launcher.unlink()
        launcher.symlink_to('/bin/true');self.install(ok=False);self.assertTrue(launcher.is_symlink());launcher.unlink()
        self.install();launcher.write_text('changed by user');self.install(ok=False);self.assertEqual(launcher.read_text(),'changed by user')
    def test_unrelated_service_owner(self):
        # Correct protocol but a backend running from the development bundle is unrelated.
        p=subprocess.Popen([str(BUNDLE/'app/bin/open-power-menu-native'),'--service','--bus-name','org.openpowermenu.Service'],env=self.env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            import time
            for _ in range(100):
                if self.pid():break
                time.sleep(.02)
            self.install(ok=False);self.assertIsNone(p.poll());self.assertFalse(self.app.exists())
        finally:p.terminate();p.wait(timeout=5)
    def test_failed_activation_rolls_back(self):
        self.bus.terminate();self.bus.wait(timeout=5);self.bus.stdout.close()
        policy=self.root/'deny.conf';policy.write_text('''<busconfig><type>session</type><listen>unix:tmpdir=/tmp</listen><standard_session_servicedirs/><policy context="default"><allow send_destination="*" eavesdrop="true"/><allow eavesdrop="true"/><allow own="*"/><deny own="org.openpowermenu.Service"/></policy></busconfig>''')
        self.bus=subprocess.Popen(['dbus-daemon','--config-file='+str(policy),'--nofork','--print-address=1'],env=self.env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        self.env['DBUS_SESSION_BUS_ADDRESS']=self.bus.stdout.readline().strip()
        self.install(ok=False);self.assertFalse(self.app.exists())
        self.assertFalse((self.data/'dbus-1/services/org.openpowermenu.Service.service').exists())
    def test_tampered_recovery_is_retained(self):
        self.install();self.install(ok=False,extra={'OPM_INSTALL_CRASH_AFTER':'2'})
        (self.app/'bin/open-power-menu-native').write_text('unexpected change')
        self.invoke('--recover',ok=False)
        self.assertTrue((self.data/'open-power-menu-recovery/native-installs/active.json').exists())
        self.assertEqual((self.app/'bin/open-power-menu-native').read_text(),'unexpected change')
    def test_committed_cleanup_preserves_changed_displaced_files(self):
        self.install()
        p=self.install(ok=False,extra={'OPM_INSTALL_CRASH_COMMIT':'1'})
        self.assertEqual(p.returncode,86)
        active=self.data/'open-power-menu-recovery/native-installs/active.json'
        transaction=json.loads(active.read_text())['id']
        displaced=self.data/('.opm-'+transaction+'-0-old')/'bin/open-power-menu-native'
        original=displaced.read_bytes();displaced.write_bytes(b'changed after commit')
        self.invoke('--recover',ok=False)
        self.assertTrue(active.exists());self.assertEqual(displaced.read_bytes(),b'changed after commit')
        displaced.write_bytes(original)
        self.invoke('--recover');self.assertFalse(active.exists());self.assertIsNotNone(self.pid())

if __name__=='__main__':unittest.main(argv=['packaging.py',*remaining])
