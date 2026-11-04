"""Explicit history deletion is confined, conflict-checked and independent of restore."""
import os
from pathlib import Path
import stat
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from openpowermenu.recovery import (MAX_CONFIG_BYTES, ConfigurationConflict,
                                   backup_deletion_revision, delete_backup, list_backups)
from openpowermenu.widget_snapshots import recovery_path, snapshot_count


@pytest.fixture
def files(tmp_path):
    target = tmp_path / 'config/menu.json'
    target.parent.mkdir(mode=0o700)
    target.write_bytes(b'{"menu":[]}')
    backup = target.with_name('menu.json.bak-manual')
    backup.write_bytes(target.read_bytes())
    unrelated = target.with_name('keep-me.txt')
    unrelated.write_bytes(b'keep me')
    return target, backup, unrelated


@pytest.mark.parametrize('content', [b'{"menu":[]}', b'{broken', b'x' * (MAX_CONFIG_BYTES + 1)])
def test_delete_valid_corrupt_and_oversized_backup_only_after_selection(files, content):
    target, backup, unrelated = files
    backup.write_bytes(content)
    revision = backup_deletion_revision(target, backup.name)
    assert revision.size == len(content) and revision.local_time
    assert list_backups(target)[0].size == len(content)
    active = target.read_bytes()
    delete_backup(target, backup.name, revision)
    assert not backup.exists() and target.read_bytes() == active
    assert unrelated.read_bytes() == b'keep me' and not list_backups(target)


@pytest.mark.parametrize('change', ['content', 'replacement', 'missing', 'symlink', 'hardlink', 'directory', 'fifo'])
def test_changed_or_unsafe_backups_are_never_deleted(files, change):
    target, backup, unrelated = files
    revision = backup_deletion_revision(target, backup.name)
    if change == 'content':
        backup.write_bytes(b'{"menu":00}')
        os.utime(backup, ns=(revision.modified_ns, revision.modified_ns))
    elif change == 'replacement':
        replacement = backup.with_name('replacement')
        replacement.write_bytes(backup.read_bytes())
        os.utime(replacement, ns=(revision.modified_ns, revision.modified_ns))
        replacement.replace(backup)
    else:
        backup.unlink()
        if change == 'symlink': backup.symlink_to(unrelated)
        elif change == 'hardlink': os.link(target, backup)
        elif change == 'directory': backup.mkdir()
        elif change == 'fifo': os.mkfifo(backup)
    with pytest.raises((ValueError, OSError)):
        delete_backup(target, backup.name, revision)
    assert target.read_bytes() == b'{"menu":[]}' and unrelated.read_bytes() == b'keep me'
    if change != 'missing': assert os.path.lexists(backup)


@pytest.mark.parametrize('name', ['menu.json', 'keep-me.txt', '../menu.json.bak-manual',
                                '/tmp/menu.json.bak-manual', 'menu.json.bak-x/../../menu.json', '', None])
def test_deletion_refuses_active_unrelated_and_arbitrary_paths(files, name):
    target, backup, unrelated = files
    revision = backup_deletion_revision(target, backup.name)
    with pytest.raises(ValueError): backup_deletion_revision(target, name)
    with pytest.raises(ValueError): delete_backup(target, name, revision)
    assert target.exists() and backup.exists() and unrelated.exists()


@pytest.mark.parametrize('suffix', ['pre-restore', 'pre-overwrite'])
def test_protected_copies_need_explicit_protected_confirmation(files, suffix):
    target, backup, _ = files
    protected = backup.with_name('menu.json.' + suffix + '-test')
    backup.rename(protected)
    revision = backup_deletion_revision(target, protected.name)
    with pytest.raises(ValueError, match='protected'):
        delete_backup(target, protected.name, revision)
    delete_backup(target, protected.name, revision, confirm_protected=True)
    assert not protected.exists() and target.exists()


def test_refuse_changed_directory_symlinked_parent_and_lock(files, tmp_path):
    target, backup, _ = files
    revision = backup_deletion_revision(target, backup.name)
    link = tmp_path / 'linked'
    link.symlink_to(target.parent, target_is_directory=True)
    with pytest.raises(OSError): delete_backup(link / target.name, backup.name, revision)
    target.with_name('.menu.lock').symlink_to(target)
    with pytest.raises(OSError): delete_backup(target, backup.name, revision)
    target.with_name('.menu.lock').unlink()
    moved = tmp_path / 'old'
    target.parent.rename(moved)
    target.parent.mkdir(mode=0o700)
    os.link(moved / backup.name, backup)
    (moved / backup.name).unlink()  # Same file, different confined directory.
    with pytest.raises(ConfigurationConflict): delete_backup(target, backup.name, revision)
    assert backup.exists() and (moved / target.name).exists()


def test_permission_failure_and_foreign_ownership_leave_files_intact(files):
    target, backup, _ = files
    revision = backup_deletion_revision(target, backup.name)
    with patch('openpowermenu.recovery.os.unlink', side_effect=PermissionError('denied')):
        with pytest.raises(PermissionError): delete_backup(target, backup.name, revision)
    original = os.fstat
    def foreign(fd):
        info = original(fd)
        if stat.S_ISREG(info.st_mode) and info.st_ino == backup.stat().st_ino:
            return SimpleNamespace(st_mode=info.st_mode, st_uid=os.getuid() + 1, st_nlink=1)
        return info
    with patch('openpowermenu.recovery.os.fstat', side_effect=foreign):
        with pytest.raises(ValueError, match='your own'):
            delete_backup(target, backup.name, revision)
    target.parent.chmod(0o777)
    try:
        with pytest.raises(PermissionError, match='directory'):
            delete_backup(target, backup.name, revision)
    finally:
        target.parent.chmod(0o700)
    assert backup.exists() and target.exists()


def test_snapshot_status_counts_only_generated_directories_and_refuses_links(tmp_path):
    assert snapshot_count(tmp_path) == 0
    root = recovery_path(tmp_path)
    root.mkdir(parents=True)
    generated = root / 'org.openpowermenu.start-20260101-010101-000000000'
    generated.mkdir()
    (root / 'manual-keep').mkdir()
    (root / 'org.openpowermenu.start-20260101-010101-000000001').symlink_to(generated, target_is_directory=True)
    (root / 'org.openpowermenu.start-20260101-010101-000000002').write_text('not a directory')
    assert snapshot_count(tmp_path) == 1
    generated.rmdir()
    assert snapshot_count(tmp_path) == 0
    moved = root.with_name('real-backups')
    root.rename(moved)
    root.symlink_to(moved, target_is_directory=True)
    with pytest.raises(OSError): snapshot_count(tmp_path)
