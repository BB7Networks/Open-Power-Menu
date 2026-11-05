"""Additional review coverage for PR #2, including failed and colliding saves."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from openpowermenu.core import DEFAULT_CONFIG, load_config, save_config


def test_lowering_retention_preserves_manual_files_and_symlinks(tmp_path):
    path = tmp_path / 'menu.json'
    cfg = deepcopy(DEFAULT_CONFIG)
    for index in range(8):
        cfg['sequence'] = index
        save_config(cfg, path)
    manual = tmp_path / 'menu.json.bak-keep-me'
    manual.write_text('manual')
    external = tmp_path / 'external'
    external.write_text('external')
    link = tmp_path / 'menu.json.bak-20200101T000000000000Z'
    link.symlink_to(external)
    directory = tmp_path / 'menu.json.bak-20200102T000000000000Z'
    directory.mkdir()
    cfg['backup_retention'] = 2
    save_config(cfg, path)
    automatic = [p for p in tmp_path.glob('menu.json.bak-*') if p.is_file() and not p.is_symlink() and p != manual]
    assert len(automatic) == 2
    assert manual.read_text() == 'manual'
    assert link.is_symlink() and external.read_text() == 'external'
    assert directory.is_dir()


@pytest.mark.parametrize('symlink', [False, True])
def test_backup_collision_never_overwrites_existing_file(tmp_path, symlink):
    cfg = deepcopy(DEFAULT_CONFIG)
    path = tmp_path / 'menu.json'
    save_config(cfg, path)
    before = path.read_bytes()
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    backup = tmp_path / ('menu.json.bak-' + stamp.strftime('%Y%m%dT%H%M%S%fZ'))
    external = tmp_path / 'external'
    external.write_text('precious')
    if symlink:
        backup.symlink_to(external)
    else:
        backup.write_text('precious')
    cfg['menu'] = []
    with patch('datetime.datetime') as clock:
        clock.now.return_value = stamp
        with pytest.raises(FileExistsError):
            save_config(cfg, path)
    assert backup.read_text() == external.read_text() == 'precious'
    assert path.read_bytes() == before
    assert not list(tmp_path.glob('.menu-*.tmp'))


def test_pruning_failure_keeps_successful_save(tmp_path):
    path = tmp_path / 'menu.json'
    cfg = deepcopy(DEFAULT_CONFIG)
    save_config(cfg, path)
    cfg['menu'] = []
    with patch('openpowermenu.core.prune_automatic_backups', side_effect=PermissionError('read only')):
        assert save_config(cfg, path) == path
    assert load_config(path)['menu'] == []
    assert list(tmp_path.glob('menu.json.bak-*'))


def test_backup_write_failure_does_not_replace_or_leave_partial_backup(tmp_path):
    path = tmp_path / 'menu.json'
    cfg = deepcopy(DEFAULT_CONFIG)
    save_config(cfg, path)
    before = path.read_bytes()
    with patch('openpowermenu.core.shutil.copyfileobj', side_effect=OSError('disk full')):
        with pytest.raises(OSError, match='disk full'):
            save_config(cfg, path)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob('menu.json.bak-*'))
    assert not list(tmp_path.glob('.menu-*.tmp'))
