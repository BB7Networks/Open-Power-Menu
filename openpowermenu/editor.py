"""Native Qt menu editor: launcher-independent, no shell execution.

Uses the same menu.json as the standalone menu and Plasma widget.  Every edit
stays in memory until Save; Cancel has no effect on disk.  Previous JSON is
backed up on save.  Qt is imported only when the editor is launched.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shlex
import sys

from .desktop_apps import application_menu_item, installed_applications
from .editor_helpers import (built_in_candidates, editable_builtin_copy,
                             preview_command, display_argv)

from .core import COMMANDS, DEFAULT_CONFIG, config_path, load_config, save_config
from .plasma_panels import list_panel_applets


def launch_editor() -> int:
    try:
        from PySide6.QtCore import Qt, QUrl
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import (
            QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
            QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMenu,
            QMessageBox, QPushButton, QScrollArea, QTabWidget, QTreeWidget, QTreeWidgetItem, QToolButton,
            QListWidget, QListWidgetItem, QPlainTextEdit, QVBoxLayout, QWidget
        )
    except ImportError:
        print("The menu editor requires PySide6. On Manjaro: sudo pacman -S --needed pyside6",
              file=sys.stderr)
        return 2

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Open Power Menu — Menu Editor")
    app.setDesktopFileName("org.openpowermenu")

    def kind_of(item: dict) -> str:
        if item.get("separator"):
            return "Separator"
        if "submenu" in item:
            return "Submenu"
        if "action" in item:
            return "Built-in"
        if "desktop_file" in item and "command" in item:
            return "Application"
        return "Custom command"

    def details(item: dict) -> tuple[str, str, str]:
        kind = kind_of(item)
        if kind == "Separator":
            return ("────────────", kind, "")
        if kind == "Submenu":
            return (str(item["submenu"]), kind, str(item.get("icon") or ""))
        if kind == "Built-in":
            spec = COMMANDS.get(item["action"], {})
            return (str(item.get("label") or spec.get("title") or item["action"]), kind,
                    str(item.get("icon") or spec.get("icon") or ""))
        return (str(item.get("label") or "Custom command"), kind,
                str(item.get("icon") or "system-run"))

    def icon_for(value: str) -> QIcon:
        return QIcon(value) if value.startswith("/") else QIcon.fromTheme(value)

    class InstalledApplicationDialog(QDialog):
        """Search the user's KDE/XDG application list; no commands are run."""
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Choose installed application")
            self.resize(630, 570)
            self.selected_application = None
            layout = QVBoxLayout(self)
            help_text = QLabel(
                "Choose an installed application. Its name, icon and KDE launch "
                "command will be filled in automatically. You can edit them next.", self)
            help_text.setWordWrap(True)
            layout.addWidget(help_text)
            self.search = QLineEdit(self)
            self.search.setPlaceholderText("Search applications by name or description...")
            self.search.setClearButtonEnabled(True)
            layout.addWidget(self.search)
            self.app_list = QListWidget(self)
            self.app_list.setObjectName("installedApplicationList")
            self.app_list.setAlternatingRowColors(True)
            layout.addWidget(self.app_list, 1)
            self.details = QLabel(self)
            self.details.setWordWrap(True)
            self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(self.details)
            self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
            self.buttons.button(QDialogButtonBox.Ok).setText("Use application")
            self.buttons.accepted.connect(self.accept)
            self.buttons.rejected.connect(self.reject)
            layout.addWidget(self.buttons)
            self.applications = installed_applications()
            self.search.textChanged.connect(self.filter_applications)
            self.app_list.currentItemChanged.connect(lambda *_: self.refresh_details())
            self.app_list.itemDoubleClicked.connect(lambda *_: self.accept())
            self.filter_applications("")
            self.search.setFocus()

        def filter_applications(self, query: str):
            needle = query.casefold().strip()
            self.app_list.clear()
            for application in self.applications:
                searchable = f"{application.name} {application.generic_name} {application.comment}".casefold()
                if needle and needle not in searchable:
                    continue
                item = QListWidgetItem(icon_for(application.icon), application.name, self.app_list)
                item.setData(Qt.UserRole, application)
                if application.comment:
                    item.setToolTip(application.comment)
            if self.app_list.count():
                self.app_list.setCurrentRow(0)
            self.refresh_details()

        def refresh_details(self):
            selected = self.app_list.currentItem()
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(selected is not None)
            if selected is None:
                self.details.setText("No matching installed applications. You can add a custom command instead.")
                return
            application = selected.data(Qt.UserRole)
            self.details.setText(
                f"{application.generic_name or application.comment or application.name}\n"
                f"Desktop file: {application.desktop_file}\n"
                "Launch: KDE will use this application's installed desktop entry.")

        def accept(self):
            selected = self.app_list.currentItem()
            if selected is None:
                return
            self.selected_application = selected.data(Qt.UserRole)
            super().accept()

    class EditEntryDialog(QDialog):
        def __init__(self, initial: dict, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Add or edit menu entry")
            self.setMinimumWidth(560)
            self.original = deepcopy(initial)
            self.kind = kind_of(initial)
            self.picked_desktop_file = initial.get("desktop_file", "")
            outer = QVBoxLayout(self)
            summary = {
                "Built-in": "Built-in actions automatically use the first available program. The commands are listed below.",
                "Custom command": "Run a program with optional arguments. No terminal or shell is required.",
                "Application": "This entry launches an installed application through its desktop file.",
                "Submenu": "Create a group of menu items. Select it in Layout before adding its children.",
                "Separator": "A separator adds a dividing line between menu items.",
            }
            explanation = QLabel(summary.get(self.kind, ""), self)
            explanation.setWordWrap(True)
            outer.addWidget(explanation)
            form = QFormLayout()
            outer.addLayout(form)
            self.builtin = None
            if self.kind == "Built-in":
                self.builtin = QComboBox(self)
                for key, spec in sorted(COMMANDS.items(), key=lambda it: it[1]["title"].lower()):
                    self.builtin.addItem(spec["title"], key)
                idx = self.builtin.findData(initial.get("action", ""))
                self.builtin.setCurrentIndex(max(0, idx))
                form.addRow("Built-in action:", self.builtin)
            if self.kind != "Separator":
                self.name = QLineEdit(self)
                if self.kind == "Submenu":
                    self.name.setText(initial.get("submenu", ""))
                else:
                    self.name.setText(initial.get("label", ""))
                self.name.setPlaceholderText(
                    "Optional: uses the action name" if self.kind == "Built-in" else "Name shown in the menu")
                form.addRow("Menu label:", self.name)
                self.icon = QLineEdit(self)
                self.icon.setText(initial.get("icon", ""))
                self.icon.setPlaceholderText("Optional theme icon name, e.g. utilities-terminal")
                form.addRow("Icon:", self.icon)
            if self.kind == "Built-in":
                self.runs = QLineEdit(self)
                self.runs.setObjectName("builtInResolvedCommand")
                self.runs.setReadOnly(True)
                form.addRow("Runs on this PC:", self.runs)
                self.candidates = QPlainTextEdit(self)
                self.candidates.setObjectName("builtInFallbackCommands")
                self.candidates.setReadOnly(True)
                self.candidates.setMaximumHeight(150)
                self.candidates.setToolTip("Commands are tried in order. Only the first available program runs.")
                form.addRow("Fallback order:", self.candidates)
                custom_button = QPushButton("Customize this command...", self)
                custom_button.setToolTip("Make an independent custom entry so you can edit its launch command.")
                custom_button.clicked.connect(self.customize_builtin)
                form.addRow("", custom_button)
                self.builtin.currentIndexChanged.connect(self.refresh_builtin)
                self.refresh_builtin()
            if self.kind in ("Custom command", "Application"):
                self.argv = QLineEdit(self)
                command = initial.get("command", [])
                self.argv.setText(display_argv(command) if isinstance(command, list) else "")
                self.argv.setPlaceholderText("Example: dolphin ~/Documents")
                self.argv.setObjectName("commandArguments")
                form.addRow("Program + arguments:", self.argv)
                controls = QHBoxLayout()
                choose_app = QPushButton("Choose installed application...", self)
                choose_app.clicked.connect(self.choose_application)
                controls.addWidget(choose_app)
                choose_binary = QPushButton("Browse executable...", self)
                choose_binary.clicked.connect(self.choose_executable)
                controls.addWidget(choose_binary)
                form.addRow("", controls)
                note = QLabel(
                    "Examples: 'dolphin ~/Documents' opens a folder; 'konsole --hold' "
                    "opens a terminal. Arguments containing spaces need quotes. "
                    "Commands are run directly, not through a shell; pipes, > and && "
                    "are not interpreted. Use the application picker for GUI apps.", self)
                note.setWordWrap(True)
                form.addRow("", note)
                if self.picked_desktop_file:
                    self.desktop_source = QLabel("Selected application: " + self.picked_desktop_file, self)
                    self.desktop_source.setWordWrap(True)
                    self.desktop_source.setTextInteractionFlags(Qt.TextSelectableByMouse)
                    form.addRow("", self.desktop_source)
                self._selected_command_text = self.argv.text()
            buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            outer.addWidget(buttons)

        def refresh_builtin(self):
            effective, candidates = built_in_candidates(self.builtin.currentData())
            self.runs.setText(effective)
            self.runs.setToolTip(effective)
            self.candidates.setPlainText("\n".join(candidates))

        def customize_builtin(self):
            candidate = editable_builtin_copy(
                self.builtin.currentData(), label=self.name.text(), icon=self.icon.text())
            custom_dialog = EditEntryDialog(candidate, self)
            if custom_dialog.exec() == QDialog.Accepted:
                self.result_entry = custom_dialog.result_entry
                QDialog.accept(self)

        def choose_application(self):
            picker = InstalledApplicationDialog(self)
            if picker.exec() != QDialog.Accepted:
                return
            try:
                entry = application_menu_item(picker.selected_application)
            except ValueError as exc:
                QMessageBox.warning(self, "Application cannot be added", str(exc))
                return
            self.name.setText(entry["label"])
            self.icon.setText(entry["icon"])
            self.argv.setText(display_argv(entry["command"]))
            self.picked_desktop_file = entry["desktop_file"]
            self._selected_command_text = self.argv.text()
            if hasattr(self, "desktop_source"):
                self.desktop_source.setText("Selected application: " + self.picked_desktop_file)
            else:
                self.desktop_source = QLabel("Selected application: " + self.picked_desktop_file, self)
                self.desktop_source.setWordWrap(True)
                self.layout().insertWidget(self.layout().count() - 1, self.desktop_source)

        def choose_executable(self):
            chosen, _ = QFileDialog.getOpenFileName(self, "Choose executable", "/usr/bin")
            if chosen:
                self.argv.setText(shlex.join([chosen]))
                self.picked_desktop_file = ""

        def definition(self) -> dict:
            item = deepcopy(self.original)
            if self.kind == "Separator":
                return {"separator": True}
            if self.kind == "Submenu":
                title = self.name.text().strip()
                if not title:
                    raise ValueError("A submenu must have a name")
                item["submenu"] = title
                item["icon"] = self.icon.text().strip()
                return item
            if self.kind == "Built-in":
                item["action"] = self.builtin.currentData()
                if self.name.text().strip():
                    item["label"] = self.name.text().strip()
                else:
                    item.pop("label", None)
                if self.icon.text().strip():
                    item["icon"] = self.icon.text().strip()
                else:
                    item.pop("icon", None)
                return item
            label = self.name.text().strip()
            if not label:
                raise ValueError("Give this entry a name to show in the menu")
            try:
                argv = shlex.split(self.argv.text(), posix=True)
            except ValueError as e:
                raise ValueError("Invalid command quoting: " + str(e)) from e
            if not argv:
                raise ValueError("Enter a program and its arguments, or choose an installed application")
            if not all(argv):
                raise ValueError("Command arguments cannot be empty")
            item["label"] = label
            item["icon"] = self.icon.text().strip() or "system-run"
            item.pop("commands", None)
            item["command"] = argv
            if self.picked_desktop_file and self.argv.text() == self._selected_command_text:
                item["desktop_file"] = self.picked_desktop_file
            else:
                item.pop("desktop_file", None)  # Edited commands are no longer app shortcuts.
            return item

        def accept(self):
            try:
                self.result_entry = self.definition()
            except ValueError as e:
                QMessageBox.warning(self, "Invalid entry", str(e))
                return
            super().accept()

    class MenuEditor(QDialog):
        def __init__(self, cfg: dict):
            super().__init__()
            self.cfg = deepcopy(cfg)
            self.setWindowTitle("Open Power Menu — Configure")
            self.resize(930, 620)
            root = QVBoxLayout(self)
            tabs = QTabWidget(self)
            tabs.setObjectName("configureTabs")
            root.addWidget(tabs, 1)

            # GENERAL: button appearance, launcher association, and menu style.
            # The original launcher stays installed and keeps its own config.
            general = QWidget(tabs)
            general.setObjectName("generalTab")
            general_layout = QVBoxLayout(general)
            general_layout.setSpacing(12)
            general_help = QLabel(
                "Choose the original launcher and how the replacement Start button looks. "
                "These settings do not change the launcher's favorites or configuration.", general)
            general_help.setWordWrap(True)
            general_layout.addWidget(general_help)

            launcher_group = QGroupBox("Original launcher", general)
            launcher_layout = QVBoxLayout(launcher_group)
            launcher_row = QHBoxLayout()
            launcher_row.addWidget(QLabel("Launcher widget:", launcher_group))
            self.launcher_target = QComboBox(launcher_group)
            self.launcher_target.setMinimumWidth(260)
            self.launcher_target.addItem("Automatically find a launcher on this panel", 0)
            # Read-only panel discovery; the live widget verifies the actual
            # selected applet belongs to its own panel before touching status.
            for panel_applet in list_panel_applets():
                self.launcher_target.addItem(panel_applet.option_label, panel_applet.applet_id)
                self.launcher_target.setItemData(
                    self.launcher_target.count() - 1, panel_applet.plugin, Qt.ToolTipRole)
            prior_target = cfg.get("launcher_applet_id", 0)
            pos = self.launcher_target.findData(prior_target)
            if pos == -1 and prior_target:
                self.launcher_target.addItem(
                    f"Saved widget #{prior_target} (not found in current panel configuration)",
                    prior_target)
                pos = self.launcher_target.count() - 1
            self.launcher_target.setCurrentIndex(max(0, pos))
            self.launcher_target.setToolTip(
                "Select the original launcher even when its button is not hidden; "
                "this also controls which launcher opens on left-click and supplies its icon.")
            launcher_row.addWidget(self.launcher_target, 1)
            launcher_layout.addLayout(launcher_row)
            self.hide_launcher = QCheckBox("Hide the original launcher's panel button", launcher_group)
            self.hide_launcher.setChecked(bool(cfg.get("hide_original_launcher", False)))
            self.hide_launcher.setToolTip(
                "Keeps the original widget registered and restores its original "
                "Plasma status when this option is disabled.")
            launcher_layout.addWidget(self.hide_launcher)
            launcher_help = QLabel(
                "Left-click uses the selected launcher; right-click uses Power User Menu. "
                "Hiding is reversible, and the launcher remains installed. "
                "Emergency restore: open-power-menu --show-launcher-button", launcher_group)
            launcher_help.setWordWrap(True)
            launcher_layout.addWidget(launcher_help)
            general_layout.addWidget(launcher_group)

            icon_group = QGroupBox("Start button icon", general)
            icon_layout = QVBoxLayout(icon_group)
            icon_row = QHBoxLayout()
            self.icon_mode = QComboBox(icon_group)
            self.icon_mode.addItem("Use original launcher icon", "launcher")
            self.icon_mode.addItem("Custom icon", "custom")
            self.icon_mode.setCurrentIndex(max(0, self.icon_mode.findData(
                cfg.get("button_icon_mode", "launcher"))))
            icon_row.addWidget(self.icon_mode)
            self.button_icon = QLineEdit(icon_group)
            self.button_icon.setText(cfg.get("button_icon", ""))
            self.button_icon.setPlaceholderText("Theme icon name or image path")
            self.button_icon.setToolTip(
                "Enter a theme icon (for example start-here-kde), "
                "or browse for a local PNG/SVG/JPEG/WebP/ICO file.")
            icon_row.addWidget(self.button_icon, 1)
            self.browse_icon = QPushButton("Browse…", icon_group)
            icon_row.addWidget(self.browse_icon)
            self.icon_preview = QLabel(icon_group)
            self.icon_preview.setFixedSize(36, 36)
            self.icon_preview.setAlignment(Qt.AlignCenter)
            icon_row.addWidget(self.icon_preview)
            icon_layout.addLayout(icon_row)
            icon_help = QLabel("Auto follows the original launcher's current Plasma icon. "
                "A custom icon only changes the Open Power Menu button.", icon_group)
            icon_help.setWordWrap(True)
            icon_layout.addWidget(icon_help)
            general_layout.addWidget(icon_group)

            def refresh_icon_preview():
                custom = self.icon_mode.currentData() == "custom"
                self.button_icon.setEnabled(custom)
                self.browse_icon.setEnabled(custom)
                if not custom:
                    self.icon_preview.setPixmap(QIcon().pixmap(24, 24))
                    self.icon_preview.setText("Auto")
                    self.icon_preview.setToolTip("Uses the selected launcher's live icon")
                    return
                name = self.button_icon.text().strip()
                if name.startswith("file://"):
                    icon = QIcon(QUrl(name).toLocalFile())
                elif name.startswith("/"):
                    icon = QIcon(name)
                else:
                    icon = QIcon.fromTheme(name or "start-here-kde")
                self.icon_preview.setText("")
                self.icon_preview.setPixmap(icon.pixmap(28, 28))
                self.icon_preview.setToolTip("Preview; theme icons depend on your desktop")

            def browse_icon():
                from pathlib import Path
                selected, _ = QFileDialog.getOpenFileName(
                    self, "Choose Start button image", str(Path.home()),
                    "Image icons (*.png *.svg *.svgz *.jpg *.jpeg *.webp *.ico)")
                if selected:
                    self.button_icon.setText(QUrl.fromLocalFile(selected).toString())

            self.icon_mode.currentIndexChanged.connect(lambda _index: refresh_icon_preview())
            self.button_icon.textChanged.connect(lambda _value: refresh_icon_preview())
            self.browse_icon.clicked.connect(browse_icon)
            refresh_icon_preview()

            style_group = QGroupBox("Power User Menu appearance", general)
            style_form = QFormLayout(style_group)
            self.appearance = QComboBox(style_group)
            self.appearance.addItem("Use the desktop theme", "native")
            self.appearance.addItem("Dark Aero", "aero")
            self.appearance.setCurrentIndex(max(0, self.appearance.findData(
                cfg.get("appearance", "native"))))
            style_form.addRow("Menu style:", self.appearance)
            general_layout.addWidget(style_group)
            general_layout.addStretch(1)
            general_scroll = QScrollArea(tabs)
            general_scroll.setWidgetResizable(True)
            general_scroll.setFrameShape(QFrame.NoFrame)
            general_scroll.setWidget(general)
            tabs.addTab(general_scroll, "General")

            # LAYOUT: only the editable Power User Menu tree lives here.
            layout_tab = QWidget(tabs)
            layout_tab.setObjectName("layoutTab")
            layout_root = QVBoxLayout(layout_tab)
            layout_help = QLabel(
                "Add an installed app with a search, choose a built-in system action, "
                "or enter an advanced command. The Runs column shows what each item launches. "
                "Select a submenu before Add to insert inside it; otherwise Add inserts after the selected entry.",
                layout_tab)
            layout_help.setWordWrap(True)
            layout_root.addWidget(layout_help)
            self.tree = QTreeWidget(layout_tab)
            self.tree.setObjectName("menuLayoutTree")
            self.tree.setColumnCount(3)
            self.tree.setHeaderLabels(["Menu item", "Type", "Runs on this computer"])
            self.tree.setColumnWidth(0, 240)
            self.tree.setColumnWidth(1, 135)
            self.tree.setAlternatingRowColors(True)
            self.tree.setSelectionMode(QTreeWidget.SingleSelection)
            self.tree.itemDoubleClicked.connect(lambda item, column: self.edit_selected())
            layout_root.addWidget(self.tree, 1)
            line = QHBoxLayout()
            self.add_button = QToolButton(layout_tab)
            self.add_button.setText("Add …")
            self.add_button.setPopupMode(QToolButton.InstantPopup)
            popup = QMenu(self.add_button)
            popup.addAction("Installed application...", self.add_application)
            popup.addSeparator()
            popup.addAction("Built-in command", lambda: self.add_entry({"action": "terminal"}, edit=True))
            popup.addAction("Custom command", lambda: self.add_entry({"label": "", "icon": "system-run", "command": []}, edit=True))
            popup.addAction("Submenu", lambda: self.add_entry({"submenu": "New submenu", "icon": "folder", "items": []}, edit=True))
            popup.addAction("Separator", lambda: self.add_entry({"separator": True}, edit=False))
            self.add_button.setMenu(popup)
            line.addWidget(self.add_button)
            for label, callback in (("Edit", self.edit_selected), ("Remove", self.remove_selected),
                                    ("Move up", lambda: self.move_selected(-1)),
                                    ("Move down", lambda: self.move_selected(1))):
                b = QPushButton(label, layout_tab)
                b.clicked.connect(callback)
                line.addWidget(b)
            line.addStretch(1)
            layout_root.addLayout(line)

            bottom_row = QHBoxLayout()
            self.show_missing = QCheckBox("Show unavailable apps as disabled entries", layout_tab)
            self.show_missing.setChecked(bool(cfg.get("show_unavailable", False)))
            bottom_row.addWidget(self.show_missing)
            bottom_row.addStretch(1)
            reset = QPushButton("Restore default layout", layout_tab)
            reset.setToolTip("Only resets the menu layout and unavailable-entry option; General is unchanged")
            reset.clicked.connect(self.restore_defaults)
            bottom_row.addWidget(reset)
            layout_root.addLayout(bottom_row)
            layout_note = QLabel(
                "These are the Power User Menu entries, not your original launcher's "
                "applications or favorites. Nothing is written until you select Save.",
                layout_tab)
            layout_note.setWordWrap(True)
            layout_root.addWidget(layout_note)
            tabs.addTab(layout_tab, "Layout")

            buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            root.addWidget(buttons)
            self.fill(cfg["menu"])

        def _make_item(self, entry: dict):
            # Build unattached: QTreeWidgetItem cannot be inserted into a
            # second parent while still belonging to the first.
            label, kind, icon = details(entry)
            item = QTreeWidgetItem()
            item.setText(0, label)
            item.setText(1, kind)
            item.setText(2, preview_command(entry))
            item.setToolTip(2, preview_command(entry))
            if icon:
                item.setIcon(0, icon_for(icon))
            item.setData(0, Qt.UserRole, deepcopy(entry))
            if kind == "Submenu":
                for child in entry.get("items", []):
                    item.addChild(self._make_item(child))
                item.setExpanded(True)
            return item

        def fill(self, entries):
            self.tree.clear()
            for entry in entries:
                self.tree.addTopLevelItem(self._make_item(entry))
            self.tree.expandAll()
            self.tree.resizeColumnToContents(0)

        def _selected(self):
            return self.tree.currentItem()

        def _container_for_add(self):
            selected = self._selected()
            if selected is None:
                return self.tree.invisibleRootItem(), self.tree.topLevelItemCount()
            entry = selected.data(0, Qt.UserRole)
            if kind_of(entry) == "Submenu":
                return selected, selected.childCount()
            parent = selected.parent() or self.tree.invisibleRootItem()
            idx = parent.indexOfChild(selected)
            return parent, idx + 1

        def add_application(self):
            picker = InstalledApplicationDialog(self)
            if picker.exec() != QDialog.Accepted:
                return
            try:
                entry = application_menu_item(picker.selected_application)
            except ValueError as exc:
                QMessageBox.warning(self, "Application cannot be added", str(exc))
                return
            self.add_entry(entry, edit=True)

        def add_entry(self, entry, edit):
            if edit:
                dialog = EditEntryDialog(entry, self)
                if dialog.exec() != QDialog.Accepted:
                    return
                entry = dialog.result_entry
            parent, index = self._container_for_add()
            item = self._make_item(entry)
            parent.insertChild(index, item)
            parent.setExpanded(True)
            self.tree.setCurrentItem(item)

        def edit_selected(self):
            selected = self._selected()
            if not selected:
                return
            original = selected.data(0, Qt.UserRole)
            if kind_of(original) == "Separator":
                return
            dialog = EditEntryDialog(original, self)
            if dialog.exec() != QDialog.Accepted:
                return
            updated = dialog.result_entry
            selected.setData(0, Qt.UserRole, updated)
            label, kind, icon = details(updated)
            selected.setText(0, label)
            selected.setText(1, kind)
            selected.setText(2, preview_command(updated))
            selected.setToolTip(2, preview_command(updated))
            selected.setIcon(0, icon_for(icon))

        def remove_selected(self):
            selected = self._selected()
            if selected is None:
                return
            parent = selected.parent() or self.tree.invisibleRootItem()
            parent.removeChild(selected)

        def move_selected(self, delta: int):
            selected = self._selected()
            if not selected:
                return
            parent = selected.parent() or self.tree.invisibleRootItem()
            index = parent.indexOfChild(selected)
            destination = index + delta
            if destination < 0 or destination >= parent.childCount():
                return
            detached = parent.takeChild(index)
            parent.insertChild(destination, detached)
            self.tree.setCurrentItem(detached)

        def _walk(self, parent):
            entries = []
            for index in range(parent.childCount()):
                item = parent.child(index)
                data = deepcopy(item.data(0, Qt.UserRole))
                if kind_of(data) == "Submenu":
                    data["items"] = self._walk(item)
                entries.append(data)
            return entries

        def restore_defaults(self):
            if QMessageBox.question(self, "Restore defaults", "Replace the unsaved Power User Menu layout with standard defaults?\nGeneral settings will stay as they are. Nothing changes on disk until Save.") != QMessageBox.Yes:
                return
            self.fill(DEFAULT_CONFIG["menu"])
            self.show_missing.setChecked(DEFAULT_CONFIG["show_unavailable"])
            # Reset applies to the Layout tab only; General settings remain untouched.

        def accept(self):
            self.cfg["menu"] = self._walk(self.tree.invisibleRootItem())
            self.cfg["show_unavailable"] = self.show_missing.isChecked()
            self.cfg["appearance"] = self.appearance.currentData()
            self.cfg["hide_original_launcher"] = self.hide_launcher.isChecked()
            self.cfg["launcher_applet_id"] = int(self.launcher_target.currentData())
            self.cfg["button_icon_mode"] = self.icon_mode.currentData()
            self.cfg["button_icon"] = self.button_icon.text().strip()
            try:
                saved = save_config(self.cfg)
            except (ValueError, OSError) as exc:
                QMessageBox.critical(self, "Could not save menu", str(exc))
                return
            self.saved_path = saved
            super().accept()

    try:
        cfg = load_config()
    except (ValueError, OSError) as exc:
        QMessageBox.critical(None, "Invalid configuration", f"Could not open {config_path()}:\n{exc}\n\nFix or back up the file before continuing.")
        return 2
    dialog = MenuEditor(cfg)
    return 0 if dialog.exec() == QDialog.Accepted else 0
