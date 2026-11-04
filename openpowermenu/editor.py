"""Native Qt menu editor: launcher-independent, no shell execution.

Uses the same menu.json as the standalone menu and Plasma widget. Edits stay in
memory until Save; closing dirty state offers Save/Discard/Cancel. Explicit
restores preserve a recovery copy. Qt is imported only when the editor opens.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shlex
import sys

from .desktop_apps import application_menu_item, installed_applications
from .editor_helpers import (built_in_candidates, editable_builtin_copy,
                             preview_command, display_argv)

from .core import (COMMANDS, DEFAULT_CONFIG, config_path, save_config,
                   validate_configuration, validate_menu_definition, MenuValidationError)
from .recovery import (ConfigurationConflict, current_revision, decode_configuration)
from .plasma_panels import list_panel_applets


def create_editor(path: Path | None = None):
    try:
        from PySide6.QtCore import Qt, QUrl
        from PySide6.QtGui import QIcon, QAction, QFontDatabase, QKeySequence, QUndoStack
        from PySide6.QtWidgets import (
            QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
            QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMenu,
            QMessageBox, QPushButton, QScrollArea, QSpinBox, QTabWidget, QTreeWidget, QTreeWidgetItem, QToolButton, QHeaderView,
            QListWidget, QListWidgetItem, QPlainTextEdit, QSizePolicy, QVBoxLayout, QWidget
        )
    except ImportError:
        print("The menu editor requires PySide6. On Manjaro: sudo pacman -S --needed pyside6",
              file=sys.stderr)
        raise

    from .editor_tree import LayoutChange, MenuTree
    from .editor_toolbar import EditorToolbar
    target = path or config_path()
    revision = current_revision(target)
    config = decode_configuration(revision.content)
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
                "Search for an application, then review its name, icon and launch command.", self)
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
            self.resize(560, 420)
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
                    "Quote arguments containing spaces. Commands run directly; "
                    "shell operators such as pipes, > and && are not interpreted.", self)
                note.setToolTip("Examples: dolphin ~/Documents; konsole --hold. Use the application picker for GUI apps.")
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
            try:
                self.initial_definition = self.definition()
            except ValueError:
                self.initial_definition = None

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
                return item
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
                if self.result_entry == self.initial_definition:
                    self.result_entry = deepcopy(self.original)
                validate_menu_definition([self.result_entry])
            except ValueError as e:
                QMessageBox.warning(self, "Invalid entry", str(e))
                field = self.argv if hasattr(self, "argv") and self.name.text().strip() else getattr(self, "name", None)
                if field is not None:
                    field.setFocus()
                return
            super().accept()

    class MenuEditor(QDialog):
        def __init__(self, cfg: dict):
            super().__init__()
            self.cfg = deepcopy(cfg)
            self.target, self.revision = target, revision
            self.saved_config = deepcopy(cfg)
            self._applying, self._closing = False, False
            self.undo_stack = QUndoStack(self)
            self.setWindowTitle("Open Power Menu — Configure[*]")
            self.resize(930, 620)
            root = QVBoxLayout(self)
            tabs = QTabWidget(self)
            self.tabs = tabs
            tabs.setObjectName("configureTabs")
            root.addWidget(tabs, 1)

            # GENERAL: button appearance, launcher association, and menu style.
            # The original launcher stays installed and keeps its own config.
            general = QWidget(tabs)
            general.setObjectName("generalTab")
            general_layout = QVBoxLayout(general)
            general_layout.setSpacing(12)
            general_help = QLabel(
                "Choose your launcher, Start button icon and menu style. "
                "Your launcher and favorites stay intact.", general)
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
                "Left-click opens your launcher; right-click opens Power User Menu. "
                "Hiding the original button is reversible.", launcher_group)
            launcher_help.setWordWrap(True)
            launcher_layout.addWidget(launcher_help)
            restore_row = QHBoxLayout()
            restore_row.addWidget(QLabel("Emergency restore", launcher_group))
            restore_row.addStretch(1)
            restore_command = "open-power-menu --show-launcher-button"
            restore_copy = QPushButton("Copy", launcher_group)
            restore_copy.setObjectName("copyEmergencyRestore")
            restore_copy.setAccessibleName("Copy emergency restore command")
            restore_copy.clicked.connect(lambda: QApplication.clipboard().setText(restore_command))
            restore_row.addWidget(restore_copy)
            launcher_layout.addLayout(restore_row)
            restore_text = QLabel(restore_command, launcher_group)
            restore_text.setObjectName("emergencyRestoreCommand")
            restore_text.setTextFormat(Qt.PlainText)
            restore_text.setWordWrap(True)
            restore_text.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
            restore_text.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            restore_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
            restore_font.setPointSizeF(self.font().pointSizeF())
            restore_text.setFont(restore_font)
            launcher_layout.addWidget(restore_text)
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

            shortcut_group = QGroupBox("Keyboard shortcut", general)
            shortcut_layout = QVBoxLayout(shortcut_group)
            shortcut_help = QLabel("Use KDE Shortcuts to open the standalone Power User Menu with Meta+X.", shortcut_group)
            shortcut_help.setWordWrap(True)
            shortcut_layout.addWidget(shortcut_help)
            shortcut_button = QPushButton("Set up Meta+X…", shortcut_group)
            shortcut_button.setObjectName("setupMenuShortcut")
            shortcut_button.clicked.connect(self.setup_shortcut)
            shortcut_layout.addWidget(shortcut_button, 0, Qt.AlignLeft)
            general_layout.addWidget(shortcut_group)

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
                "<b>Organize your Power User Menu</b>"
                "<ul style='margin-top:4px; margin-bottom:0px'>"
                "<li><b>Add</b> an application, built-in action or custom command.</li>"
                "<li><b>Drag</b> entries to reorder or move them into submenus.</li>"
                "<li><b>Edit, duplicate or remove</b> the selected entry.</li>"
                "<li><b>Save</b> when finished.</li></ul>", layout_tab)
            layout_help.setObjectName("layoutInstructions")
            layout_help.setTextFormat(Qt.RichText)
            layout_help.setAccessibleName("Organize your Power User Menu. Add an entry. Drag to reorder or move into a submenu. Edit, duplicate or remove the selected entry. Save when finished.")
            layout_help.setWordWrap(True)
            layout_root.addWidget(layout_help)
            self.tree = MenuTree(self, layout_tab)
            self.tree.setObjectName("menuLayoutTree")
            self.tree.setColumnCount(3)
            self.tree.setHeaderLabels(["Menu item", "Type", "Runs on this computer"])
            self.tree.setAccessibleName("Power User Menu layout")
            self.tree.setTextElideMode(Qt.ElideMiddle)
            self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
            self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            self.tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
            self.tree.setColumnWidth(1, 135)
            self.tree.setAlternatingRowColors(True)
            self.tree.setSelectionMode(QTreeWidget.SingleSelection)
            self.tree.itemDoubleClicked.connect(lambda item, column: self.edit_selected())
            layout_root.addWidget(self.tree, 1)
            editing_buttons = []
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
            editing_buttons.append(self.add_button)
            self.edit_buttons = {}
            for label, callback in (("Edit", self.edit_selected), ("Remove", self.remove_selected), ("Duplicate", self.duplicate_selected),
                                    ("Move up", lambda: self.move_selected(-1)),
                                    ("Move down", lambda: self.move_selected(1))):
                b = QPushButton(label, layout_tab)
                b.clicked.connect(callback)
                editing_buttons.append(b)
                self.edit_buttons[label] = b
            history_buttons = []
            self.undo_action = self.undo_stack.createUndoAction(self, "Undo")
            self.undo_action.setShortcuts(QKeySequence.Undo)
            self.redo_action = self.undo_stack.createRedoAction(self, "Redo")
            self.redo_action.setShortcuts([QKeySequence("Ctrl+Shift+Z"), QKeySequence("Ctrl+Y")])
            self.undo_action.setToolTip("Undo layout change (Ctrl+Z)")
            self.redo_action.setToolTip("Redo layout change (Ctrl+Shift+Z or Ctrl+Y)")
            for action in (self.undo_action, self.redo_action):
                self.addAction(action)
                button = QToolButton(layout_tab)
                button.setDefaultAction(action)
                button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
                history_buttons.append(button)
            self.undo_action.setIcon(QIcon.fromTheme("edit-undo"))
            self.redo_action.setIcon(QIcon.fromTheme("edit-redo"))
            self.toolbar = EditorToolbar(editing_buttons, history_buttons, layout_tab)
            layout_root.addWidget(self.toolbar)
            self.context_actions = {}
            for label, callback, shortcut in (("Edit", self.edit_selected, "F2"),
                    ("Duplicate", self.duplicate_selected, "Ctrl+D"),
                    ("Remove", self.remove_selected, "Delete"),
                    ("Move up", lambda: self.move_selected(-1), "Alt+Up"),
                    ("Move down", lambda: self.move_selected(1), "Alt+Down"),
                    ("Move into previous submenu", self.indent_selected, "Alt+Right"),
                    ("Move out of submenu", self.outdent_selected, "Alt+Left")):
                action = QAction(label, self.tree)
                action.triggered.connect(callback)
                action.setShortcut(QKeySequence(shortcut))
                action.setShortcutContext(Qt.WidgetShortcut)
                self.tree.addAction(action)
                self.context_actions[label] = action
                if label in self.edit_buttons:
                    self.edit_buttons[label].setToolTip(f"{label} ({shortcut})")
            self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
            self.tree.customContextMenuRequested.connect(self.context_menu)

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
                "Nothing is written until you select Save. Right-click an entry for keyboard shortcuts.",
                layout_tab)
            layout_note.setWordWrap(True)
            layout_root.addWidget(layout_note)
            tabs.addTab(layout_tab, "Layout")

            # BACKUPS: configuration history and separate installation snapshots.
            backups_tab = QWidget(tabs)
            backups_tab.setObjectName("backupsTab")
            backups_layout = QVBoxLayout(backups_tab)
            backups_group = QGroupBox("Configuration backups", backups_tab)
            backups_form = QFormLayout(backups_group)
            self.backup_retention = QSpinBox(backups_group)
            self.backup_retention.setObjectName("backupRetentionSpin")
            self.backup_retention.setRange(0, 1000)
            self.backup_retention.setValue(cfg.get("backup_retention", DEFAULT_CONFIG["backup_retention"]))
            self.backup_retention.setSpecialValueText("Off (no new backups)")
            self.backup_retention.setToolTip(
                "Number of previous menu.json versions to keep. Default: 10. "
                "Setting 0 stops creating automatic backups without deleting existing ones.")
            backups_form.addRow("Previous versions to keep:", self.backup_retention)
            backups_help = QLabel(
                "Restore an earlier configuration when you need it. "
                "Default: 10 backups. Set 0 to stop new automatic backups; existing copies remain.", backups_group)
            backups_help.setWordWrap(True)
            backups_form.addRow(backups_help)
            manage = QPushButton("Manage / Restore Backups…", backups_group)
            manage.setObjectName("manageBackupsButton")
            manage.clicked.connect(self.manage_backups)
            backups_form.addRow(manage)
            backups_layout.addWidget(backups_group)

            snapshot_group = QGroupBox("Widget upgrade snapshots", backups_tab)
            snapshot_layout = QVBoxLayout(snapshot_group)
            snapshot_help = QLabel("Previous widget files are kept separately during upgrades. "
                                   "Default: 5 snapshots. Uninstall preserves them.", snapshot_group)
            snapshot_help.setWordWrap(True)
            snapshot_layout.addWidget(snapshot_help)
            self.snapshot_location = QLabel(snapshot_group)
            self.snapshot_location.setObjectName("widgetSnapshotLocation")
            self.snapshot_location.setTextFormat(Qt.PlainText)
            self.snapshot_location.setWordWrap(True)
            self.snapshot_location.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            snapshot_layout.addWidget(self.snapshot_location)
            self.refresh_snapshots()
            snapshot_setting = QLabel("Choose the limit when installing: OPM_WIDGET_BACKUP_RETENTION=5 bash install.sh", snapshot_group)
            snapshot_setting.setWordWrap(True)
            snapshot_setting.setToolTip("Installer setting: 1–1,000. It is separate from configuration backup retention. See the recovery guide to restore a widget and its matching backend.")
            snapshot_layout.addWidget(snapshot_setting)
            backups_layout.addWidget(snapshot_group)
            backups_layout.addStretch(1)
            backups_scroll = QScrollArea(tabs)
            backups_scroll.setWidgetResizable(True)
            backups_scroll.setFrameShape(QFrame.NoFrame)
            backups_scroll.setWidget(backups_tab)
            tabs.addTab(backups_scroll, "Backups")
            tabs.currentChanged.connect(lambda index: self.refresh_snapshots()
                                        if tabs.widget(index) is backups_scroll else None)

            buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            self.dirty_label = QLabel(self)
            root.addWidget(self.dirty_label)
            root.addWidget(buttons)
            self.fill(cfg["menu"])
            self._last_layout = self.capture_layout()
            self.tree.itemSelectionChanged.connect(self.update_actions)
            self.undo_stack.indexChanged.connect(self.update_dirty)
            for control in (self.appearance, self.launcher_target, self.icon_mode):
                control.currentIndexChanged.connect(self.update_dirty)
            self.hide_launcher.toggled.connect(self.update_dirty)
            self.button_icon.textChanged.connect(self.update_dirty)
            self.backup_retention.valueChanged.connect(self.update_dirty)
            self.show_missing.toggled.connect(self.unavailable_changed)
            self.update_dirty()
            self.update_actions()

        def refresh_snapshots(self):
            import os
            from .widget_snapshots import recovery_path, snapshot_count
            data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
            try:
                count = snapshot_count(data_home)
                status = f"{count} generated snapshots available." if count else "No widget snapshots yet."
            except OSError:
                status = "Snapshot directory is unavailable."
            self.snapshot_location.setText(f"{recovery_path(data_home)}\n{status}")

        def setup_shortcut(self):
            from .shortcut_setup import create_shortcut_dialog
            create_shortcut_dialog(self).exec()

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
            item.setToolTip(0, label)
            item.setFlags(item.flags() | Qt.ItemIsDragEnabled)
            if kind != "Submenu":
                item.setFlags(item.flags() & ~Qt.ItemIsDropEnabled)
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
            before = self.capture_layout()
            parent, index = self._container_for_add()
            item = self._make_item(entry)
            parent.insertChild(index, item)
            parent.setExpanded(True)
            self.tree.setCurrentItem(item)
            self.record_layout(before, "Add entry")

        def edit_selected(self):
            selected = self._selected()
            if not selected:
                return
            original = self.entry_data(selected)
            if kind_of(original) == "Separator":
                return
            dialog = EditEntryDialog(original, self)
            if dialog.exec() != QDialog.Accepted:
                return
            before = self.capture_layout()
            updated = dialog.result_entry
            selected.setData(0, Qt.UserRole, updated)
            label, kind, icon = details(updated)
            selected.setText(0, label)
            selected.setText(1, kind)
            selected.setText(2, preview_command(updated))
            selected.setToolTip(2, preview_command(updated))
            selected.setIcon(0, icon_for(icon))
            selected.setToolTip(0, label)
            self.record_layout(before, "Edit entry")

        def remove_selected(self):
            selected = self._selected()
            if selected is None:
                return
            before = self.capture_layout()
            parent = selected.parent() or self.tree.invisibleRootItem()
            index = parent.indexOfChild(selected)
            parent.takeChild(index)
            self.tree.setCurrentItem(parent.child(min(index, parent.childCount()-1)) if parent.childCount()
                                     else parent if parent is not self.tree.invisibleRootItem() else None)
            self.record_layout(before, "Remove entry")

        def move_selected(self, delta: int):
            selected = self._selected()
            if not selected:
                return
            parent = selected.parent() or self.tree.invisibleRootItem()
            index = parent.indexOfChild(selected)
            destination = index + delta
            if destination < 0 or destination >= parent.childCount():
                return
            self.relocate(selected, parent, destination if delta < 0 else destination + 1)

        def _walk(self, parent):
            entries = []
            for index in range(parent.childCount()):
                item = parent.child(index)
                data = self.entry_data(item)
                entries.append(data)
            return entries

        def indent_selected(self):
            selected = self._selected()
            if selected is None:
                return
            parent = selected.parent() or self.tree.invisibleRootItem()
            index = parent.indexOfChild(selected)
            previous = parent.child(index - 1) if index > 0 else None
            if previous is not None and 'submenu' in previous.data(0, Qt.UserRole):
                self.relocate(selected, previous, previous.childCount())

        def outdent_selected(self):
            selected = self._selected()
            if selected is None or selected.parent() is None:
                return
            parent = selected.parent()
            grandparent = parent.parent() or self.tree.invisibleRootItem()
            self.relocate(selected, grandparent, grandparent.indexOfChild(parent) + 1)

        def restore_defaults(self):
            if QMessageBox.question(self, "Restore defaults", "Replace the unsaved Power User Menu layout with standard defaults?\nGeneral settings will stay as they are. Nothing changes on disk until Save.") != QMessageBox.Yes:
                return
            before = self.capture_layout()
            self._applying = True
            self.fill(DEFAULT_CONFIG["menu"])
            self.show_missing.setChecked(DEFAULT_CONFIG["show_unavailable"])
            self._applying = False
            self.record_layout(before, "Restore default layout")
            # Reset applies to the Layout tab only; General settings remain untouched.

        def entry_data(self, item):
            data = deepcopy(item.data(0, Qt.UserRole))
            if 'submenu' in data:
                data['items'] = self._walk(item)
            return data

        def path_for(self, item):
            path = []
            while item is not None:
                parent = item.parent() or self.tree.invisibleRootItem()
                path.append(parent.indexOfChild(item))
                item = item.parent()
            return tuple(reversed(path))

        def item_for(self, path):
            item = self.tree.invisibleRootItem()
            for index in path:
                item = item.child(index) if item is not None else None
            return item if path else None

        def capture_layout(self):
            expanded = []
            def visit(parent, path=()):
                for i in range(parent.childCount()):
                    child = parent.child(i)
                    if child.isExpanded():
                        expanded.append(path + (i,))
                    visit(child, path + (i,))
            visit(self.tree.invisibleRootItem())
            return {'menu': self._walk(self.tree.invisibleRootItem()),
                    'show_unavailable': self.show_missing.isChecked(),
                    'selected': self.path_for(self.tree.currentItem()),
                    'expanded': expanded, 'scroll': self.tree.verticalScrollBar().value()}

        def apply_layout(self, state):
            self._applying = True
            try:
                self.fill(state['menu'])
                self.tree.collapseAll()
                for path in state['expanded']:
                    item = self.item_for(path)
                    if item:
                        item.setExpanded(True)
                self.tree.setCurrentItem(self.item_for(state['selected']))
                self.show_missing.setChecked(state['show_unavailable'])
                self.tree.verticalScrollBar().setValue(state['scroll'])
            finally:
                self._applying = False
            self._last_layout = self.capture_layout()
            self.update_actions()
            self.update_dirty()

        def record_layout(self, before, label):
            after = self.capture_layout()
            try:
                validate_menu_definition(after['menu'])
            except ValueError as exc:
                self.apply_layout(before)
                QMessageBox.warning(self, 'Cannot change layout', str(exc))
                return False
            if any(before[key] != after[key] for key in ('menu', 'show_unavailable')):
                self.undo_stack.push(LayoutChange(self, before, after, label))
            self._last_layout = after
            self.update_dirty()
            self.update_actions()
            return True

        def unavailable_changed(self):
            if not self._applying:
                before = self.capture_layout()
                before['show_unavailable'] = self._last_layout['show_unavailable']
                self.record_layout(before, 'Show unavailable entries')

        def relocate(self, source, parent, index):
            ancestor = parent
            while ancestor is not None:
                if ancestor is source:
                    return False
                ancestor = ancestor.parent()
            root = self.tree.invisibleRootItem()
            if parent is not root and 'submenu' not in parent.data(0, Qt.UserRole):
                return False
            if not 0 <= index <= parent.childCount():
                return False
            previous = source.parent() or root
            old_index = previous.indexOfChild(source)
            if old_index < 0:
                return False
            if parent is previous and index > old_index:
                index -= 1
            if parent is previous and index == old_index:
                return False
            before = self.capture_layout()
            previous.takeChild(old_index)
            parent.insertChild(index, source)
            if parent is not root:
                parent.setExpanded(True)
            self.tree.setCurrentItem(source)
            return self.record_layout(before, 'Move entry')

        def duplicate_selected(self):
            selected = self.tree.currentItem()
            if selected is None:
                return
            before = self.capture_layout()
            parent = selected.parent() or self.tree.invisibleRootItem()
            duplicate = self._make_item(self.entry_data(selected))
            parent.insertChild(parent.indexOfChild(selected) + 1, duplicate)
            self.tree.setCurrentItem(duplicate)
            self.record_layout(before, 'Duplicate entry')

        def update_actions(self):
            if not hasattr(self, 'edit_buttons'):
                return
            selected = self.tree.currentItem()
            parent = (selected.parent() or self.tree.invisibleRootItem()) if selected else None
            index = parent.indexOfChild(selected) if parent else -1
            states = {'Edit': selected is not None and not selected.data(0, Qt.UserRole).get('separator'),
                      'Remove': selected is not None, 'Duplicate': selected is not None,
                      'Move up': index > 0, 'Move down': parent is not None and index + 1 < parent.childCount(),
                      'Move into previous submenu': index > 0 and 'submenu' in parent.child(index - 1).data(0, Qt.UserRole),
                      'Move out of submenu': selected is not None and selected.parent() is not None}
            for name, enabled in states.items():
                if name in self.edit_buttons:
                    self.edit_buttons[name].setEnabled(enabled)
                if name in self.context_actions:
                    self.context_actions[name].setEnabled(enabled)

        def context_menu(self, position):
            item = self.tree.itemAt(position)
            if item:
                self.tree.setCurrentItem(item)
            menu = QMenu(self.tree)
            for action in self.context_actions.values():
                menu.addAction(action)
            menu.addSeparator()
            menu.addAction(self.undo_action)
            menu.addAction(self.redo_action)
            menu.exec(self.tree.viewport().mapToGlobal(position))

        def configuration(self):
            config = deepcopy(self.cfg)
            config['menu'] = self._walk(self.tree.invisibleRootItem())
            config['show_unavailable'] = self.show_missing.isChecked()
            config['appearance'] = self.appearance.currentData()
            config['hide_original_launcher'] = self.hide_launcher.isChecked()
            config['launcher_applet_id'] = int(self.launcher_target.currentData())
            config['button_icon_mode'] = self.icon_mode.currentData()
            config['button_icon'] = self.button_icon.text().strip()
            config['backup_retention'] = self.backup_retention.value()
            return config

        def is_dirty(self):
            return self.configuration() != self.saved_config

        def update_dirty(self):
            if self._applying or not hasattr(self, 'dirty_label'):
                return
            dirty = self.is_dirty()
            self.setWindowModified(dirty)
            self.dirty_label.setText('Unsaved changes' if dirty else 'No unsaved changes')

        def load_state(self, config, revision):
            self._applying = True
            try:
                self.cfg = deepcopy(config)
                self.saved_config = deepcopy(config)
                self.revision = revision
                self.fill(config['menu'])
                self.show_missing.setChecked(config['show_unavailable'])
                self.hide_launcher.setChecked(config['hide_original_launcher'])
                for widget, key in ((self.appearance, 'appearance'), (self.icon_mode, 'button_icon_mode'),
                                    (self.launcher_target, 'launcher_applet_id')):
                    index = widget.findData(config[key])
                    if index < 0:
                        widget.addItem(f"Saved widget #{config[key]}", config[key])
                        index = widget.count() - 1
                    widget.setCurrentIndex(index)
                self.button_icon.setText(config['button_icon'])
                self.backup_retention.setValue(config['backup_retention'])
                self.undo_stack.clear()
                self._last_layout = self.capture_layout()
            finally:
                self._applying = False
            self.update_actions()
            self.update_dirty()

        def confirm_discard(self, operation):
            return not self.is_dirty() or QMessageBox.question(self, operation,
                'Discard the unsaved editor changes before continuing?',
                QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Discard

        def reload_external(self):
            if not self.confirm_discard('Reload configuration'):
                return False
            try:
                revision = current_revision(self.target)
                config = decode_configuration(revision.content)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, 'Could not reload', str(exc))
                return False
            self.load_state(config, revision)
            return True

        def conflict_choice(self):
            message = QMessageBox(QMessageBox.Warning, 'Configuration changed elsewhere',
                'Another editor or tool changed menu.json. Keep editing, reload the newer file, '
                'or overwrite it after keeping a separate recovery copy.', parent=self)
            keep = message.addButton('Keep editing', QMessageBox.RejectRole)
            reload_button = message.addButton('Reload…', QMessageBox.ActionRole)
            overwrite = message.addButton('Overwrite with recovery copy', QMessageBox.DestructiveRole)
            message.setDefaultButton(keep)
            message.exec()
            return 'reload' if message.clickedButton() is reload_button else 'overwrite' if message.clickedButton() is overwrite else 'cancel'

        def accept(self):
            config = self.configuration()
            try:
                validate_configuration(config)
                try:
                    saved = save_config(config, self.target, expected_revision=self.revision)
                except ConfigurationConflict:
                    current = current_revision(self.target)
                    decision = self.conflict_choice()
                    if decision == 'reload':
                        self.reload_external()
                        return False
                    if decision != 'overwrite':
                        return False
                    saved = save_config(config, self.target, expected_revision=current, recovery_reason='overwrite')
            except (ValueError, OSError) as exc:
                if isinstance(exc, MenuValidationError):
                    self.tabs.setCurrentIndex(1)
                    self.tree.setCurrentItem(self.item_for(exc.path))
                    self.tree.setFocus()
                elif 'button_icon' in str(exc) or 'icon' in str(exc).lower():
                    self.tabs.setCurrentIndex(0)
                    self.button_icon.setFocus()
                QMessageBox.critical(self, 'Could not save menu', str(exc))
                return False
            self.saved_path = saved
            self.saved_config = deepcopy(config)
            self._closing = True
            super().accept()
            return True

        def reject(self):
            if self.is_dirty():
                choice = QMessageBox.question(self, 'Unsaved changes', 'Save your changes before closing?',
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
                if choice == QMessageBox.Save:
                    self.accept()
                    return
                if choice != QMessageBox.Discard:
                    return
            self._closing = True
            super().reject()

        def closeEvent(self, event):
            if not self._closing:
                self.reject()
            event.accept() if self._closing else event.ignore()

        def manage_backups(self):
            from .backup_dialog import BackupDialog
            def ready_to_restore():
                if not self.is_dirty():
                    return True
                QMessageBox.warning(self, 'Unsaved changes',
                    'Save or discard your editor changes and reopen Configure before restoring a backup. You can still preview backups now.')
                return False
            dialog = BackupDialog(self.target, self, before_restore=ready_to_restore)
            dialog.exec()
            if dialog.restored:
                try:
                    revision = current_revision(self.target)
                    config = decode_configuration(revision.content)
                    self.load_state(config, revision)
                except (OSError, ValueError) as exc:
                    QMessageBox.warning(self, 'Could not refresh configuration', str(exc))

    dialog = MenuEditor(config)
    dialog.application = app
    return dialog


def launch_editor() -> int:
    try:
        dialog = create_editor()
    except ImportError:
        return 2
    except (ValueError, OSError) as exc:
        from PySide6.QtWidgets import QApplication, QMessageBox
        from .backup_dialog import BackupDialog
        app = QApplication.instance() or QApplication(sys.argv[:1])
        if QMessageBox.question(None, "Invalid configuration", f"{exc}\n\nOpen configuration backups to recover?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return 2
        recovery = BackupDialog(config_path())
        recovery.exec()
        if not recovery.restored:
            return 2
        return launch_editor()
    dialog.exec()
    return 0
