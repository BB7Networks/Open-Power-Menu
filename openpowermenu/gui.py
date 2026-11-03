"""Qt Widgets front end. Uses a native QMenu rather than embedding a launcher."""
from __future__ import annotations

import subprocess
import sys

from .core import normalized_menu


def launch_menu(cfg: dict, anchor: str | None = None, theme: str | None = None) -> int:
    try:
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtGui import QCursor, QIcon
        from PySide6.QtWidgets import QApplication, QMenu, QMessageBox
    except ImportError:
        print("Open Power Menu needs PySide6. On Manjaro: sudo pacman -S --needed pyside6", file=sys.stderr)
        return 2

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Open Power Menu")
    app.setDesktopFileName("org.openpowermenu")

    menu = QMenu()
    menu.setObjectName("OpenPowerMenu")
    menu.setWindowTitle("Open Power Menu")
    menu.setToolTipsVisible(True)
    menu.setMinimumWidth(292)
    if (theme or cfg["appearance"]) == "aero":
        menu.setStyleSheet("""
            QMenu#OpenPowerMenu, QMenu {
                background-color: #242A31; color: #E4EBF2;
                border: 1px solid #5E7D94;
                padding: 5px 3px;
            }
            QMenu::item { padding: 6px 25px 6px 13px; border-radius: 2px; }
            QMenu::item:selected { background-color: #355B76; color: #FFFFFF; }
            QMenu::item:disabled { color: #89939C; }
            QMenu::separator { height: 1px; background: #445463; margin: 5px 10px; }
            QMenu::icon { padding-left: 5px; }
        """)

    def icon_for(name: str):
        return QIcon.fromTheme(name) if name else QIcon()

    def populate(target_menu, entries):
        for entry in entries:
            kind = entry["kind"]
            if kind == "separator":
                target_menu.addSeparator()
            elif kind == "submenu":
                submenu = target_menu.addMenu(icon_for(entry["icon"]), entry["title"])
                populate(submenu, entry["items"])
            else:
                item_action = target_menu.addAction(icon_for(entry["icon"]), entry["title"])
                item_action.setEnabled(entry["command"] is not None)
                if entry["command"] is not None:
                    item_action.setData(list(entry["command"].argv))
                else:
                    item_action.setToolTip("Application not installed")

    entries = normalized_menu(cfg["menu"], bool(cfg.get("show_unavailable")))
    if not entries:
        QMessageBox.information(None, "Open Power Menu", "No configured commands are available on this system.")
        return 1
    populate(menu, entries)

    placement = anchor or cfg["anchor"]
    cursor_pos = QCursor.pos()
    screen = app.screenAt(cursor_pos) or app.primaryScreen()
    available = screen.availableGeometry() if screen else None
    if placement == "bottom-left" and available:
        pos = QPoint(available.x() + 8, available.y() + available.height() - menu.sizeHint().height() - 8)
    elif placement == "bottom-right" and available:
        pos = QPoint(available.right() - menu.sizeHint().width() - 8,
                     available.y() + available.height() - menu.sizeHint().height() - 8)
    else:
        pos = cursor_pos
    # Qt/QMenu handles keyboard navigation, submenus, dismissal and the final selection.
    # On Wayland the compositor may adjust the requested popup coordinates.
    selected = menu.exec(pos)
    if selected is None:
        return 0
    argv = selected.data()
    if not argv:
        return 0
    try:
        subprocess.Popen(argv, close_fds=True, start_new_session=True)
    except OSError as exc:
        QMessageBox.critical(None, "Could not open " + selected.text(), str(exc))
        return 1
    return 0
