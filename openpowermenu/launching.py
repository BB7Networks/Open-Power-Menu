"""Detached argv execution shared by the backend and standalone menu.

Sessions isolate terminal signals, not process ancestry or systemd cgroups.
The backend calls reap_children while children run; standalone menus exit.
"""
from __future__ import annotations

import subprocess

_children: set[subprocess.Popen] = set()


def reap_children() -> bool:
    """Reap finished children, returning whether any still need monitoring."""
    for child in tuple(_children):
        if child.poll() is not None:
            _children.discard(child)
    return bool(_children)


def launch_detached(argv: list[str] | tuple[str, ...]) -> subprocess.Popen:
    """Launch without a shell, inherited pipes, or terminal/session coupling.

    Commands needing terminal output should launch a terminal explicitly. GUI
    applications keep their inherited desktop environment and normal permissions.
    """
    reap_children()
    child = subprocess.Popen(list(argv), close_fds=True, start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    _children.add(child)
    return child
