"""Content conflicts, non-executing previews, and failure-safe recovery."""
from copy import deepcopy
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from openpowermenu.core import DEFAULT_CONFIG, MenuValidationError, save_config, validate_configuration
from openpowermenu.recovery import (ConfigurationConflict, configuration_summary, current_revision,
                                   decode_configuration, list_backups, restore_backup)


@pytest.fixture
def configuration(tmp_path):
    target = tmp_path / 'config/menu.json'
    config = deepcopy(DEFAULT_CONFIG)
    config['menu'] = [{'submenu': 'Work', 'custom': {'nested': [1, 2]}, 'items': [
        {'label': 'Literal arguments', 'command': ['echo', 'a b', ';'], 'custom': [3]}]}]
    save_config(config, target)
    return target, config


@pytest.mark.parametrize('change', ['contents', 'replacement', 'deletion'])
def test_conflicts_include_same_mtime_and_identical_replacement(configuration, change):
    target, config = configuration
    revision = current_revision(target)
    timestamp = target.stat().st_mtime_ns
    if change == 'contents':
        target.write_text('{"menu": []}')
        os.utime(target, ns=(timestamp, timestamp))
    elif change == 'replacement':
        other = target.with_name('replacement')
        other.write_bytes(target.read_bytes())
        other.replace(target)
    else:
        target.unlink()
    current = current_revision(target)
    with pytest.raises(ConfigurationConflict):
        save_config(config, target, expected_revision=revision)
    assert current_revision(target) == current
    assert not list_backups(target)


def test_explicit_overwrite_keeps_external_bytes_even_with_retention_zero(configuration):
    target, config = configuration
    target.write_bytes(b'{broken external JSON')
    external = current_revision(target)
    config['backup_retention'] = 0
    save_config(config, target, expected_revision=external, recovery_reason='overwrite')
    copies = list(target.parent.glob('menu.json.pre-overwrite-*'))
    assert len(copies) == 1 and copies[0].read_bytes() == external.content
    assert decode_configuration(target.read_bytes()) == config


@pytest.mark.parametrize('keep', [0, 1, 10])
def test_restore_preserves_current_and_source_and_metadata(configuration, keep):
    target, config = configuration
    config['backup_retention'] = keep
    source = target.with_name('menu.json.bak-20000101T000000000000Z')
    source.write_text(json.dumps(config))
    newer = deepcopy(config)
    newer['menu'] = []
    save_config(newer, target)
    source.write_text(json.dumps(config))  # may have been rotated by the setup save
    active = current_revision(target)
    restore_backup(target, source.name, active)
    assert decode_configuration(target.read_bytes()) == config
    assert source.exists()
    copies = list(target.parent.glob('menu.json.pre-restore-*'))
    assert len(copies) == 1 and copies[0].read_bytes() == active.content
    assert copies[0].stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('failure', ['backup-copy', 'replace', 'temp-write'])
def test_failed_restore_preserves_file_source_and_history(configuration, failure):
    target, config = configuration
    config['backup_retention'] = 1
    source = target.with_name('menu.json.bak-manual')
    source.write_text(json.dumps(config))
    history = target.with_name('menu.json.bak-20000101T000000000000Z')
    history.write_bytes(b'old history')
    before = target.read_bytes()
    operation = {'backup-copy': 'shutil.copyfileobj', 'replace': 'os.replace', 'temp-write': 'os.fsync'}[failure]
    with patch('openpowermenu.core.' + operation, side_effect=OSError('disk full')):
        with pytest.raises(OSError, match='disk full'):
            restore_backup(target, source.name, current_revision(target))
    assert target.read_bytes() == before
    assert source.exists() and history.read_bytes() == b'old history'
    assert not list(target.parent.glob('.menu-*.tmp'))


def test_preview_is_nonexecuting_and_marks_corrupt_backups(configuration):
    target, config = configuration
    valid = target.with_name('menu.json.bak-manual')
    valid.write_text(json.dumps(config))
    target.with_name('menu.json.bak-corrupt').write_text('{broken')
    target.with_name('menu.json.bak-link').symlink_to(valid)
    target.with_name('unrelated.json').write_text('{}')
    with patch('subprocess.Popen', side_effect=AssertionError('preview ran a process')):
        rows = list_backups(target)
        assert {row.name for row in rows} == {'menu.json.bak-manual', 'menu.json.bak-corrupt'}
        assert sum(row.config is not None for row in rows) == 1
        assert all(row.local_time for row in rows)
        preview = configuration_summary(config, {**config, 'menu': []})
    assert '2 entries' in preview and 'Work' in preview and 'Literal arguments' in preview
    assert 'Changed sections/settings: menu' in preview


@pytest.mark.parametrize('bad', ['corrupt', 'missing', 'symlink', 'outside', 'changed', 'fifo'])
def test_restore_rejects_bad_sources_without_changes(configuration, tmp_path, bad):
    target, config = configuration
    source = target.with_name('menu.json.bak-manual')
    source.write_text(json.dumps(config))
    preview = current_revision(source)
    name = source.name
    if bad == 'corrupt':
        source.write_text('{broken')
    elif bad == 'missing':
        source.unlink()
    elif bad == 'symlink':
        source.unlink()
        source.symlink_to(target)
    elif bad == 'outside':
        name = '../' + name
    elif bad == 'changed':
        source.write_text('{"menu": []}')
    elif bad == 'fifo':
        source.unlink()
        os.mkfifo(source)
    before = target.read_bytes()
    with pytest.raises((OSError, ValueError)):
        restore_backup(target, name, current_revision(target),
                       expected_source=preview if bad == 'changed' else None)
    assert target.read_bytes() == before
    assert not list(target.parent.glob('menu.json.pre-restore-*'))


def test_symlinked_parent_and_lock_refused(configuration, tmp_path):
    target, config = configuration
    linked = tmp_path / 'linked'
    linked.symlink_to(target.parent, target_is_directory=True)
    before = target.read_bytes()
    for operation in (lambda: save_config(config, linked / target.name),
                      lambda: list_backups(linked / target.name)):
        with pytest.raises(OSError):
            operation()
    lock = target.with_name('.menu.lock')
    lock.unlink()
    lock.symlink_to(target)
    with pytest.raises(OSError):
        save_config(config, target)
    assert target.read_bytes() == before


def test_recovery_from_invalid_active_file_and_missing_directory(configuration, tmp_path):
    target, config = configuration
    source = target.with_name('menu.json.bak-good')
    source.write_bytes(target.read_bytes())
    target.write_bytes(b'invalid active JSON')
    restore_backup(target, source.name, current_revision(target))
    assert decode_configuration(target.read_bytes()) == config
    assert list(target.parent.glob('menu.json.pre-restore-*'))[0].read_bytes() == b'invalid active JSON'
    missing = tmp_path / 'missing/menu.json'
    assert list_backups(missing) == []
    assert current_revision(missing).content is None


def test_validation_identifies_nested_entry(configuration):
    _, config = configuration
    config['menu'][0]['items'][0]['command'] = 'unsafe shell string'
    with pytest.raises(MenuValidationError, match='1 / 1.*Literal arguments.*array of nonempty strings') as error:
        validate_configuration(config)
    assert error.value.path == (0, 0)


def test_two_editors_cannot_save_the_same_revision(configuration):
    target, config = configuration
    revision = current_revision(target)
    first = {**config, 'menu': []}
    save_config(first, target, expected_revision=revision)
    with pytest.raises(ConfigurationConflict):
        save_config(config, target, expected_revision=revision)
    assert decode_configuration(target.read_bytes()) == first


def test_restore_rejects_changed_active_file_and_unreadable_source(configuration, monkeypatch):
    target, config = configuration
    source = target.with_name('menu.json.bak-manual')
    source.write_bytes(target.read_bytes())
    revision = current_revision(target)
    target.write_text('{"menu": []}')
    with pytest.raises(ConfigurationConflict):
        restore_backup(target, source.name, revision)
    before = target.read_bytes()
    def denied(*args):
        raise PermissionError('backup cannot be read')
    monkeypatch.setattr('openpowermenu.recovery.read_at', denied)
    with pytest.raises(PermissionError):
        restore_backup(target, source.name, revision)
    assert target.read_bytes() == before and source.exists()
    assert not list(target.parent.glob('menu.json.pre-restore-*'))


def test_oversized_or_excessively_nested_json_is_rejected_safely(configuration):
    from openpowermenu.recovery import MAX_CONFIG_BYTES
    target, _ = configuration
    source = target.with_name('menu.json.bak-invalid')
    for payload in (b' ' * (MAX_CONFIG_BYTES + 1), b'[' * 2000 + b']' * 2000):
        source.write_bytes(payload)
        rows = list_backups(target)
        assert rows[0].config is None and rows[0].error
