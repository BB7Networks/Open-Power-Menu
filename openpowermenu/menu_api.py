"""Convert resolved commands into stable, non-executable widget UI data.

The panel sends an item key, never a shell command. The service resolves the
command against the current user configuration at dispatch time.
"""
from __future__ import annotations

import json
from typing import Any

from .core import normalized_menu


def to_public_menu(items: list[dict], prefix: tuple[int, ...] = ()) -> list[dict]:
    result = []
    for i, item in enumerate(items):
        key = ".".join(map(str, prefix + (i,)))
        common = {"kind": item["kind"], "key": key}
        if item["kind"] == "separator":
            result.append(common)
        elif item["kind"] == "submenu":
            result.append({**common, "title": item["title"], "icon": item["icon"],
                           "items": to_public_menu(item["items"], prefix + (i,))})
        else:
            result.append({**common, "title": item["title"], "icon": item["icon"],
                           "enabled": item["command"] is not None,
                           "close_before_run": item.get("close_before_run", False)})
    return result


def public_menu_from_config(config: dict) -> list[dict]:
    return to_public_menu(normalized_menu(config["menu"], config.get("show_unavailable", False)))


def command_at_key(config: dict, key: str):
    if not isinstance(key, str) or not key or len(key) > 128:
        return None
    bits = key.split(".")
    if len(bits) > 12 or any(not part.isascii() or not part.isdigit() or len(part) > 5 for part in bits):
        return None
    tree = normalized_menu(config["menu"], config.get("show_unavailable", False))
    item = None
    for j, part in enumerate(bits):
        idx = int(part)
        if idx >= len(tree):
            return None
        item = tree[idx]
        if j < len(bits) - 1:
            if item["kind"] != "submenu":
                return None
            tree = item["items"]
    return item["command"] if item and item["kind"] == "command" else None


def public_json(config: dict) -> str:
    return json.dumps(public_menu_from_config(config), separators=(",", ":"), ensure_ascii=False)
