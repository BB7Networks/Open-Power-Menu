"""Configuration recovery without Qt, command execution, or arbitrary file access."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import stat

MAX_CONFIG_BYTES = 4 * 1024 * 1024


class ConfigurationConflict(ValueError):
    pass


@dataclass(frozen=True)
class Revision:
    content: bytes | None
    identity: tuple[int, int] | None = None


@contextmanager
def configuration_directory(target: Path, *, create=False):
    """Open each path component without following symlinks; use relative I/O."""
    directory = target.absolute().parent
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in directory.parts[1:]:
            if create:
                try:
                    os.mkdir(component, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def read_at(directory: int, name: str) -> Revision:
    if not name or Path(name).name != name or name in ('.', '..'):
        raise ValueError('Choose a file inside the Open Power Menu configuration directory')
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    except FileNotFoundError:
        return Revision(None)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Configuration and backup files must be regular files')
        content = stream.read(MAX_CONFIG_BYTES + 1)
        if len(content) > MAX_CONFIG_BYTES:
            raise ValueError('Configuration is larger than the 4 MiB safety limit')
        return Revision(content, (info.st_dev, info.st_ino))


def current_revision(target: Path) -> Revision:
    try:
        with configuration_directory(target) as directory:
            return read_at(directory, target.name)
    except FileNotFoundError:
        return Revision(None)


@contextmanager
def configuration_lock(target: Path):
    with configuration_directory(target, create=True) as directory:
        fd = os.open('.menu.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError('Configuration lock must be a regular file')
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield directory
        finally:
            os.close(fd)


def decode_configuration(content: bytes | None) -> dict:
    from .core import DEFAULT_CONFIG, validate_configuration
    if content is None:
        return deepcopy(DEFAULT_CONFIG)
    try:
        value = json.loads(content)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError(f'Invalid configuration JSON: {exc}') from exc
    if not isinstance(value, dict) or not isinstance(value.get('menu'), list):
        raise ValueError("Configuration must contain a 'menu' array")
    config = deepcopy(DEFAULT_CONFIG)
    config.update(value)
    validate_configuration(config)
    return config


def is_backup_name(target: Path, name: str) -> bool:
    return Path(name).name == name and any(name.startswith(target.name + suffix) for suffix in
                                        ('.bak-', '.pre-restore-', '.pre-overwrite-'))


@dataclass
class Backup:
    name: str
    modified: float
    size: int
    config: dict | None
    error: str = ''

    @property
    def local_time(self):
        return datetime.fromtimestamp(self.modified).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')


def list_backups(target: Path) -> list[Backup]:
    result = []
    try:
        with configuration_directory(target) as directory:
            for name in os.listdir(directory):
                if not is_backup_name(target, name):
                    continue
                try:
                    info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode):
                        continue
                    revision = read_at(directory, name)
                    if revision.content is None:
                        continue
                    try:
                        config, error = decode_configuration(revision.content), ''
                    except ValueError as exc:
                        config, error = None, str(exc)
                    result.append(Backup(name, info.st_mtime, info.st_size, config, error))
                except (OSError, ValueError) as exc:
                    result.append(Backup(name, 0, 0, None, str(exc)))
    except FileNotFoundError:
        pass
    return sorted(result, key=lambda row: (row.modified, row.name), reverse=True)


def restore_backup(target: Path, name: str, expected: Revision, *, expected_source: Revision | None = None) -> Path:
    from .core import save_config
    if not is_backup_name(target, name):
        raise ValueError('Select an Open Power Menu configuration backup')
    with configuration_directory(target) as directory:
        revision = read_at(directory, name)
    if revision.content is None:
        raise FileNotFoundError('The selected backup no longer exists')
    if expected_source is not None and revision != expected_source:
        raise ConfigurationConflict('The selected backup changed. Refresh and preview it again before restoring.')
    config = decode_configuration(revision.content)
    return save_config(config, target, expected_revision=expected,
                       recovery_reason='restore', protected_backups=frozenset({name}))


def configuration_summary(config: dict, active: dict | None = None) -> str:
    """Show definitions only: never resolve or execute a command during preview."""
    from .core import COMMANDS
    count = 0
    lines = []
    def walk(items, depth=0):
        nonlocal count
        for item in items:
            count += 1
            label = item.get('submenu') or item.get('label') or COMMANDS.get(item.get('action'), {}).get('title') or ('Separator' if item.get('separator') else 'Custom command')
            lines.append('  ' * depth + str(label))
            if 'submenu' in item:
                walk(item['items'], depth + 1)
    walk(config['menu'])
    general = {key: value for key, value in config.items() if key != 'menu'}
    changes = ''
    if active is not None:
        changed = [key for key in sorted(set(active) | set(config)) if active.get(key) != config.get(key)]
        changes = '\nChanged sections/settings: ' + (', '.join(changed) or 'None')
    return f'{count} entries (including submenus and separators)\n' + '\n'.join(lines) + '\n\nGeneral settings:\n' + json.dumps(general, ensure_ascii=False, indent=2) + changes
