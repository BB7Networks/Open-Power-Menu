"""Real install engines and archives in isolated XDG directories, no live KDE."""
import json
import os
from pathlib import Path
import shlex
import shutil
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
    backups = list((temp / 'data/open-power-menu-recovery/widget-backups').iterdir())
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
    assert (backups[0] / 'previous.txt').read_text() == 'old widget'


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


def test_installed_application_entry_with_spaces_and_percent(isolated_install):
    from openpowermenu.desktop_apps import desktop_exec_argv, read_desktop_application
    temp, env = isolated_install
    env['XDG_BIN_HOME'] = str(temp / 'user bin 100%')
    run('bash', 'scripts/install-core.sh', env=env)
    desktop = read_desktop_application(temp / 'data/applications/org.openpowermenu.desktop')
    argv = desktop_exec_argv(desktop.exec_line, desktop.name, desktop.icon, desktop.desktop_file)
    assert argv == [str(temp / 'user bin 100%/open-power-menu')]
    assert 'Open Power Menu v' in run(*argv, '--check', env=env).stdout


def test_installed_standalone_reports_window_exposure(isolated_install):
    pytest.importorskip('PySide6.QtWidgets')
    import selectors
    import time
    temp, env = isolated_install
    run('bash', 'scripts/install-core.sh', env=env)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    launcher = str(temp / 'bin/open-power-menu')
    run(launcher, '--check', env=env)
    child = subprocess.Popen([launcher, '--diagnose-launch'], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = b''
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and b'"exposed": true' not in output:
                if selector.select(timeout=0.1):
                    chunk = os.read(child.stdout.fileno(), 4096)
                    if not chunk: break
                    output += chunk
        assert b'"event": "cli-start"' in output
        assert b'"exposed": true' in output, output.decode()
        assert child.poll() is None
    finally:
        child.terminate()
        child.communicate(timeout=5)


def test_friendly_wrappers(isolated_install):
    pytest.importorskip('PySide6.QtDBus')
    temp, env = isolated_install
    if os.geteuid() == 0:
        pytest.skip('Friendly installer intentionally refuses root')
    source = temp / 'source with spaces'
    shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns('.git', '.venv', 'dist', '__pycache__', '.pytest_cache'))
    assert 'SUCCESS' in run('bash', 'install.sh', cwd=source, env=env).stdout
    assert (temp / 'bin/open-power-menu').exists()
    assert 'Cancelled' in run('bash', 'uninstall.sh', cwd=source, env=env, input='n\n').stdout
    assert (temp / 'bin/open-power-menu').exists()
    run('bash', 'uninstall.sh', cwd=source, env=env, input='y\n')
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
        for relative in ['install.sh', 'uninstall.sh', 'scripts/install-core.sh', 'scripts/uninstall-core.sh',
                         'openpowermenu/launching.py', 'openpowermenu/layout_edit.py',
                         'openpowermenu/editor_toolbar.py', 'plasmoid/metadata.json', 'docs/KDE-STORE.md',
                         'openpowermenu/shortcut_setup.py',
                         'docs/IN-MENU-EDITING.md', 'plasmoid/contents/ui/LayoutEditor.qml',
                         'plasmoid/contents/ui/LayoutDraft.js', 'plasmoid/contents/ui/LayoutController.js']:
            assert prefix + relative in names
        assert len({name.casefold() for name in names}) == len(names)
        for wrapper in ('install.sh', 'uninstall.sh'):
            assert prefix + wrapper.capitalize() not in names
        assert not any('__pycache__' in name or name.endswith('.pyc') or name.endswith('/menu.json') for name in names)
        assert json.loads(zipped.read(prefix + 'plasmoid/metadata.json'))['KPlugin']['Version'] == version
        extracted = tmp_path / 'extracted source with spaces'
        zipped.extractall(extracted)
    with tarfile.open(ROOT / f'dist/OpenPowerMenu-EZ-v{version}.tar.gz') as tar:
        assert {member.name for member in tar.getmembers() if member.isfile()} == names
    with zipfile.ZipFile(ROOT / f'dist/org.openpowermenu.start-{version}.plasmoid') as widget:
        assert widget.testzip() is None
        assert 'metadata.json' in widget.namelist() and 'contents/ui/main.qml' in widget.namelist()
        for name in ('LayoutEditor.qml', 'LayoutDraft.js', 'LayoutController.js'):
            assert 'contents/ui/' + name in widget.namelist()
    run('sha256sum', '-c', 'SHA256SUMS', cwd=ROOT / 'dist')
    run(sys.executable, 'run.py', '--check', cwd=extracted / prefix)


def seed_snapshots(root, count=7):
    root.mkdir(parents=True, exist_ok=True)
    result = []
    for i in range(count):
        path = root / f'org.openpowermenu.start-20250101-0000{i:02d}-000000000'
        path.mkdir()
        (path / 'old.txt').write_text(str(i))
        result.append(path)
    return result


@pytest.mark.parametrize('keep', [5, 2])
def test_successful_upgrade_prunes_only_generated_snapshots(isolated_install, keep):
    from openpowermenu.widget_snapshots import recovery_path
    temp, env = isolated_install
    run('bash', 'scripts/install-core.sh', env=env)
    root = recovery_path(temp / 'data')
    old = seed_snapshots(root)
    manual = root / 'my-important-widget'
    manual.mkdir()
    (manual / 'keep').write_text('manual')
    external = temp / 'outside'
    external.mkdir()
    (external / 'keep').write_text('external')
    linked = root / 'org.openpowermenu.start-20000101-000000-000000000'
    linked.symlink_to(external, target_is_directory=True)
    # A nested link in a pruned snapshot must also preserve its destination.
    (old[0] / 'nested-link').symlink_to(external, target_is_directory=True)
    if keep != 5:
        env['OPM_WIDGET_BACKUP_RETENTION'] = str(keep)
    run('bash', 'scripts/install-core.sh', env=env)
    assert all(path.exists() for path in old[-(keep-1):])
    assert not any(path.exists() for path in old[:-(keep-1)])
    assert (external / 'keep').read_text() == 'external'
    assert linked.is_symlink() and (manual / 'keep').read_text() == 'manual'
    assert len([p for p in root.iterdir() if p.is_dir() and not p.is_symlink()]) == keep + 1


def test_failed_upgrade_preserves_all_history_and_previous_widget_snapshot(isolated_install):
    from openpowermenu.widget_snapshots import recovery_path
    temp, env = isolated_install
    run('bash', 'scripts/install-core.sh', env=env)
    root = recovery_path(temp / 'data')
    old = seed_snapshots(root)
    widget = temp / 'data/plasma/plasmoids/org.openpowermenu.start'
    (widget / 'last-working').write_text('recover me')
    (temp / 'tools/kpackagetool6').write_text('#!/bin/sh\nexit 1\n')
    env['OPM_WIDGET_BACKUP_RETENTION'] = '1'
    failed = subprocess.run(['bash', 'scripts/install-core.sh'], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=30)
    assert failed.returncode != 0
    assert all(path.exists() for path in old)
    newest = sorted(root.iterdir())[-1]
    assert (newest / 'last-working').read_text() == 'recover me'


@pytest.mark.parametrize('operation', ['install', 'uninstall'])
def test_legacy_snapshot_migration_preserves_manual_files_and_collisions(isolated_install, operation):
    from openpowermenu.widget_snapshots import recovery_path
    temp, env = isolated_install
    run('bash', 'scripts/install-core.sh', env=env)
    legacy = temp / 'data/open-power-menu/widget-backups'
    old = seed_snapshots(legacy, 1)[0]
    root = recovery_path(temp / 'data')
    existing = seed_snapshots(root, 1)[0]
    (existing / 'old.txt').write_text('new location')
    (legacy / 'manual.txt').write_text('keep manual')
    (legacy / 'manual-link').symlink_to(temp / 'missing')
    run('bash', f'scripts/{operation}-core.sh', env=env)
    assert (existing / 'old.txt').read_text() == 'new location'
    assert list(root.glob('legacy-*/old.txt'))[0].read_text() == '0'
    assert (root / 'manual.txt').read_text() == 'keep manual'
    assert (root / 'manual-link').is_symlink()
    assert not old.exists()


def test_copy_failure_cleans_partial_snapshot_and_preserves_widget(tmp_path, monkeypatch):
    from openpowermenu import widget_snapshots as snapshots
    widget = tmp_path / 'plasma/plasmoids/org.openpowermenu.start'
    widget.mkdir(parents=True)
    (widget / 'keep').write_text('working')
    def fail(*args, **kwargs):
        raise OSError('disk full')
    monkeypatch.setattr(snapshots.shutil, 'copytree', fail)
    with pytest.raises(OSError, match='disk full'):
        snapshots.snapshot(tmp_path)
    assert (widget / 'keep').read_text() == 'working'
    assert list(snapshots.recovery_path(tmp_path).iterdir()) == []


@pytest.mark.parametrize('unsafe', ['widget-link', 'history-link', 'legacy-link', 'invalid-retention'])
def test_prepare_failure_aborts_before_replacing_installed_files(isolated_install, unsafe):
    temp, env = isolated_install
    run('bash', 'scripts/install-core.sh', env=env)
    backend = temp / 'data/open-power-menu/run.py'
    backend.write_text('previous backend marker')
    external = temp / 'outside'
    external.mkdir()
    (external / 'keep').write_text('untouched')
    if unsafe == 'invalid-retention':
        env['OPM_WIDGET_BACKUP_RETENTION'] = '0'
    else:
        target = {'widget-link': temp / 'data/plasma/plasmoids/org.openpowermenu.start',
                  'history-link': temp / 'data/open-power-menu-recovery',
                  'legacy-link': temp / 'data/open-power-menu/widget-backups'}[unsafe]
        if target.exists():
            target.rename(target.with_name('previous'))
        target.symlink_to(external, target_is_directory=True)
    result = subprocess.run(['bash', 'scripts/install-core.sh'], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert backend.read_text() == 'previous backend marker'
    assert (external / 'keep').read_text() == 'untouched'


def test_uninstall_aborts_when_legacy_history_cannot_be_migrated(isolated_install):
    temp, env = isolated_install
    run('bash', 'scripts/install-core.sh', env=env)
    legacy = temp / 'data/open-power-menu/widget-backups'
    legacy.symlink_to(temp / 'unreadable-or-missing', target_is_directory=True)
    result = subprocess.run(['bash', 'scripts/uninstall-core.sh'], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert (temp / 'bin/open-power-menu').exists() and legacy.is_symlink()
