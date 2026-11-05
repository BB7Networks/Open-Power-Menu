"""Real install engines and archives in isolated XDG directories, no live KDE."""
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


class PrivateEnvironment(dict):
    def __repr__(self):
        return '<isolated XDG environment; inherited values hidden>'


def run(*args, env=None, cwd=ROOT, input=None):
    result = subprocess.run(args, cwd=cwd, env=env, input=input,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture
def isolated_install(tmp_path):
    tools = tmp_path / 'tools'
    tools.mkdir()
    # Stand-ins cover the kpackagetool control flow, never modify a real desktop.
    (tools / 'kpackagetool6').write_text('''#!/usr/bin/env python3
import os,pathlib,shutil,sys
args=sys.argv[1:]
target=pathlib.Path(os.environ['XDG_DATA_HOME'])/'plasma/plasmoids/org.openpowermenu.start'
if '--remove' in args:
 shutil.rmtree(target,ignore_errors=True)
else:
 source=pathlib.Path(args[-1])
 if target.exists(): shutil.rmtree(target)
 shutil.copytree(source,target)
''')
    for tool in ('busctl', 'kbuildsycoca6'):
        (tools / tool).write_text('#!/bin/sh\nexit 0\n')
    for tool in tools.iterdir():
        tool.chmod(0o755)
    (tools / 'python3').write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
    (tools / 'python3').chmod(0o755)
    env = PrivateEnvironment({**os.environ, 'XDG_CONFIG_HOME': str(tmp_path / 'config'),
           'XDG_DATA_HOME': str(tmp_path / 'data'), 'XDG_BIN_HOME': str(tmp_path / 'bin'),
           'XDG_CACHE_HOME': str(tmp_path / 'cache'), 'PATH': str(tools) + os.pathsep + os.environ['PATH']})
    return tmp_path, env


@pytest.mark.parametrize('previous_version', ['0.4.16', '0.4.17'])
def test_upgrade_preserves_menu_panel_and_widget_backup(isolated_install, previous_version):
    temp, env = isolated_install
    config = temp / 'config/open-power-menu/menu.json'
    config.parent.mkdir(parents=True)
    custom = {'version': 1, 'menu': [{'label': 'My existing command', 'command': ['echo', 'unchanged']}],
              'hide_original_launcher': True}
    config.write_text(json.dumps(custom))
    before = config.read_bytes()
    panel = temp / 'config/plasma-org.kde.plasma.desktop-appletsrc'
    panel.write_text('existing favorites and panel layout')
    widget = temp / 'data/plasma/plasmoids/org.openpowermenu.start'
    widget.mkdir(parents=True)
    (widget / 'metadata.json').write_text(json.dumps({'KPlugin': {'Version': previous_version}}))
    (widget / 'previous.txt').write_text('old widget')
    run('bash', 'scripts/install-core.sh', env=env)
    assert config.read_bytes() == before
    assert panel.read_text() == 'existing favorites and panel layout'
    assert not (widget / 'previous.txt').exists()
    backups = list((temp / 'data/open-power-menu/widget-backups').iterdir())
    assert len(backups) == 1
    assert (backups[0] / 'previous.txt').read_text() == 'old widget'
    assert json.loads((backups[0] / 'metadata.json').read_text())['KPlugin']['Version'] == previous_version
    launcher = temp / 'bin/open-power-menu'
    assert stat.S_IMODE(launcher.stat().st_mode) == 0o755
    assert 'Open Power Menu v0.4.17' in run(str(launcher), '--check', env=env).stdout
    run('bash', 'scripts/uninstall-core.sh', env=env)
    assert config.read_bytes() == before
    assert panel.read_text() == 'existing favorites and panel layout'
    assert not launcher.exists() and not widget.exists()


def test_fresh_install_generates_current_defaults_and_repeat_install_preserves_them(isolated_install):
    temp, env = isolated_install
    run('bash', 'scripts/install-core.sh', env=env)
    path = temp / 'config/open-power-menu/menu.json'
    original = path.read_bytes()
    assert {'action': 'printers'} in json.loads(original)['menu']
    assert json.loads(original)['backup_retention'] == 10
    run('bash', 'scripts/install-core.sh', env=env)
    assert path.read_bytes() == original
    assert (temp / 'data/dbus-1/services/org.openpowermenu.Service.service').is_file()


def test_friendly_wrappers(isolated_install):
    pytest.importorskip('PySide6.QtDBus')
    temp, env = isolated_install
    if os.geteuid() == 0:
        pytest.skip('Friendly installer intentionally refuses root')
    assert 'SUCCESS' in run('bash', 'Install.sh', env=env).stdout
    assert (temp / 'bin/open-power-menu').exists()
    assert 'Cancelled' in run('bash', 'Uninstall.sh', env=env, input='n\n').stdout
    assert (temp / 'bin/open-power-menu').exists()
    run('bash', 'Uninstall.sh', env=env, input='y\n')
    assert not (temp / 'bin/open-power-menu').exists()
    assert (temp / 'config/open-power-menu/menu.json').exists()


def test_release_archives_complete_clean_consistent_and_extractable(tmp_path):
    run('bash', 'scripts/build-release.sh')
    run('bash', 'scripts/build-widget-only.sh')
    version = json.loads((ROOT / 'plasmoid/metadata.json').read_text())['KPlugin']['Version']
    prefix = f'OpenPowerMenu-v{version}/'
    archive = ROOT / f'dist/OpenPowerMenu-EZ-v{version}.zip'
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        names = {name for name in zipped.namelist() if not name.endswith('/')}
        for relative in ['Install.sh', 'Uninstall.sh', 'scripts/install-core.sh', 'scripts/uninstall-core.sh',
                         'openpowermenu/launching.py', 'plasmoid/metadata.json', 'docs/KDE-STORE.md']:
            assert prefix + relative in names
        assert len({name.casefold() for name in names}) == len(names)
        assert not any('__pycache__' in name or name.endswith('.pyc') or name.endswith('/menu.json') for name in names)
        assert json.loads(zipped.read(prefix + 'plasmoid/metadata.json'))['KPlugin']['Version'] == version
        extracted = tmp_path / 'extracted source with spaces'
        zipped.extractall(extracted)
    with tarfile.open(ROOT / f'dist/OpenPowerMenu-EZ-v{version}.tar.gz') as tar:
        assert {member.name for member in tar.getmembers() if member.isfile()} == names
    with zipfile.ZipFile(ROOT / f'dist/org.openpowermenu.start-{version}.plasmoid') as widget:
        assert widget.testzip() is None
        assert 'metadata.json' in widget.namelist() and 'contents/ui/main.qml' in widget.namelist()
    run('sha256sum', '-c', 'SHA256SUMS', cwd=ROOT / 'dist')
    run(sys.executable, 'run.py', '--check', cwd=extracted / prefix)
