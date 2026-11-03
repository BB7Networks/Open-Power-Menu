"""Editor presentation helpers, separated from Qt for reliable tests."""
from __future__ import annotations

from copy import deepcopy
import shlex
from pathlib import Path

from .core import COMMANDS, desktop_is_available, expand_part, resolve_action, which_executable


def display_argv(argv: list[str] | tuple[str, ...]) -> str:
    return shlex.join(argv) if argv else ""


def built_in_candidates(action_id: str) -> tuple[str, list[str]]:
    """Show both the effective command and the fallback order transparently."""
    spec = COMMANDS[action_id]
    selected = resolve_action(action_id)
    effective = display_argv(selected.argv) if selected else "Not available on this computer"
    valid_spec = desktop_is_available(spec.get("desktops"))
    required_path = spec.get("path_required")
    if required_path and not Path(expand_part(required_path)).exists():
        valid_spec = False
    for required in spec.get("requires", []):
        if not which_executable(required):
            valid_spec = False
    details = []
    for index, candidate in enumerate(spec.get("commands", []), start=1):
        if isinstance(candidate, dict):
            raw = candidate.get("argv", [])
            valid_desktop = desktop_is_available(candidate.get("desktops"))
        else:
            raw, valid_desktop = candidate, True
        if not isinstance(raw, list) or not raw:
            continue
        argv = [expand_part(part) for part in raw]
        available = valid_spec and valid_desktop and which_executable(argv[0])
        status = "installed" if available else "not available"
        details.append(f"{index}. {display_argv(argv)}  [{status}]")
    return effective, details


def editable_builtin_copy(action_id: str, *, label: str = "", icon: str = "") -> dict:
    """Detach a built-in into a custom entry; keep the original builtin unchanged."""
    spec = COMMANDS[action_id]
    selected = resolve_action(action_id)
    if selected:
        argv = list(selected.argv)
    else:
        first = spec["commands"][0]
        argv = deepcopy(first.get("argv", []) if isinstance(first, dict) else first)
    return {"label": label.strip() or spec["title"],
            "icon": icon.strip() or spec["icon"],
            "command": argv}


def preview_command(entry: dict) -> str:
    if entry.get("separator") or "submenu" in entry:
        return ""
    if "action" in entry:
        selected = resolve_action(entry["action"])
        return display_argv(selected.argv) if selected else "Unavailable on this computer"
    if "command" in entry and isinstance(entry["command"], list):
        return display_argv(entry["command"])
    if "commands" in entry and isinstance(entry["commands"], list):
        for candidate in entry["commands"]:
            argv = candidate.get("argv", []) if isinstance(candidate, dict) else candidate
            if isinstance(argv, list):
                return display_argv(argv)
    return ""
