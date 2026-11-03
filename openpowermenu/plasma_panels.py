"""Read-only KDE panel applet discovery for optional launcher-button masking.

This deliberately never writes appletsrc. The live QML widget independently
validates that any selected applet is still present in its own containment.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re

GROUP_RE = re.compile(r'^\[Containments\]\[(\d+)\](?:\[Applets\]\[(\d+)\])?$')
KNOWN_LAUNCHER_IDS = {
    'org.kde.plasma.kickoff', 'org.kde.plasma.kicker',
    'org.kde.plasma.kickerdash', 'dev.xarbit.appgrid',
    'dev.xarbit.appgrid.panel',
}


@dataclass(frozen=True)
class PanelApplet:
    panel_id: int
    applet_id: int
    plugin: str
    title: str
    likely_launcher: bool

    @property
    def option_label(self) -> str:
        suffix = '' if self.likely_launcher else '  [manual selection]'
        return f'Panel {self.panel_id}: {self.title} (widget {self.applet_id}){suffix}'


def is_likely_launcher(plugin: str, title: str = '') -> bool:
    if plugin in KNOWN_LAUNCHER_IDS:
        return True
    words = f'{plugin.replace(".", " ").replace("_", " ")} {title}'.lower()
    return any(term in words for term in (
        'appgrid', 'kickoff', 'kicker', 'application launcher',
        'application dashboard', 'start menu', 'startmenu',
        'launcher widget', 'launcher menu', 'application menu', 'launcher',
    ))


def _metadata_name(plugin: str, data_home: Path) -> str:
    roots = [data_home / 'plasma/plasmoids', Path('/usr/share/plasma/plasmoids')]
    for root in roots:
        file = root / plugin / 'metadata.json'
        try:
            value = json.loads(file.read_text(encoding='utf-8')).get('KPlugin', {}).get('Name')
            if isinstance(value, str) and value:
                return value
        except (OSError, ValueError, TypeError):
            continue
    return plugin


def list_panel_applets(path: Path | None = None, data_home: Path | None = None) -> list[PanelApplet]:
    """Discover local panel widgets; existing saved config may be stale.

    Only exact two- and four-level KConfig group headings are inspected.
    Nested configuration keys never become widget records. Duplicate IDs,
    incomplete records and non-panel desktop containments are ignored.
    """
    if path is None:
        path = Path(os.environ.get('XDG_CONFIG_HOME') or (Path.home() / '.config')) / 'plasma-org.kde.plasma.desktop-appletsrc'
    if data_home is None:
        data_home = Path(os.environ.get('XDG_DATA_HOME') or (Path.home() / '.local/share'))
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError):
        return []
    sections: dict[tuple[int, int | None], dict[str, str]] = {}
    current = None
    for line in lines:
        line = line.strip()
        if line.startswith('['):
            m = GROUP_RE.fullmatch(line)
            current = (int(m.group(1)), int(m.group(2)) if m.group(2) is not None else None) if m else None
            if current is not None:
                sections.setdefault(current, {})
        elif current is not None and '=' in line and not line.startswith(('#', ';')):
            key, value = line.split('=', 1)
            sections[current][key.strip()] = value.strip()
    panel_ids = {pid for (pid, aid), values in sections.items()
                 if aid is None and values.get('plugin', '').lower() in (
                     'org.kde.panel', 'org.kde.plasma.panel')}
    results: list[PanelApplet] = []
    seen: set[int] = set()
    for (pid, aid), values in sections.items():
        if pid not in panel_ids or aid is None or aid in seen or aid <= 0:
            continue
        plugin = values.get('plugin', '').strip()
        if not plugin or plugin == 'org.openpowermenu.start':
            continue
        seen.add(aid)
        title = _metadata_name(plugin, data_home)
        results.append(PanelApplet(pid, aid, plugin, title, is_likely_launcher(plugin, title)))
    return sorted(results, key=lambda a: (not a.likely_launcher, a.panel_id, a.applet_id))
