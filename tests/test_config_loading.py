"""The runtime and CLI share the editor's bounded, no-follow config reader."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from openpowermenu.core import DEFAULT_CONFIG, config_path, load_config
from openpowermenu.recovery import MAX_CONFIG_BYTES

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def target(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    return config_path()


def cli(option):
    return subprocess.run([sys.executable, str(ROOT / 'run.py'), option], cwd=ROOT,
                          capture_output=True, text=True, timeout=10)


@pytest.mark.parametrize('existing_directory', [False, True])
def test_missing_config_returns_independent_defaults_without_writing(target, existing_directory):
    if existing_directory:
        target.parent.mkdir(parents=True)
    original = deepcopy(DEFAULT_CONFIG)
    loaded = load_config()
    assert loaded == original
    loaded['menu'].clear()
    assert load_config(target) == DEFAULT_CONFIG == original
    result = cli('--check')
    assert result.returncode == 0, result.stderr
    assert '(using defaults)' in result.stdout
    assert target.parent.exists() == existing_directory
    assert not target.exists()
    if existing_directory:
        assert list(target.parent.iterdir()) == []


def test_legacy_config_preserves_values_metadata_and_defaults(target):
    target.parent.mkdir(parents=True)
    legacy = {'menu': [{'submenu': 'Café', 'items': [{'label': 'Quoted arguments',
               'command': [sys.executable, '-c', 'raise SystemExit(99)', 'two words'],
               'custom': {'kept': [1, 2]}}]}], 'appearance': 'aero', 'custom': ['kept']}
    payload = json.dumps(legacy, ensure_ascii=False).encode('utf-8')
    target.write_bytes(payload)
    assert load_config() == {**deepcopy(DEFAULT_CONFIG), **legacy}
    result = cli('--widget-menu-json')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)[0]['title'] == 'Café'
    assert target.read_bytes() == payload
    assert list(target.parent.iterdir()) == [target]


def test_exact_byte_limit_remains_readable(target):
    target.parent.mkdir(parents=True)
    payload = b'{"menu":[]}'
    target.write_bytes(payload + b' ' * (MAX_CONFIG_BYTES - len(payload)))
    assert load_config()['menu'] == []
    result = cli('--check')
    assert result.returncode == 0, result.stderr


@pytest.fixture(params=['oversized', 'symlink', 'dangling-symlink', 'parent-symlink',
                       'dangling-parent-symlink', 'malformed', 'invalid-encoding',
                       'invalid-schema', 'excessive-nesting', 'directory', 'fifo'])
def unsafe_config(target, tmp_path, request):
    kind = request.param
    target.parent.mkdir(parents=True)
    outside = tmp_path / 'outside.json'
    outside.write_bytes(b'{"menu":[],"custom":"preserve me"}')
    if kind == 'oversized':
        target.write_bytes(b'{"menu":[]}' + b' ' * MAX_CONFIG_BYTES)
    elif kind == 'symlink':
        target.symlink_to(outside)
    elif kind == 'dangling-symlink':
        target.symlink_to(tmp_path / 'missing.json')
    elif kind in ('parent-symlink', 'dangling-parent-symlink'):
        target.parent.rmdir()
        external_directory = tmp_path / 'external-config'
        if kind == 'parent-symlink':
            external_directory.mkdir()
            (external_directory / target.name).write_bytes(outside.read_bytes())
        target.parent.symlink_to(external_directory, target_is_directory=True)
    elif kind == 'directory':
        target.mkdir()
    elif kind == 'fifo':
        os.mkfifo(target)
    else:
        target.write_bytes({'malformed': b'{broken', 'invalid-encoding': b'\xff',
                            'invalid-schema': b'{"menu":false}',
                            'excessive-nesting': b'[' * 2000 + b']' * 2000}[kind])
    # Observe all actual test files and link entries, without following links.
    def snapshot():
        files = {}
        for directory, directories, names in os.walk(tmp_path, followlinks=False):
            for name in directories + names:
                path = Path(directory) / name
                info = path.lstat()
                files[str(path.relative_to(tmp_path))] = (
                    info.st_mode, info.st_ino, info.st_size,
                    os.readlink(path) if path.is_symlink() else path.read_bytes() if path.is_file() else None)
        return files
    before = snapshot()
    yield target
    assert snapshot() == before


def test_load_rejects_unsafe_or_invalid_config(unsafe_config):
    if unsafe_config.is_fifo():
        # A regression to blocking reads must time out instead of hanging pytest.
        result = subprocess.run([sys.executable, '-c',
                                 'from openpowermenu.core import load_config; load_config()'],
                                cwd=ROOT, capture_output=True, text=True, timeout=5)
        assert result.returncode == 1
        assert 'ValueError: Configuration and backup files must be regular files' in result.stderr
        return
    with pytest.raises((OSError, ValueError)):
        load_config(unsafe_config)


@pytest.mark.parametrize('option', ['--check', '--widget-menu-json', '--show-launcher-button'])
def test_cli_reports_bad_config_without_fallback_or_writes(unsafe_config, option):
    result = cli(option)
    assert result.returncode == 2, result.stdout + result.stderr
    assert not result.stdout
    assert result.stderr.startswith('Could not restore launcher visibility:' if option == '--show-launcher-button'
                                    else f'Invalid {unsafe_config}:')
    assert 'Traceback' not in result.stderr
