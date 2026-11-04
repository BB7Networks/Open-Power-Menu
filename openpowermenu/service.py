"""D-Bus-activated, local-user command dispatcher for Plasma panel widget.

No shell input from D-Bus is accepted. Only indexed entries in the user's own
menu.json may execute. QtDBus needs PySide6, already required by the app.
"""
from __future__ import annotations

import json
import subprocess
import sys

from .launching import launch_detached, reap_children

BUS_NAME = "org.openpowermenu.Service"
OBJECT_PATH = "/OpenPowerMenu"


def run_service() -> int:
    try:
        from PySide6.QtCore import QCoreApplication, QObject, QTimer, Slot
        from PySide6.QtDBus import QDBusConnection
    except ImportError:
        print("D-Bus service needs PySide6 with QtDBus. Install Manjaro package pyside6.", file=sys.stderr)
        return 2

    from .core import load_config
    from .menu_api import public_json, command_at_key

    app = QCoreApplication(sys.argv[:1])
    app.setApplicationName("Open Power Menu backend")
    idle_timer = QTimer()
    idle_timer.setSingleShot(True)
    idle_timer.setInterval(5 * 60 * 1000)
    idle_timer.timeout.connect(app.quit)

    # Popen only opportunistically reaps discarded children on a later launch.
    # Reap promptly even when no further menu requests arrive; never signal apps.
    child_timer = QTimer()
    child_timer.setInterval(1000)

    def reap_finished():
        if not reap_children():
            child_timer.stop()

    child_timer.timeout.connect(reap_finished)

    def launch(argv):
        launch_detached(argv)
        if not child_timer.isActive():
            child_timer.start()

    class MenuService(QObject):
        def touch(self):
            idle_timer.start()

        @Slot(result=str)
        def GetMenu(self):
            self.touch()
            try:
                return public_json(load_config())
            except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
                print("Open Power Menu configuration error:", exc, file=sys.stderr)
                return json.dumps([{"kind": "command", "key": "",
                                    "title": "Invalid menu.json — see README",
                                    "icon": "dialog-error", "enabled": False}])

        @Slot(str, result=bool)
        def Run(self, key):
            self.touch()
            try:
                cmd = command_at_key(load_config(), key)
                if cmd is None:
                    return False
                launch(cmd.argv)
                return True
            except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
                print("Open Power Menu could not run item", key, ":", exc, file=sys.stderr)
                return False

        @Slot(result=bool)
        def Edit(self):
            self.touch()
            # Open the user's installed editor; never pass command strings
            # or any caller-controlled arguments to a shell.
            from pathlib import Path
            script = Path(__file__).resolve().parents[1] / "run.py"
            try:
                launch([sys.executable, str(script), "--edit"])
                return True
            except OSError as exc:
                print("Could not start Open Power Menu editor:", exc, file=sys.stderr)
                return False

        @Slot(result=str)
        def GetIntegration(self):
            """Read a harmless visibility preference; widget owns live integration."""
            self.touch()
            try:
                cfg = load_config()
                return json.dumps({"hide_original_launcher": cfg.get("hide_original_launcher", False),
                                   "launcher_applet_id": cfg.get("launcher_applet_id", 0),
                                   "button_icon_mode": cfg.get("button_icon_mode", "launcher"),
                                   "button_icon": cfg.get("button_icon", "")})
            except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
                print("Open Power Menu integration configuration error:", exc, file=sys.stderr)
                return json.dumps({"hide_original_launcher": False, "launcher_applet_id": 0,
                                   "button_icon_mode": "launcher", "button_icon": ""})

        @Slot(result=str)
        def Ping(self):
            self.touch()
            return "Open Power Menu v0.4.17"

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        print("No D-Bus user session bus. Is this running inside your desktop session?", file=sys.stderr)
        return 1
    service = MenuService()
    if not bus.registerService(BUS_NAME):
        print("Could not register D-Bus service", BUS_NAME, bus.lastError().message(), file=sys.stderr)
        return 1
    if not bus.registerObject(OBJECT_PATH, BUS_NAME, service, QDBusConnection.ExportAllSlots):
        print("Could not register D-Bus object", OBJECT_PATH, bus.lastError().message(), file=sys.stderr)
        bus.unregisterService(BUS_NAME)
        return 1
    idle_timer.start()
    return app.exec()


def stop_owned_service() -> int:
    """Stop only this user's *installed* Open Power Menu service.

    Intended for upgrades while the old backend may still hold the DBus name.
    Never signal arbitrary processes, another account's service, or a service
    running from a development checkout.
    """
    import os
    import re
    import signal
    from pathlib import Path

    try:
        reply = subprocess.run([
            "busctl", "--user", "call", "org.freedesktop.DBus",
            "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "GetConnectionUnixProcessID", "s", BUS_NAME,
        ], capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return 0  # D-Bus may not be available in this session.
    match = re.fullmatch(r"u\s+(\d+)\s*", reply.stdout or "")
    if reply.returncode or not match:
        return 0
    pid = int(match.group(1))
    if pid < 2 or pid == os.getpid():
        return 0
    proc = Path("/proc") / str(pid)
    try:
        status = (proc / "status").read_text()
        uid_line = next(line for line in status.splitlines() if line.startswith("Uid:"))
        if int(uid_line.split()[1]) != os.getuid():
            return 0
        args = (proc / "cmdline").read_bytes().split(b"\0")
        decoded = [p.decode("utf-8", "replace") for p in args if p]
        data_home = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local/share"))
        expected = str(data_home / "open-power-menu/run.py")
        if "--service" not in decoded or expected not in decoded:
            print("Backend belongs to a different process; leaving it running")
            return 0
        os.kill(pid, signal.SIGTERM)
        print("Stopped previous Open Power Menu backend; D-Bus will activate v0.4.17 on demand")
    except (OSError, StopIteration, ValueError):
        return 0
    return 0
