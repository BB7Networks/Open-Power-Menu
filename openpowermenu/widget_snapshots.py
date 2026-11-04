"""Widget history and read-only status, independent of configuration backups.

This module is also a standalone script so extracted installers need no imports
from an already installed backend. All paths are user-local XDG data paths.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import time
from uuid import uuid4


GENERATED = re.compile(r'org\.openpowermenu\.start-\d{8}-\d{6}-\d{9}')
DEFAULT_RETENTION = 5


@contextmanager
def directory(path, *, create=False):
    """Hold a directory without traversing symlink components."""
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in Path(path).absolute().parts[1:]:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def recovery_path(data_home):
    return Path(data_home) / 'open-power-menu-recovery/widget-backups'


def generated_names(root):
    names = []
    for name in os.listdir(root):
        if not GENERATED.fullmatch(name):
            continue
        try:
            if stat.S_ISDIR(os.stat(name, dir_fd=root, follow_symlinks=False).st_mode):
                names.append(name)
        except FileNotFoundError:
            continue  # An upgrade or user cleanup may have removed this entry.
    return names


def snapshot_count(data_home):
    try:
        with directory(recovery_path(data_home)) as root:
            return len(generated_names(root))
    except FileNotFoundError:
        return 0


def retention(value):
    if not re.fullmatch(r'[0-9]+', str(value)) or not 1 <= int(value) <= 1000:
        raise ValueError('OPM_WIDGET_BACKUP_RETENTION must be an integer from 1 to 1000 (default 5)')
    return int(value)


def migrate(data_home):
    """Move every legacy entry without reading through links or overwriting names.

    Manual files and symlinks are preserved as entries, never followed or pruned.
    Failure aborts the installer/uninstaller before disposable files are removed.
    """
    old = Path(data_home) / 'open-power-menu/widget-backups'
    if not os.path.lexists(old):
        return
    with directory(old) as source, directory(recovery_path(data_home), create=True) as dest:
        for name in os.listdir(source):
            new_name = name
            try:
                os.stat(new_name, dir_fd=dest, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                new_name = f'legacy-{uuid4().hex}-{name}'
            os.rename(name, new_name, src_dir_fd=source, dst_dir_fd=dest)


def snapshot(data_home):
    """Finish copying the old widget before the installer may replace it."""
    widget = Path(data_home) / 'plasma/plasmoids/org.openpowermenu.start'
    if not os.path.lexists(widget):
        return None
    destination = recovery_path(data_home)
    with directory(widget) as source, directory(destination, create=True) as dest:
        # /proc keeps the copy anchored to the verified directories on Linux.
        # copytree(symlinks=True) copies links as links, never their destinations.
        base = Path(f'/proc/self/fd/{dest}')
        temporary = Path(tempfile.mkdtemp(prefix='.snapshot-', dir=base))
        try:
            shutil.copytree(f'/proc/self/fd/{source}', temporary, symlinks=True, dirs_exist_ok=True)
            now = time.time_ns()
            stamp = datetime.fromtimestamp(now // 10**9, timezone.utc).strftime('%Y%m%d-%H%M%S-')
            name = f'org.openpowermenu.start-{stamp}{now % 10**9:09d}'
            # Reserve the final name exclusively. rename replaces only our empty
            # directory; a failed copy never becomes a recognized snapshot.
            os.mkdir(name, 0o700, dir_fd=dest)
            try:
                os.rename(temporary.name, name, src_dir_fd=dest, dst_dir_fd=dest)
            except BaseException:
                os.rmdir(name, dir_fd=dest)
                raise
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    return destination / name


def prune(data_home, keep):
    keep = retention(keep)
    path = recovery_path(data_home)
    if not os.path.lexists(path):
        return
    with directory(path) as root:
        names = generated_names(root)
        for name in sorted(names, reverse=True)[keep:]:
            # Python's fd-based rmtree refuses a symlink substituted at the root
            # and unlinks nested links without traversing their destinations.
            shutil.rmtree(name, dir_fd=root)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[0] not in ('prepare', 'prune', 'migrate'):
        raise ValueError('Usage: widget_snapshots.py prepare|prune|migrate DATA_HOME')
    operation, data_home = args
    if operation == 'migrate':
        migrate(data_home)
    else:
        keep = retention(os.environ.get('OPM_WIDGET_BACKUP_RETENTION', DEFAULT_RETENTION))
        if operation == 'prepare':
            migrate(data_home)
            saved = snapshot(data_home)
            if saved:
                print(f'Previous widget backed up: {saved}')
        else:
            prune(data_home, keep)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, shutil.Error) as exc:
        print(f'Widget recovery failed: {exc}', file=sys.stderr)
        sys.exit(1)
