"""Installed-application discovery and safe launcher command generation.

No app is launched during discovery. KDE desktop files are handed to kioclient6,
which honors Desktop Entry semantics (DBus activation, Terminal, field codes,
working directory) rather than assuming the Exec line is the whole contract.
The stdlib fallback uses Exec only when desktop-file launchers are unavailable.
"""
from __future__ import annotations

import configparser
from dataclasses import dataclass
import locale
import os
from pathlib import Path
import re
import shlex
import shutil


@dataclass(frozen=True)
class DesktopApplication:
    name: str
    icon: str
    desktop_file: Path
    exec_line: str
    comment: str = ""
    generic_name: str = ""
    terminal: bool = False


def _flag(value: str) -> bool:
    return value.strip().lower() == "true"


def _local_name(section, key: str) -> str:
    language = locale.getlocale()[0] or os.environ.get("LANG", "").split(".", 1)[0]
    choices = []
    if language:
        choices = [f"{key}[{language}]", f"{key}[{language.split('_')[0]}]"]
    for candidate in (*choices, key):
        if candidate in section:
            return section[candidate].strip()
    return ""


def read_desktop_application(file: Path) -> DesktopApplication | None:
    """Return a menu-visible Application desktop entry or None."""
    parser = configparser.RawConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        with file.open("r", encoding="utf-8") as stream:
            parser.read_file(stream)
        if not parser.has_section("Desktop Entry"):
            return None
        meta = parser["Desktop Entry"]
        if meta.get("Type") != "Application":
            return None
        if _flag(meta.get("Hidden", "false")) or _flag(meta.get("NoDisplay", "false")):
            return None
        current = set(filter(None, os.environ.get("XDG_CURRENT_DESKTOP", "KDE").upper().replace(";", ":").split(":")))
        only = set(filter(None, meta.get("OnlyShowIn", "").upper().split(";")))
        blocked = set(filter(None, meta.get("NotShowIn", "").upper().split(";")))
        if only and not (current & only):
            return None
        if current & blocked:
            return None
        try_exec = meta.get("TryExec", "").strip()
        if try_exec and not (Path(try_exec).is_file() and os.access(try_exec, os.X_OK) if "/" in try_exec else shutil.which(try_exec)):
            return None
        exec_line = meta.get("Exec", "").strip()
        if not exec_line and not _flag(meta.get("DBusActivatable", "false")):
            return None
        name = _local_name(meta, "Name")
        if not name:
            return None
        return DesktopApplication(
            name=name,
            icon=meta.get("Icon", "").strip(),
            desktop_file=file.resolve(),
            exec_line=exec_line,
            comment=_local_name(meta, "Comment"),
            generic_name=_local_name(meta, "GenericName"),
            terminal=_flag(meta.get("Terminal", "false")),
        )
    except (OSError, UnicodeError, configparser.Error, ValueError):
        return None


def installed_applications() -> list[DesktopApplication]:
    """Search XDG application directories with user and directory precedence."""
    home = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local/share"))
    system = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    roots = [home, *[Path(part) for part in system.split(":") if part]]
    visited_ids: set[str] = set()
    found: list[DesktopApplication] = []
    for base in roots:
        applications = base / "applications"
        if not applications.is_dir():
            continue
        try:
            entries = sorted(applications.rglob("*.desktop"))
        except OSError:
            continue
        for file in entries:
            desktop_id = str(file.relative_to(applications)).replace("/", "-")
            if desktop_id in visited_ids:
                continue
            visited_ids.add(desktop_id)  # Hidden user override masks system entry.
            application = read_desktop_application(file)
            if application:
                found.append(application)
    return sorted(found, key=lambda app: (app.name.casefold(), str(app.desktop_file)))


def desktop_exec_argv(exec_line: str, name: str, icon: str, desktop_file: Path) -> list[str]:
    """Conservative Desktop Entry Exec fallback when no desktop launcher exists.

    No file or URI is supplied by this menu: corresponding field codes vanish.
    Unsupported field codes fail closed rather than silently altering a command.
    """
    if not exec_line:
        raise ValueError("This application uses desktop activation only; a KDE desktop launcher is required")
    try:
        parts = shlex.split(exec_line, posix=True)
    except ValueError as exc:
        raise ValueError("Invalid desktop Exec quoting") from exc
    argv: list[str] = []
    for part in parts:
        if part in ("%f", "%F", "%u", "%U", "%d", "%D", "%n", "%N", "%v", "%m"):
            continue
        if part == "%i":
            if icon:
                argv.extend(("--icon", icon))
        elif part == "%c":
            argv.append(name)
        elif part == "%k":
            argv.append(str(desktop_file))
        else:
            # Protect %% while rejecting unknown codes and unsupported embedded
            # field expansions. Spec permits a literal percent as %%.
            literal = part.replace("%%", "\x00")
            if "%" in literal:
                raise ValueError("Unsupported field code in desktop application command")
            argv.append(literal.replace("\x00", "%"))
    if not argv or argv[0].startswith("-"):
        raise ValueError("The selected desktop file has no executable command")
    return argv


def application_command(app: DesktopApplication) -> list[str]:
    """Prefer KDE's desktop-file execution, then GIO, then conservative Exec."""
    file = str(app.desktop_file)
    if shutil.which("kioclient6"):
        return ["kioclient6", "exec", file]
    if shutil.which("gio"):
        return ["gio", "launch", file]
    if app.terminal:
        raise ValueError("This application needs terminal handling. Install kioclient6 to use the picker")
    return desktop_exec_argv(app.exec_line, app.name, app.icon, app.desktop_file)


def application_menu_item(app: DesktopApplication) -> dict:
    """Return a plain menu.json-compatible item; no new schema required."""
    return {
        "label": app.name,
        "icon": app.icon or "application-x-executable",
        "command": application_command(app),
        "desktop_file": str(app.desktop_file),  # editor metadata; core ignores it
    }
