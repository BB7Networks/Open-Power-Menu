"""Source checkout scripts give guidance without touching the user's session."""
import os
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('script', ['install.sh', 'uninstall.sh'])
@pytest.mark.parametrize('arguments', [[], ['--rollback'], ['--recover'], ['--force']])
def test_source_guidance_is_non_mutating(tmp_path, script, arguments):
    profile = tmp_path/'profile with spaces';profile.mkdir()
    env = dict(os.environ, HOME=str(profile), XDG_CONFIG_HOME=str(profile/'config'),
               XDG_DATA_HOME=str(profile/'data'), XDG_BIN_HOME=str(profile/'bin'), XDG_CACHE_HOME=str(profile/'cache'))
    for name in ('menu.json', 'plasma-org.kde.plasma.desktop-appletsrc', 'kglobalshortcutsrc', 'recovery-snapshot'):
        (profile/name).write_text('preserve '+name)
    before = {str(p.relative_to(profile)): p.read_bytes() for p in profile.rglob('*') if p.is_file()}
    tools=tmp_path/'tools';tools.mkdir()
    marker=tmp_path/'unexpected-operation'
    for name in ('sudo','pacman','apt','curl','wget','python','python3','kpackagetool6','qdbus6','systemctl'):
        p=tools/name;p.write_text('#!/bin/sh\ntouch "$OPM_UNEXPECTED_OPERATION"\nexit 99\n');p.chmod(0o755)
    env.update(PATH=str(tools)+':'+env['PATH'], OPM_UNEXPECTED_OPERATION=str(marker))
    result=subprocess.run(['bash', str(ROOT/script), *arguments], cwd=profile, env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert 'native' in result.stdout.lower() and 'install.sh' in result.stdout
    assert not marker.exists()
    assert before == {str(p.relative_to(profile)): p.read_bytes() for p in profile.rglob('*') if p.is_file()}
    assert not any(p.is_dir() for p in profile.iterdir())


@pytest.mark.parametrize('script', ['install.sh','uninstall.sh','scripts/install-core.sh','scripts/uninstall-core.sh'])
def test_legacy_entrypoints_require_explicit_fixture_opt_in(tmp_path, script):
    env=dict(os.environ, HOME=str(tmp_path))
    env.pop('OPM_LEGACY_FIXTURE',None)
    result=subprocess.run(['bash', str(ROOT/'legacy/1.0.1'/script)], env=env, capture_output=True, text=True)
    assert result.returncode == 1 and 'fixture' in (result.stdout+result.stderr).lower()
    assert list(tmp_path.iterdir()) == []
