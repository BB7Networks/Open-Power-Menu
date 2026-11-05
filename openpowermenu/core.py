"""Stdlib configuration, availability and command-resolution logic.

No Qt imports or live panel access; desktop capability probes are read-only.
UI adapters consume this model and ask the launcher to execute resolved argv.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import logging
from functools import lru_cache
import os
from pathlib import Path
import shutil
import re
import subprocess
import time
from urllib.parse import urlsplit, unquote
from typing import Any

CONFIG_FILENAME = "menu.json"
MAX_BACKUP_RETENTION = 1000
_logger = logging.getLogger(__name__)


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "open-power-menu"


def expand_part(s: str) -> str:
    return os.path.expandvars(os.path.expanduser(s.replace("{home}", str(Path.home()))))


@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]
    title: str
    icon: str
    explanation: str = ""


# List of candidate commands in preference order. No shell commands, sudo,
# hidden privilege escalation or third-party dependencies beyond existing apps.
# Plasma session functions always ask KDE to display its native prompt.
COMMANDS: dict[str, dict[str, Any]] = {
    "applications": {
        "title": "Installed Applications", "icon": "applications-other",
        "commands": [["pamac-manager"], ["plasma-discover"], ["gnome-software"], ["octopi"]],
    },
    "power": {
        "title": "Power Options", "icon": "battery",
        "commands": [["kcmshell6", "kcm_powerdevilprofilesconfig"], ["systemsettings"], ["gnome-control-center", "power"]],
    },
    "logs": {
        "title": "System Logs", "icon": "view-list-details",
        "commands": [["ksystemlog"],
                     {"argv": ["konsole", "--hold", "-e", "journalctl", "-b", "-p", "warning", "-n", "1000", "--follow", "--no-pager"],
                      "requires": ["journalctl"]},
                     {"argv": ["xterm", "-hold", "-e", "journalctl", "-b", "-p", "warning", "-n", "1000", "--follow", "--no-pager"],
                      "requires": ["journalctl"]}],
    },
    "system": {
        "title": "System Information", "icon": "computer",
        "commands": [["kinfocenter"], ["hardinfo2"], ["gnome-control-center", "info-overview"]],
    },
    "hardware": {
        "title": "Hardware Information", "icon": "preferences-system",
        "commands": [["konsole", "--hold", "-e", "inxi", "-Fzxx"], ["hardinfo2"], ["kinfocenter"]],
    },
    "network": {
        "title": "Network Connections", "icon": "network-wired",
        "commands": [["nm-connection-editor"], ["kcmshell6", "kcm_networkmanagement"], ["systemsettings"]],
    },
    "disks": {
        "title": "Disk Management", "icon": "drive-harddisk",
        "commands": [["partitionmanager"], ["gnome-disks"], ["gparted"]],
    },
    "printers": {
        "title": "Printers", "icon": "preferences-devices-printer",
        "commands": [{"argv": ["kcmshell6", "kcm_printer_manager"], "kcm": "kcm_printer_manager"},
                     ["system-config-printer"]],
    },
    "vms": {
        "title": "Virtual Machine Manager", "icon": "computer",
        "commands": [["virt-manager"], ["virtualbox"]],
    },
    "terminal": {
        "title": "Terminal", "icon": "utilities-terminal",
        "commands": [["konsole"], ["kitty"], ["alacritty"], ["gnome-terminal"], ["xfce4-terminal"], ["xterm"]],
    },
    "monitor": {
        "title": "Task Manager / System Monitor", "icon": "utilities-system-monitor",
        "commands": [["plasma-systemmonitor"], ["gnome-system-monitor"], ["ksysguard"], ["xfce4-taskmanager"]],
    },
    "files": {
        "title": "File Manager", "icon": "system-file-manager",
        "commands": [["dolphin"], ["nautilus"], ["thunar"], ["nemo"], ["pcmanfm-qt"]],
    },
    "settings": {
        "title": "Settings", "icon": "preferences-system",
        "commands": [["systemsettings"], ["gnome-control-center"], ["xfce4-settings-manager"]],
    },
    "run": {
        "title": "Search / Run", "icon": "system-search",
        "commands": [{"argv": ["qdbus6", "org.kde.krunner", "/App", "org.kde.krunner.App.display"], "desktops": ["KDE", "PLASMA"]}, ["rofi", "-show", "run"], ["krunner"]],
    },
    "remote": {
        "title": "Remote Desktop", "icon": "preferences-desktop-remote-desktop",
        "commands": [["remmina"], ["krdc"]],
    },
    "network_locations": {
        "title": "Network Locations", "icon": "network-server",
        "commands": [["dolphin", "{home}/Network Locations"]],
        "path_required": "{home}/Network Locations",
    },
    "lock": {
        "title": "Lock", "icon": "system-lock-screen",
        "commands": [["loginctl", "lock-session"]],
    },
    "logout": {
        "title": "Sign out...", "icon": "system-log-out",
        "commands": [["qdbus6", "org.kde.LogoutPrompt", "/LogoutPrompt", "promptLogout"]],
        "desktops": ["KDE", "PLASMA"],
    },
    "reboot": {
        "title": "Restart...", "icon": "system-reboot",
        "commands": [["qdbus6", "org.kde.LogoutPrompt", "/LogoutPrompt", "promptReboot"]],
        "desktops": ["KDE", "PLASMA"],
    },
    "show_desktop": {
        "title": "Desktop", "icon": "user-desktop",
        "desktops": ["KDE", "PLASMA"],
        "commands": [{"argv": ["qdbus6", "org.kde.kglobalaccel", "/component/kwin",
                               "org.kde.kglobalaccel.Component.invokeShortcut", "Show Desktop"],
                      "kwin_shortcut": "Show Desktop"}],
    },
    "shutdown": {
        "title": "Shut down...", "icon": "system-shutdown",
        "commands": [["qdbus6", "org.kde.LogoutPrompt", "/LogoutPrompt", "promptShutDown"]],
        "desktops": ["KDE", "PLASMA"],
    },
}

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "appearance": "native",
    "anchor": "cursor",
    "show_unavailable": False,
    "show_menu_icons": True,
    "auto_close_on_pointer_leave": False,
    "backup_retention": 10,  # Number of previous automatic menu.json versions to retain.
    # Opt-in, presentation-only Plasma panel integration; never writes panel config.
    "hide_original_launcher": False,
    # 0 = auto-detect a unique launcher on this panel, >0 = exact Plasma applet ID.
    "launcher_applet_id": 0,
    # Start button presentation: inherit the selected live Plasma launcher or
    # use an explicit local icon/theme name. Original launcher stays untouched.
    "button_icon_mode": "launcher",
    "button_icon": "",
    "menu": [
        {"action": "applications"},
        {"action": "power"},
        {"action": "logs"},
        {"action": "system"},
        {"action": "hardware"},
        {"action": "network"},
        {"action": "disks"},
        {"action": "printers"},
        {"action": "vms"},
        {"separator": True},
        {"action": "terminal"},
        {"action": "monitor"},
        {"action": "files"},
        {"action": "settings"},
        {"action": "run"},
        {"separator": True},
        {"submenu": "Remote & Work", "icon": "network-server", "items": [
            {"action": "remote"}
        ]},
        {"submenu": "Shut down or sign out", "icon": "system-shutdown", "items": [
            {"action": "lock"}, {"action": "logout"}, {"action": "reboot"}, {"action": "shutdown"}
        ]},
        {"action": "show_desktop"},
    ],
}


def config_path() -> Path:
    return config_home() / CONFIG_FILENAME


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Use the same bounded, no-follow reader and validation as editor recovery."""
    from .recovery import current_revision, decode_configuration

    return decode_configuration(current_revision(path or config_path()).content)


def which_executable(name: str) -> bool:
    if "/" in name:
        return any(p.is_file() and os.access(p, os.X_OK) for p in (Path(name), Path(expand_part(name))))
    return shutil.which(name) is not None


def desktop_is_available(allowed: list[str] | None) -> bool:
    if not allowed:
        return True
    current = set(os.environ.get("XDG_CURRENT_DESKTOP", "").upper().replace(";", ":").split(":"))
    return bool(current.intersection(value.upper() for value in allowed))


@lru_cache(maxsize=1)
def _kcm_modules(executable: str, interval: int) -> frozenset[str]:
    """Ask KDE rather than guessing distro-specific plugin paths.

    Cache for at most 30 seconds so menu/editor refreshes do not repeatedly
    start kcmshell6, while newly installed modules can be discovered.
    """
    try:
        reply = subprocess.run([executable, "--list"], capture_output=True,
                               text=True, errors="replace", timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return frozenset()
    if reply.returncode:
        return frozenset()
    return frozenset(line.split()[0] for line in reply.stdout.splitlines() if line.split())


def kcm_is_available(module: str) -> bool:
    executable = shutil.which("kcmshell6")
    return bool(executable and module in _kcm_modules(executable, int(time.monotonic() // 30)))


@lru_cache(maxsize=1)
def _kwin_shortcuts(executable: str, interval: int) -> frozenset[str]:
    """Read the actual registered action IDs; never toggle during discovery."""
    try:
        result = subprocess.run([executable, "org.kde.kglobalaccel", "/component/kwin",
                                 "org.kde.kglobalaccel.Component.shortcutNames"],
                                capture_output=True, text=True, errors="replace", timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        return frozenset()
    return frozenset(result.stdout.splitlines()) if result.returncode == 0 else frozenset()


def candidate_argv(candidate: list | dict, *, expand: bool = True) -> tuple[str, ...]:
    raw = candidate.get("argv") if isinstance(candidate, dict) else candidate
    if not isinstance(raw, list) or not raw or not all(isinstance(p, str) and p and "\x00" not in p for p in raw):
        raise ValueError("Invalid command: use a nonempty argv list, not a shell string")
    return tuple(expand_part(part) if expand else part for part in raw)


def candidate_is_available(candidate: list | dict, *, expand: bool = True) -> bool:
    """The resolver and editor use identical per-candidate requirements."""
    argv = candidate_argv(candidate, expand=expand)
    if not which_executable(argv[0]):
        return False
    if isinstance(candidate, dict):
        if not desktop_is_available(candidate.get("desktops")):
            return False
        requires = candidate.get("requires", [])
        if not isinstance(requires, list) or not all(isinstance(name, str) and name for name in requires):
            raise ValueError("requires must be an array of executable names")
        if any(not which_executable(name) for name in requires):
            return False
        shortcut = candidate.get("kwin_shortcut")
        if shortcut and shortcut not in _kwin_shortcuts(shutil.which(argv[0]) or argv[0], int(time.monotonic() // 30)):
            return False
        module = candidate.get("kcm")
        if module and not kcm_is_available(module):
            return False
    return True


def resolve_action(action_id: str, custom: dict[str, Any] | None = None) -> Command | None:
    if custom is None:
        if action_id not in COMMANDS:
            raise KeyError(f"Unknown action ID {action_id!r}")
        spec = COMMANDS[action_id]
    else:
        spec = custom
    if not desktop_is_available(spec.get("desktops")):
        return None
    required_path = spec.get("path_required")
    if required_path and not Path(expand_part(required_path)).exists():
        return None
    requires = spec.get("requires", [])
    if not isinstance(requires, list) or not all(isinstance(x, str) for x in requires):
        raise ValueError("requires must be an array of executable names")
    if any(not which_executable(name) for name in requires):
        return None
    cmds = spec.get("commands", [])
    if "command" in spec:
        cmds = [spec["command"]]
    for candidate in cmds:
        expand = spec.get("expand_arguments", True)
        if candidate_is_available(candidate, expand=expand):
            return Command(candidate_argv(candidate, expand=expand), str(spec.get("title") or action_id), str(spec.get("icon") or ""), str(spec.get("description") or ""))
    return None


def get_item_info(item: dict[str, Any]) -> tuple[str, str, Command | None]:
    """Return title, icon and safe candidate for a builtin/custom menu item."""
    if not isinstance(item, dict):
        raise ValueError("Each menu item must be an object")
    if "action" in item:
        action_id = item["action"]
        if action_id not in COMMANDS:
            raise ValueError(f"Unknown built-in action: {action_id}")
        spec = COMMANDS[action_id]
        cmd = resolve_action(action_id)
        return (str(item.get("label") or spec["title"]), str(item.get("icon") or spec["icon"]), cmd)
    if "command" in item or "commands" in item:
        title = item.get("label", "Custom command")
        spec = {
            "title": title,
            "icon": item.get("icon", "system-run"),
            "commands": [item["command"]] if "command" in item else item["commands"],
            "desktops": item.get("desktops"),
            "path_required": item.get("path_required"),
            "requires": item.get("requires", []),
            # Picker argv already follows desktop-entry substitutions. A name
            # or filename containing $, ~ or {home} must remain literal.
            "expand_arguments": not bool(item.get("desktop_file")),
        }
        cmd = resolve_action(str(title), spec)
        return str(title), str(item.get("icon") or "system-run"), cmd
    raise ValueError("Menu item requires an 'action', 'command', 'submenu', or 'separator' key")


def normalized_menu(items: list[dict[str, Any]], show_unavailable: bool = False) -> list[dict[str, Any]]:
    """Resolve items, remove empty submenus and adjacent/trailing separators."""
    output: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each menu item must be an object")
        if item.get("separator"):
            if output and output[-1]["kind"] != "separator":
                output.append({"kind": "separator"})
            continue
        if "submenu" in item:
            if not isinstance(item.get("items"), list):
                raise ValueError("Submenu requires an items array")
            children = normalized_menu(item["items"], show_unavailable)
            if children:
                output.append({"kind": "submenu", "title": str(item["submenu"]), "icon": str(item.get("icon", "")), "items": children})
            continue
        title, icon, command = get_item_info(item)
        if command is None and not show_unavailable:
            continue
        output.append({"kind": "command", "title": title, "icon": icon, "command": command,
                       "close_before_run": item.get("action") == "show_desktop"})
    while output and output[-1]["kind"] == "separator":
        output.pop()
    return output


def describe_menu(items: list[dict[str, Any]], indent: int = 0) -> list[str]:
    lines: list[str] = []
    for item in items:
        if item["kind"] == "separator":
            lines.append("  " * indent + "---")
        elif item["kind"] == "submenu":
            lines.append("  " * indent + item["title"] + " >")
            lines.extend(describe_menu(item["items"], indent + 1))
        else:
            cmd = item["command"]
            lines.append("  " * indent + item["title"] + ("  [available]" if cmd else "  [not installed]"))
    return lines


class MenuValidationError(ValueError):
    def __init__(self, path, label, message):
        self.path = path
        super().__init__(f"Menu entry {' / '.join(str(i + 1) for i in path)} ({label}): {message}")


def validate_menu_definition(items: list[dict[str, Any]], depth: int = 0, _path=()) -> None:
    """Validate without executing commands; include the affected entry path."""
    if depth > 8:
        raise MenuValidationError(_path, 'Submenu', 'Menus may be nested at most eight levels')
    if not isinstance(items, list) or len(items) > 200:
        raise MenuValidationError(_path, 'Menu', 'Each menu must contain at most 200 entries')
    for index, item in enumerate(items):
        try:
            if not isinstance(item, dict):
                raise ValueError("Menu entries must be objects")
            if item.get("separator") is True:
                continue
            if "submenu" in item:
                if not isinstance(item["submenu"], str) or not item["submenu"].strip():
                    raise ValueError("Every submenu needs a name")
                validate_menu_definition(item.get("items"), depth + 1, _path + (index,))
                continue
            if "action" in item:
                if not isinstance(item["action"], str) or item["action"] not in COMMANDS:
                    raise ValueError("Unknown built-in action: " + str(item["action"]))
                continue
            commands = [item["command"]] if "command" in item else item.get("commands")
            if not isinstance(commands, list) or not commands:
                raise ValueError("Custom menu items need an argument-array command")
            validate_requirements(item)
            for candidate in commands:
                argv = candidate.get("argv") if isinstance(candidate, dict) else candidate
                if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a and "\x00" not in a for a in argv):
                    raise ValueError("A custom command must be an array of nonempty strings (no shell command string)")
                if isinstance(candidate, dict):
                    validate_requirements(candidate)

        except MenuValidationError:
            raise
        except ValueError as exc:
            label = (item.get('submenu') or item.get('label') or item.get('action')) if isinstance(item, dict) else None
            raise MenuValidationError(_path + (index,), str(label or f'Entry {index + 1}'), str(exc)) from exc


def validate_requirements(spec: dict[str, Any]) -> None:
    for key in ("requires", "desktops"):
        value = spec.get(key)
        if value is not None and (not isinstance(value, list) or not all(isinstance(p, str) and p and "\x00" not in p for p in value)):
            raise ValueError(f"{key} must be an array of nonempty names")
    if "kcm" in spec and (not isinstance(spec["kcm"], str) or not spec["kcm"]):
        raise ValueError("kcm must be a module name")


def validate_button_icon(mode: str, icon: str) -> None:
    """Only theme icon names or local image files can be selected."""
    if mode not in ("launcher", "custom"):
        raise ValueError("button_icon_mode must be 'launcher' or 'custom'")
    if not isinstance(icon, str) or len(icon) > 512 or "\x00" in icon:
        raise ValueError("button_icon must be a string of at most 512 characters")
    if not icon:
        return  # Existing Plasma widget icon is the fallback.
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+\-]{0,127}", icon):
        return
    if icon.startswith("file://"):
        parts = urlsplit(icon)
        if parts.scheme == "file" and parts.netloc in ("", "localhost") and not parts.query and not parts.fragment:
            local_path = unquote(parts.path)
        else:
            raise ValueError("Only local file:// icon URLs are supported")
    elif icon.startswith("/"):
        local_path = icon
    else:
        raise ValueError("Use a theme icon name or absolute local image path")
    if not Path(local_path).is_absolute() or Path(local_path).suffix.lower() not in (
            ".png", ".svg", ".svgz", ".jpg", ".jpeg", ".webp", ".ico"):
        raise ValueError("Custom image must be a local PNG/SVG/JPEG/WebP/ICO file")


def validate_backup_retention(value: Any) -> None:
    if type(value) is not int or not 0 <= value <= MAX_BACKUP_RETENTION:
        raise ValueError(f"backup_retention must be an integer from 0 to {MAX_BACKUP_RETENTION}")


def prune_automatic_backups(target: Path, keep: int, protected: frozenset[str] = frozenset()) -> None:
    """Remove excess timestamped automatic backups; never delete manual files.

    Keep zero disables *future* backup creation but leaves existing history
    alone. Backups are pruned only after an atomic configuration save succeeds.
    """
    if keep == 0:
        return
    # Our automatic names: menu.json.bak-YYYYMMDDTHHMMSSffffffZ.
    # Filter symlinks and unrelated names so user-maintained backups survive.
    pattern = re.compile(re.escape(target.name) + r"\.bak-\d{8}T\d{12}Z")
    import stat
    from .recovery import configuration_directory
    with configuration_directory(target) as directory:
        backups = sorted((name for name in os.listdir(directory)
                          if pattern.fullmatch(name) and stat.S_ISREG(os.stat(
                              name, dir_fd=directory, follow_symlinks=False).st_mode)), reverse=True)
        for old in backups[keep:]:
            if old in protected:
                continue
            try:
                os.unlink(old, dir_fd=directory)
            except OSError as exc:
                _logger.warning("Could not remove old Open Power Menu backup %s: %s", old, exc)


def validate_configuration(config: dict[str, Any]) -> None:
    if not isinstance(config, dict) or not isinstance(config.get("menu"), list):
        raise ValueError("Configuration must contain a menu array")
    if type(config.get("auto_close_on_pointer_leave", False)) is not bool:
        raise ValueError("auto_close_on_pointer_leave must be true or false")
    if not isinstance(config.get("show_menu_icons", True), bool):
        raise ValueError("show_menu_icons must be a boolean")
    if config.get("appearance", "native") not in ("native", "aero"):
        raise ValueError("Invalid appearance")
    if config.get("anchor", "cursor") not in ("cursor", "bottom-left", "bottom-right"):
        raise ValueError("Invalid menu anchor")
    if type(config.get("hide_original_launcher", False)) is not bool:
        raise ValueError("hide_original_launcher must be true or false")
    launcher_id = config.get("launcher_applet_id", 0)
    if type(launcher_id) is not int or not 0 <= launcher_id <= 2147483647:
        raise ValueError("launcher_applet_id must be an integer from 0 to 2147483647")
    validate_button_icon(config.get("button_icon_mode", "launcher"),
                         config.get("button_icon", ""))
    validate_backup_retention(config.get("backup_retention", DEFAULT_CONFIG["backup_retention"]))
    validate_menu_definition(config["menu"])


_ANY_REVISION = object()


def save_config(config: dict[str, Any], path: Path | None = None, *,
                expected_revision=_ANY_REVISION, recovery_reason: str | None = None,
                protected_backups: frozenset[str] = frozenset()) -> Path:
    """Atomically save under a cooperative lock, optionally checking the loaded file.

    Explicit restore/overwrite recovery copies are independent of auto retention.
    No Plasma settings or launcher configurations are modified here.
    """
    from datetime import datetime, timezone
    from io import BytesIO
    from uuid import uuid4
    from .recovery import (ConfigurationConflict, MAX_CONFIG_BYTES,
                           configuration_lock, read_at)

    validate_configuration(config)
    if recovery_reason not in (None, 'restore', 'overwrite'):
        raise ValueError('Unknown recovery operation')
    retention = config.get("backup_retention", DEFAULT_CONFIG["backup_retention"])
    target = path or config_path()
    if target.is_symlink():
        raise ValueError("Refusing to replace a symlinked menu configuration")
    payload = (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode('utf-8')
    if len(payload) > MAX_CONFIG_BYTES:
        raise ValueError('Configuration is larger than the 4 MiB safety limit')
    with configuration_lock(target) as directory:
        current = read_at(directory, target.name)
        if expected_revision is not _ANY_REVISION and current != expected_revision:
            raise ConfigurationConflict('menu.json changed outside this editor. Reload it or explicitly overwrite after preserving a recovery copy.')
        name = '.menu-' + uuid4().hex + '.tmp'
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
        try:
            with os.fdopen(fd, 'wb') as temp:
                temp.write(payload)
                temp.flush()
                os.fsync(temp.fileno())
            if current.content is not None and (retention > 0 or recovery_reason):
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                suffix = '.pre-' + recovery_reason + '-' if recovery_reason else '.bak-'
                backup = target.name + suffix + stamp
                backup_fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
                try:
                    with os.fdopen(backup_fd, 'wb') as dest:
                        shutil.copyfileobj(BytesIO(current.content), dest)
                        dest.flush()
                        os.fsync(dest.fileno())
                except BaseException:
                    os.unlink(backup, dir_fd=directory)
                    raise
            if read_at(directory, target.name) != current:
                raise ConfigurationConflict('menu.json changed during saving; your changes are still in the editor.')
            os.replace(name, target.name, src_dir_fd=directory, dst_dir_fd=directory)
            # A cleanup failure must not report a successful save as failed.
            if retention > 0:
                try:
                    if protected_backups:
                        prune_automatic_backups(target, retention, protected_backups)
                    else:
                        prune_automatic_backups(target, retention)
                except OSError as exc:
                    _logger.warning("Could not inspect automatic backups for %s: %s", target, exc)
        finally:
            try:
                os.unlink(name, dir_fd=directory)
            except FileNotFoundError:
                pass
    return target
