"""Qt Widgets front end. Uses a native QMenu rather than embedding a launcher."""
from __future__ import annotations

import sys

from .core import normalized_menu
from .launching import launch_detached


def launch_menu(cfg: dict, anchor: str | None = None, theme: str | None = None, *, diagnostic=None) -> int:
    try:
        from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
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
    # xdg-shell cannot create a grabbing popup in a fresh process: there is
    # neither a transient parent nor an input serial. Use a real toplevel on
    # Wayland, with QMenu's normal actions, keyboard navigation and submenus.
    # The compositor chooses placement and grants activation (including KDE's
    # launch token); we never force focus or try to fabricate an input serial.
    standalone_window = app.platformName().startswith('wayland')
    if standalone_window:
        menu.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)

    def report(event):
        if diagnostic:
            win = menu.windowHandle()
            diagnostic(event, platform=app.platformName(), toplevel=standalone_window,
                       visible=menu.isVisible(), exposed=bool(win and win.isExposed()),
                       active=menu.isActiveWindow())

    class VisibilityProbe(QObject):
        def eventFilter(self, watched, event):
            if event.type() in (QEvent.Expose, QEvent.WindowActivate, QEvent.WindowDeactivate, QEvent.Hide):
                report(event.type().name)
            return False

    probe = VisibilityProbe(menu)
    was_active = False
    def application_state(state):
        nonlocal was_active
        if state == Qt.ApplicationActive:
            was_active = True
        elif was_active and standalone_window:
            # Changing to one of our submenus keeps the application active.
            # Clicking another application dismisses the standalone toplevel.
            menu.close()

    def shown():
        win = menu.windowHandle()
        if win:
            if diagnostic:
                win.installEventFilter(probe)
            if standalone_window:
                win.requestActivate()
        report('show-requested')

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

    # Explicitly parent submenus and retain their wrappers. The PySide 6.10
    # addMenu(icon, title) overload can leave an invalid submenu wrapper.
    submenus = []
    def populate(target_menu, entries):
        for entry in entries:
            kind = entry["kind"]
            if kind == "separator":
                target_menu.addSeparator()
            elif kind == "submenu":
                submenu = QMenu(entry["title"], target_menu)
                submenu.setIcon(icon_for(entry["icon"]))
                target_menu.addMenu(submenu)
                submenus.append(submenu)
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
    app.applicationStateChanged.connect(application_state)
    application_state(app.applicationState())

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
    # Timers belong to the menu: an early dismissal cannot leave callbacks
    # referring to a deleted window or a later launch.
    for delay in (0, 250, 1500):
        timer = QTimer(menu)
        timer.setSingleShot(True)
        timer.timeout.connect(shown if delay == 0 else lambda: report('visibility-sample'))
        timer.start(delay)
    try:
        selected = menu.exec(pos)
    finally:
        app.applicationStateChanged.disconnect(application_state)
        for timer in menu.findChildren(QTimer):
            timer.stop()
        report('dismissed')
    if selected is None:
        return 0
    argv = selected.data()
    if not argv:
        return 0
    try:
        launch_detached(argv)
    except OSError as exc:
        QMessageBox.critical(None, "Could not open " + selected.text(), str(exc))
        return 1
    return 0
