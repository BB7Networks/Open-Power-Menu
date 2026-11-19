#!/usr/bin/env python3
"""Application selection in private XDG trees. Never launches selected actions."""
import argparse
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--probe', required=True)
parser.add_argument('--live-audit', help='Record this disposable image\'s real application/module availability')
args, remainder = parser.parse_known_args()
PROBE = str(Path(args.probe).resolve())


class ApplicationResolution(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='opm-applications-'); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('bin', 'config', 'data/applications', 'cache', 'system', 'policy', 'home'):
            (self.root/name).mkdir(parents=True, exist_ok=True)
        # Supply a real MIME database and a private XDG menu, without exposing
        # installed application entries. KService cannot build MIME offers from
        # desktop files alone when its application menu is absent.
        (self.root/'system/mime').symlink_to('/usr/share/mime', target_is_directory=True)
        (self.root/'config/menus').mkdir()
        (self.root/'config/menus/applications.menu').write_text('<Menu><Name>Applications</Name><DefaultAppDirs/><Include><All/></Include></Menu>')
        self.env = {**os.environ, 'HOME': str(self.root/'home'), 'PATH': str(self.root/'bin'),
                    'XDG_CURRENT_DESKTOP': 'KDE', 'XDG_SESSION_TYPE': 'x11', 'QT_QPA_PLATFORM': 'offscreen',
                    'XDG_DATA_HOME': str(self.root/'data'), 'XDG_DATA_DIRS': str(self.root/'system'),
                    'XDG_CONFIG_HOME': str(self.root/'config'), 'XDG_CONFIG_DIRS': str(self.root/'policy'),
                    'XDG_CACHE_HOME': str(self.root/'cache'), 'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/opm-no-bus',
                    'DBUS_SYSTEM_BUS_ADDRESS': 'unix:path=/opm-no-bus'}
        self.binary('kioclient6')
        self.builder = shutil.which('kbuildsycoca6')
        self.assertTrue(self.builder, 'KService cache builder is required')

    def binary(self, name, body='exit 0'):
        path = self.root/'bin'/name
        path.write_text('#!/bin/sh\n'+body+'\n'); path.chmod(0o755)
        return path

    def desktop(self, name, program, extra=''):
        path = self.root/'data/applications'/name
        path.write_text('[Desktop Entry]\nType=Application\nName='+name+'\nExec='+program+'\n'+extra+'\n')
        return path

    def resolve(self, action=None, item=None):
        config = self.root/'menu.json'
        config.write_text(json.dumps({'menu': [item if item is not None else {'action': action}]}))
        subprocess.run([self.builder, '--noincremental'], env=self.env, capture_output=True, check=True, timeout=15)
        result = subprocess.run([PROBE, config], env=self.env, capture_output=True, text=True, check=True, timeout=15)
        return json.loads(result.stdout)[0]['argv']

    def test_explicit_custom_command_wins(self):
        self.binary('chosen'); self.binary('dolphin')
        self.assertEqual(self.resolve(item={'label': 'File Manager', 'command': ['chosen', 'literal'],
                                           'future': {'keep': True}, 'builtin_id': 'files'}), ['chosen', 'literal'])
        self.assertEqual(self.resolve(item={'commands': [{'argv': ['chosen', 'literal'],
                                           'dbus_service': 'org.test.FutureMetadata'}]}), ['chosen', 'literal'])

    def test_default_directory_handler_beats_fallback(self):
        self.binary('dolphin'); self.binary('chosen-files')
        chosen = self.desktop('org.test.Files.desktop', 'chosen-files %U', 'MimeType=inode/directory;')
        self.desktop('org.kde.dolphin.desktop', 'dolphin %U', 'MimeType=inode/directory;')
        (self.root/'config/mimeapps.list').write_text('[Default Applications]\ninode/directory=org.test.Files.desktop;\n')
        self.assertEqual(self.resolve('files'), [str(self.root/'bin/kioclient6'), 'exec', str(chosen)])

    def test_kde_terminal_service_and_legacy_preference(self):
        self.binary('konsole'); self.binary('chosen-terminal')
        chosen = self.desktop('org.test.Terminal.desktop', 'chosen-terminal')
        (self.root/'config/kdeglobals').write_text('[General]\nTerminalService=org.test.Terminal.desktop\n')
        self.assertEqual(self.resolve('terminal')[-1], str(chosen))
        (self.root/'config/kdeglobals').write_text('[General]\nTerminalApplication=chosen-terminal --new-window\n')
        self.assertEqual(self.resolve('terminal'), ['chosen-terminal', '--new-window'])

    def test_xdg_terminal_preference_and_missing_selection(self):
        self.binary('konsole'); self.binary('chosen-terminal')
        chosen = self.desktop('org.test.Terminal.desktop', 'chosen-terminal')
        self.binary('xdg-terminal-exec', '[ "$1" = --print-id ] || exit 3\nprintf "%s\\n" org.test.Terminal.desktop')
        self.assertEqual(self.resolve('terminal'), ['xdg-terminal-exec'])
        self.desktop('org.test.Terminal.desktop', 'chosen-terminal', 'Actions=New;\n[Desktop Action New]\nName=New\nExec=chosen-terminal --new')
        self.binary('xdg-terminal-exec', '[ "$1" = --print-id ] || exit 3\nprintf "%s\\n" org.test.Terminal.desktop:New')
        self.assertEqual(self.resolve('terminal'), ['xdg-terminal-exec'])
        chosen.unlink()
        self.assertEqual(self.resolve('terminal'), ['konsole'])

    def test_appstream_preference_beats_installed_order(self):
        for name in ('pamac-manager', 'plasma-discover', 'gnome-software'): self.binary(name)
        self.desktop('org.kde.discover.desktop', 'plasma-discover', 'MimeType=x-scheme-handler/appstream;')
        chosen = self.desktop('org.gnome.Software.desktop', 'gnome-software', 'MimeType=x-scheme-handler/appstream;')
        (self.root/'config/mimeapps.list').write_text('[Default Applications]\nx-scheme-handler/appstream=org.gnome.Software.desktop;\n')
        self.assertEqual(self.resolve('applications')[-1], str(chosen))

    def test_each_supported_software_manager(self):
        for program, desktop in (('pamac-manager', 'org.manjaro.pamac.manager.desktop'),
                                 ('plasma-discover', 'org.kde.discover.desktop'),
                                 ('gnome-software', 'org.gnome.Software.desktop'),
                                 ('octopi', 'octopi.desktop'),
                                 ('snap-store', 'snap-store_ubuntu-software.desktop'),
                                 ('snap-store', 'snap-store_app-center.desktop')):
            with self.subTest(program=program, desktop=desktop):
                executable = self.binary(program)
                entry = self.desktop(desktop, program)
                self.assertEqual(self.resolve('applications')[-1], str(entry))
                entry.unlink(); executable.unlink()
                self.assertEqual(self.resolve('applications'), [])

    def test_software_manager_desktop_and_distribution_priority(self):
        for program in ('pamac-manager', 'plasma-discover', 'gnome-software'):
            self.binary(program)
        expected = 'pamac-manager' if platform.freedesktop_os_release()['ID'] == 'manjaro' else 'plasma-discover'
        self.assertEqual(self.resolve('applications'), [expected])

    def test_default_remote_desktop_and_hardware_fallback(self):
        self.binary('krdc'); self.binary('remmina')
        entry = self.desktop('org.remmina.Remmina.desktop', 'remmina %U', 'MimeType=x-scheme-handler/rdp;')
        (self.root/'config/mimeapps.list').write_text('[Default Applications]\nx-scheme-handler/rdp=org.remmina.Remmina.desktop;\n')
        self.assertEqual(self.resolve('remote')[-1], str(entry))
        self.binary('konsole')
        self.assertEqual(self.resolve('hardware'), [])
        self.binary('inxi')
        self.assertEqual(self.resolve('hardware'), ['konsole', '--hold', '-e', 'inxi', '-Fzxx'])

    def test_invalid_registered_desktop_not_bypassed(self):
        self.binary('plasma-systemmonitor'); self.binary('gnome-system-monitor')
        for extra in ('Hidden=true', 'NoDisplay=true', 'OnlyShowIn=GNOME;', 'TryExec=opm-missing'):
            with self.subTest(extra=extra):
                self.desktop('org.kde.plasma-systemmonitor.desktop', 'plasma-systemmonitor', extra)
                self.assertEqual(self.resolve('monitor'), ['gnome-system-monitor'])
        self.desktop('org.kde.plasma-systemmonitor.desktop', 'opm-missing')
        self.assertEqual(self.resolve('monitor'), ['gnome-system-monitor'])

    def test_desktop_launch_semantics_are_delegated(self):
        self.binary('plasma-systemmonitor'); self.binary('actual-monitor')
        chosen = self.desktop('org.kde.plasma-systemmonitor.desktop', 'actual-monitor --flag %U',
                              'Terminal=true\nPath=/tmp\nDBusActivatable=true')
        self.assertEqual(self.resolve('monitor'), [str(self.root/'bin/kioclient6'), 'exec', str(chosen)])

    def test_kcm_capability_not_just_launcher(self):
        self.binary('systemsettings'); self.binary('kcmshell6', 'printf "%s\\n" unrelated-module')
        self.assertEqual(self.resolve('power'), [])
        self.assertEqual(self.resolve('network'), [])
        self.assertEqual(self.resolve('printers'), [])
        self.binary('kcmshell6', 'printf "%s\\n" kcm_powerdevilprofilesconfig kcm_networkmanagement kcm_printer_manager')
        for action, module in [('power', 'kcm_powerdevilprofilesconfig'), ('network', 'kcm_networkmanagement'), ('printers', 'kcm_printer_manager')]:
            with self.subTest(action=action): self.assertEqual(self.resolve(action), ['kcmshell6', module])

    def test_network_and_printer_fallbacks(self):
        self.binary('kcmshell6'); self.binary('nm-connection-editor'); self.binary('system-config-printer')
        self.assertEqual(self.resolve('network'), ['nm-connection-editor'])
        self.assertEqual(self.resolve('printers'), ['system-config-printer'])

    def test_recognized_alternatives_and_missing_tools(self):
        for action, program in [('applications','octopi'), ('files','nemo'), ('terminal','kitty'),
                                ('monitor','gnome-system-monitor'), ('disks','gnome-disks'), ('vms','virtualbox'),
                                ('remote','remmina'), ('system','hardinfo2'), ('hardware','hardinfo2'), ('logs','ksystemlog')]:
            with self.subTest(action=action):
                path = self.binary(program)
                self.assertEqual(self.resolve(action), [program])
                path.unlink()
                self.assertEqual(self.resolve(action), [])

    def test_logs_require_journalctl_and_settings_context(self):
        self.binary('konsole')
        self.assertEqual(self.resolve('logs'), [])
        self.binary('journalctl')
        self.assertEqual(self.resolve('logs')[:4], ['konsole','--hold','-e','journalctl'])
        self.binary('gnome-control-center')
        self.assertEqual(self.resolve('settings'), [])
        self.env['XDG_CURRENT_DESKTOP'] = 'GNOME'
        self.assertEqual(self.resolve('settings'), ['gnome-control-center'])

    def test_search_service_or_executable_required(self):
        self.binary('qdbus6')
        self.assertEqual(self.resolve('run'), [])
        self.binary('qdbus6', 'printf "%s\\n" org.kde.krunner')
        self.assertEqual(self.resolve('run')[1], 'org.kde.krunner')
        self.binary('qdbus6'); self.binary('krunner')
        self.assertEqual(self.resolve('run'), ['krunner'])


if __name__ == '__main__':
    if args.live_audit:
        result = subprocess.run([PROBE], capture_output=True, text=True, check=True, timeout=60)
        rows = json.loads(result.stdout)
        required = {'applications', 'files', 'terminal', 'settings', 'power', 'network', 'printers', 'monitor', 'system', 'run'}
        missing = [row['action'] for row in rows if row['action'] in required and not row['argv']]
        Path(args.live_audit).write_text(json.dumps({'os_release': Path('/etc/os-release').read_text(), 'actions': rows, 'missing_required': missing}, indent=2)+'\n')
        assert not missing, 'Missing expected KDE desktop capabilities: '+str(missing)
    else:
        unittest.main(argv=[__file__, *remainder])
