"""CLI entry point, intentionally importable without Qt."""
import argparse
import json
import sys
import time

from . import __version__
from .core import COMMANDS, DEFAULT_CONFIG, config_path, describe_menu, load_config, normalized_menu


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Launcher-independent Linux Power User menu")
    parser.add_argument("--list", action="store_true", help="List visible menu entries and available tools without opening a GUI")
    parser.add_argument("--check", action="store_true", help="Check configuration and print resolved menu contents")
    parser.add_argument("--diagnose-launch", action="store_true", help="Open the standalone menu and report startup, exposure and focus (does not test KDE shortcut dispatch)")
    parser.add_argument("--default-config", action="store_true", help="Print the default menu.json file")
    parser.add_argument("--anchor", choices=("cursor", "bottom-left", "bottom-right"), help="Where to open the menu")
    parser.add_argument("--theme", choices=("native", "aero"), help="Override configured theme for this invocation")
    parser.add_argument("--service", action="store_true", help="Run the D-Bus-activated panel backend")
    parser.add_argument("--edit", action="store_true", help="Edit menu entries in a graphical settings window")
    parser.add_argument("--show-launcher-button", action="store_true", help="Emergency recovery: show the original launcher button again")
    parser.add_argument("--launcher-diagnostics", action="store_true", help="List panel applets read-only, for selecting the launcher widget")
    parser.add_argument("--restart-owned-service", action="store_true", help="Safely restart this application's already running backend")
    parser.add_argument("--widget-menu-json", action="store_true", help="Preview the panel menu JSON without Qt")
    parser.add_argument("--version", action="version", version=f"Open Power Menu {__version__}")
    args = parser.parse_args(argv)
    started = time.monotonic()
    sequence = 0
    def trace(event, **state):
        nonlocal sequence
        sequence += 1
        print('OPM_LAUNCH ' + json.dumps(dict(seq=sequence, elapsed_ms=round((time.monotonic() - started) * 1000),
                                            event=event, **state)), flush=True)
    diagnostic = trace if args.diagnose_launch else None
    if diagnostic:
        diagnostic('cli-start')
    if args.service:
        from .service import run_service
        return run_service()
    if args.restart_owned_service:
        from .service import stop_owned_service
        return stop_owned_service()
    if args.show_launcher_button:
        from .core import save_config
        try:
            config = load_config()
            config["hide_original_launcher"] = False
            saved = save_config(config)
            print("Original launcher visibility requested. The widget will restore it on its next refresh:", saved)
            return 0
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            print("Could not restore launcher visibility:", exc, file=sys.stderr)
            return 2
    if args.launcher_diagnostics:
        from .plasma_panels import list_panel_applets
        applets = list_panel_applets()
        if not applets:
            print("No saved Plasma panel applets found. Is this a Plasma desktop session?")
        for a in applets:
            print(f"{a.option_label}: {a.plugin}")
        print("Read-only discovery. A selected widget must still exist on the same live panel.")
        return 0
    if args.edit:
        from .editor import launch_editor
        return launch_editor()
    if args.default_config:
        print(json.dumps(DEFAULT_CONFIG, indent=2))
        return 0
    try:
        cfg = load_config()
        entries = normalized_menu(cfg["menu"], bool(cfg.get("show_unavailable")))
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        if diagnostic:
            diagnostic('configuration-error')
        print(f"Invalid {config_path()}: {exc}", file=sys.stderr)
        return 2
    if args.widget_menu_json:
        from .menu_api import public_json
        print(public_json(cfg))
        return 0
    if args.list or args.check:
        print("Open Power Menu v" + __version__)
        print("Configuration:", config_path(), "(using defaults)" if not config_path().exists() else "")
        print("Launcher dependence: none")
        print("Desktop:", __import__("os").environ.get("XDG_CURRENT_DESKTOP", "unknown"))
        print("\n".join(describe_menu(entries)) or "(no entries available)")
        return 0
    from .gui import launch_menu
    result = launch_menu(cfg, anchor=args.anchor, theme=args.theme, diagnostic=diagnostic)
    if diagnostic:
        diagnostic('complete', exit_code=result)
    return result
