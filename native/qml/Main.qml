import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import org.kde.kirigami as Kirigami
import "../shared" as Shared
import "../shared/LayoutDraft.js" as Draft

Kirigami.ApplicationWindow {
    id: window
    objectName: "nativeConfigure"
    width: 960
    height: 720
    minimumWidth: 620
    minimumHeight: 480
    visible: true
    title: "Open Power Menu — Configure" + (editorSession.dirty ? " *" : "")
    property bool closingApproved: false
    property var settings: JSON.parse(editorSession.settingsJson)
    property var layoutDraft: Draft.start(JSON.parse(editorSession.layoutJson))
    property var backupRows: JSON.parse(editorSession.backupsJson)
    property string localError: ""
    property bool invalidGeneral: false
    property string confirmAction: ""
    property var launcherRows: []
    function syncLaunchers() {
        let rows = Array.from(editorCatalog.launchers);
        if (!rows.some(row => row.id === settings.launcher_applet_id))
            rows.push({
                id: settings.launcher_applet_id,
                title: "Saved widget #" + settings.launcher_applet_id + " (not currently found)"
            });
        launcherRows = rows;
    }
    function syncLayout() {
        const update = JSON.parse(editorSession.layoutJson);
        let parentId = layoutDraft ? layoutDraft.parentId : "";
        if (parentId && !Draft.find(update.entries, parentId))
            parentId = "";
        const selected = layoutDraft ? layoutDraft.selectedId : "";
        const rows = Draft.children(update.entries, parentId) || [];
        layoutDraft = Object.assign({}, layoutDraft || Draft.start(update), {
            entries: update.entries,
            parentId: parentId,
            selectedId: Draft.find(update.entries, selected) ? selected : (rows.length ? rows[0].id : "")
        });
    }
    function preference(key, value) {
        const change = {};
        change[key] = value;
        editorSession.preference(JSON.stringify(change));
    }
    function confirm(action, title, message) {
        confirmAction = action;
        confirmation.title = title;
        confirmationText.text = message;
        confirmation.open();
    }
    function save(closeAfter) {
        if (invalidGeneral) {
            tabs.currentIndex = 0;
            buttonIconField.forceActiveFocus();
            return;
        }
        if (editorSession.save()) {
            if (closeAfter) {
                closingApproved = true;
                close();
            }
        } else if (editorSession.errorCode === "conflict" || editorSession.errorCode === "configuration")
            conflict.open();
    }
    function selectedFields() {
        return layoutDraft.selectedId ? JSON.parse(editorSession.itemFields(layoutDraft.selectedId)) : {};
    }
    function editSelected() {
        const field = selectedFields();
        if (field.kind && field.kind !== "separator")
            entryDialog.begin(field.kind, field.id, layoutDraft.parentId);
    }
    Component.onCompleted: syncLaunchers()
    onActiveChanged: if (active)
        editorSession.checkExternal()
    onClosing: event => {
        if (!closingApproved && editorSession.dirty) {
            event.accepted = false;
            unsaved.open();
        }
    }
    Connections {
        target: editorSession
        function onChanged() {
            window.syncLayout();
            window.syncLaunchers();
        }
        function onFocusItem(id) {
            const found = Draft.find(window.layoutDraft.entries, id);
            if (found) {
                window.layoutDraft = Draft.select(window.layoutDraft, found.parentId, id);
                Qt.callLater(() => layoutEditor.revealCurrent());
            }
        }
    }
    Connections {
        target: editorCatalog
        function onRefreshed() {
            window.syncLaunchers();
        }
    }
    Shortcut {
        sequences: [StandardKey.Undo]
        enabled: tabs.currentIndex === 1 && !entryDialog.opened
        onActivated: editorSession.undo()
    }
    Shortcut {
        sequences: [StandardKey.Redo, "Ctrl+Shift+Z"]
        enabled: tabs.currentIndex === 1 && !entryDialog.opened
        onActivated: editorSession.redo()
    }
    Shortcut {
        sequence: "F2"
        enabled: tabs.currentIndex === 1 && !entryDialog.opened
        onActivated: window.editSelected()
    }
    Shortcut {
        sequence: "Ctrl+D"
        enabled: tabs.currentIndex === 1 && !entryDialog.opened
        onActivated: editorSession.duplicateItem(window.layoutDraft.selectedId)
    }
    Timer {
        interval: 2000
        running: window.active
        repeat: true
        onTriggered: editorSession.checkExternal()
    }
    header: Controls.TabBar {
        id: tabs
        objectName: "configureTabs"
        Controls.TabButton {
            text: "General"
            objectName: "generalTab"
        }
        Controls.TabButton {
            text: "Layout"
            objectName: "layoutTab"
        }
        Controls.TabButton {
            text: "Backups"
            objectName: "backupsTab"
        }
        onCurrentIndexChanged: if (currentIndex === 2)
            editorSession.refreshBackups()
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: text.length > 0
            type: Kirigami.MessageType.Error
            text: window.localError || editorSession.error
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: editorSession.externalChanged
            type: Kirigami.MessageType.Warning
            text: "The configuration changed in another window. Your draft is retained. Save will offer recovery choices."
        }
        StackLayout {
            currentIndex: tabs.currentIndex
            Layout.fillWidth: true
            Layout.fillHeight: true
            Controls.ScrollView {
                Controls.ScrollBar.vertical.policy: Controls.ScrollBar.AsNeeded
                Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AlwaysOff
                clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    width: parent.width
                    spacing: 16
                    Controls.Label {
                        text: "Choose your launcher, Start button icon and menu style. Your launcher and favorites stay intact."
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                    Controls.GroupBox {
                        title: "Original launcher"
                        Layout.fillWidth: true
                        ColumnLayout {
                            anchors.fill: parent
                            Controls.ComboBox {
                                objectName: "launcherSelection"
                                model: window.launcherRows
                                textRole: "title"
                                Layout.fillWidth: true
                                currentIndex: Math.max(0, window.launcherRows.findIndex(row => row.id === window.settings.launcher_applet_id))
                                onActivated: index => window.preference("launcher_applet_id", window.launcherRows[index].id)
                            }
                            Controls.CheckBox {
                                text: "Hide the original launcher's panel button"
                                checked: window.settings.hide_original_launcher
                                onToggled: window.preference("hide_original_launcher", checked)
                            }
                            Controls.Label {
                                text: "Left-click opens your launcher; right-click opens Power User Menu. Hiding the original button is reversible."
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }
                            RowLayout {
                                Controls.Label {
                                    text: "Emergency restore"
                                    Layout.fillWidth: true
                                }
                                Controls.Button {
                                    text: "Copy command"
                                    onClicked: editorCatalog.copy("open-power-menu --show-launcher-button")
                                }
                            }
                            Controls.Label {
                                text: "open-power-menu --show-launcher-button"
                                font.family: "monospace"
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }
                        }
                    }
                    Controls.GroupBox {
                        title: "Start button icon"
                        Layout.fillWidth: true
                        ColumnLayout {
                            anchors.fill: parent
                            Controls.ComboBox {
                                model: ["Use original launcher icon", "Custom icon"]
                                Layout.fillWidth: true
                                currentIndex: window.settings.button_icon_mode === "custom" ? 1 : 0
                                onActivated: index => window.preference("button_icon_mode", index === 1 ? "custom" : "launcher")
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                enabled: window.settings.button_icon_mode === "custom"
                                Controls.TextField {
                                    id: buttonIconField
                                    text: window.settings.button_icon
                                    placeholderText: "Theme icon name or image path"
                                    Layout.fillWidth: true
                                    onEditingFinished: {
                                        window.invalidGeneral = !editorSession.preference(JSON.stringify({
                                            button_icon: text
                                        }));
                                        window.localError = window.invalidGeneral ? editorSession.error : "";
                                    }
                                }
                                Kirigami.Icon {
                                    source: window.settings.button_icon || "start-here-kde"
                                    implicitWidth: 32
                                    implicitHeight: 32
                                }
                                Controls.Button {
                                    text: "Browse…"
                                    onClicked: iconPicker.open()
                                }
                            }
                        }
                    }
                    Controls.GroupBox {
                        title: "Power User Menu appearance"
                        Layout.fillWidth: true
                        ColumnLayout {
                            anchors.fill: parent
                            Controls.ComboBox {
                                Layout.fillWidth: true
                                model: ["Use the desktop theme", "Dark Aero"]
                                currentIndex: window.settings.appearance === "aero" ? 1 : 0
                                onActivated: index => window.preference("appearance", index === 1 ? "aero" : "native")
                            }
                            Controls.CheckBox {
                                text: "Show icons in Power User Menu"
                                checked: window.settings.show_menu_icons
                                onToggled: window.preference("show_menu_icons", checked)
                            }
                            Controls.CheckBox {
                                text: "Automatically close when pointer leaves menu"
                                checked: window.settings.auto_close_on_pointer_leave
                                onToggled: window.preference("auto_close_on_pointer_leave", checked)
                            }
                            RowLayout {
                                enabled: window.settings.auto_close_on_pointer_leave
                                Controls.Label { text: "Close delay (seconds)" }
                                Controls.SpinBox {
                                    objectName: "closeDelay"
                                    from: 5; to: 50; stepSize: 1
                                    value: window.settings.auto_close_delay_ms / 100
                                    textFromValue: (value, locale) => Number(value / 10).toLocaleString(locale, 'f', 1)
                                    onValueModified: window.preference("auto_close_delay_ms", value * 100)
                                    Accessible.name: "Automatic-close delay in seconds"
                                }
                            }
                            Controls.CheckBox {
                                objectName: "accessKeysEnabled"
                                text: "Enable menu access keys"
                                checked: window.settings.access_keys_enabled
                                onToggled: window.preference("access_keys_enabled", checked)
                            }
                            Controls.CheckBox {
                                objectName: "accessKeyHints"
                                text: "Show access-key hints"
                                enabled: window.settings.access_keys_enabled
                                checked: window.settings.show_access_key_hints
                                onToggled: window.preference("show_access_key_hints", checked)
                            }
                            Controls.Label {
                                text: "Delay applies outside the menu and all flyouts. Keyboard navigation and editing keep it open."
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                Controls.Label {
                    text: "Add entries, drag to reorder or move into submenus, then Save. Use Go Back to move through the layout."
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 6
                    Controls.Button {
                        text: "Add…"
                        objectName: "addEntry"
                        onClicked: addMenu.popup()
                    }
                    Controls.Button {
                        text: "Edit"
                        objectName: "editEntry"
                        enabled: !!window.layoutDraft.selectedId && window.selectedFields().kind !== "separator"
                        onClicked: window.editSelected()
                    }
                    Controls.Button {
                        text: "Duplicate"
                        objectName: "duplicateEntry"
                        enabled: !!window.layoutDraft.selectedId
                        onClicked: editorSession.duplicateItem(window.layoutDraft.selectedId)
                    }
                    Controls.Button {
                        text: "Remove"
                        enabled: !!window.layoutDraft.selectedId
                        onClicked: window.confirm("remove", "Remove entry", "Remove this entry and any children? You can undo this before saving.")
                    }
                    Controls.Button {
                        text: "Undo"
                        objectName: "undoLayout"
                        enabled: editorSession.canUndo
                        onClicked: editorSession.undo()
                    }
                    Controls.Button {
                        text: "Redo"
                        objectName: "redoLayout"
                        enabled: editorSession.canRedo
                        onClicked: editorSession.redo()
                    }
                }
                Shared.LayoutEditor {
                    id: layoutEditor
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    showActions: false
                    draft: window.layoutDraft
                    onEdited: value => {
                        const changed = JSON.stringify(Draft.references(value.entries)) !== JSON.stringify(Draft.references(window.layoutDraft.entries));
                        if (!changed || editorSession.rearrange(JSON.stringify(Draft.references(value.entries))))
                            window.layoutDraft = value;
                        editorSession.selectItem(window.layoutDraft.selectedId);
                    }
                    onFailed: message => window.localError = message
                    onSaveRequested: window.save(false)
                    onCancelRequested: window.close()
                    onCloseRequested: window.close()
                }
                RowLayout {
                    Layout.fillWidth: true
                    Controls.CheckBox {
                        text: "Show unavailable commands in the menu"
                        checked: !!window.settings.show_unavailable
                        onToggled: window.preference("show_unavailable", checked)
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    Controls.Button {
                        text: "Reset access keys"
                        onClicked: editorSession.resetAccessKeys()
                        Controls.ToolTip.text: "Restore unambiguous OPM presets without changing the layout. Undo is available."
                        Controls.ToolTip.visible: hovered
                    }
                    Controls.Button {
                        text: "Restore default layout…"
                        onClicked: window.confirm("defaults", "Restore default layout", "Replace the menu layout and unavailable-entry option with their defaults? General settings and backups are preserved. You can undo this change.")
                    }
                }
            }
            ColumnLayout {
                RowLayout {
                    Controls.Label {
                        text: "Automatic configuration backups:"
                    }
                    Controls.SpinBox {
                        objectName: "backupRetention"
                        from: 0
                        to: 1000
                        editable: true
                        value: window.settings.backup_retention
                        onValueModified: window.preference("backup_retention", value)
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    Controls.Button {
                        text: "Refresh"
                        onClicked: {
                            editorSession.refreshBackups();
                            editorCatalog.refresh();
                        }
                    }
                }
                Controls.Label {
                    text: "Zero disables new automatic backups. Restore and explicit overwrite still keep protected recovery copies."
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Controls.SplitView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Controls.ScrollView {
                        Controls.ScrollBar.vertical.policy: Controls.ScrollBar.AsNeeded
                        Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AlwaysOff
                        Controls.SplitView.preferredWidth: 300
                        ListView {
                            id: history
                            objectName: "backupHistory"
                            clip: true
                            model: window.backupRows
                            delegate: Controls.ItemDelegate {
                                required property var modelData
                                objectName: "backupEntry:" + modelData.name
                                width: ListView.view.width
                                text: modelData.modified + (modelData.protectedCopy ? "  · Protected" : "") + "\n" + modelData.name + (modelData.valid ? "" : "\nCannot restore: " + modelData.error)
                                highlighted: modelData.name === editorSession.selectedBackupName
                                onClicked: editorSession.selectBackup(modelData.name)
                            }
                            Controls.Label {
                                anchors.centerIn: parent
                                visible: history.count === 0
                                text: "No configuration backups yet."
                            }
                        }
                    }
                    Controls.ScrollView {
                        Controls.ScrollBar.vertical.policy: Controls.ScrollBar.AsNeeded
                        Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AlwaysOff
                        Controls.SplitView.fillWidth: true
                        Controls.TextArea {
                            objectName: "backupPreview"
                            text: editorSession.backupPreview
                            readOnly: true
                            selectByMouse: true
                            wrapMode: Text.Wrap
                        }
                    }
                }
                RowLayout {
                    Controls.Button {
                        text: "Restore selected…"
                        objectName: "restoreBackup"
                        enabled: editorSession.canRestore
                        onClicked: window.confirm("restore", "Restore configuration backup", "Restore " + editorSession.selectedBackupName + "? The current file will be kept as a protected recovery copy." + (editorSession.dirty ? " Unsaved changes in this window will be discarded." : ""))
                    }
                    Controls.Button {
                        text: "Delete selected…"
                        objectName: "deleteBackup"
                        enabled: editorSession.canDeleteBackup
                        onClicked: window.confirm("delete", editorSession.selectedProtected ? "Delete protected recovery copy" : "Delete backup", "Permanently delete " + editorSession.selectedBackupName + "?" + (editorSession.selectedProtected ? " This is a protected recovery copy." : ""))
                    }
                }
                Controls.Label {
                    text: "Widget recovery\n" + editorCatalog.snapshotStatus
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Controls.Label {
                text: editorSession.dirty ? "Unsaved changes" : "No unsaved changes"
                Layout.fillWidth: true
            }
            Controls.Button {
                text: "Save"
                objectName: "saveConfiguration"
                onClicked: window.save(false)
            }
            Controls.Button {
                text: "Close"
                onClicked: window.close()
            }
        }
    }
    FileDialog {
        id: iconPicker
        title: "Choose Start button image"
        nameFilters: ["Images (*.png *.svg *.svgz *.jpg *.jpeg *.webp *.ico)"]
        onAccepted: window.preference("button_icon", selectedFile.toString())
    }
    EntryDialog {
        id: entryDialog
        session: editorSession
        catalog: editorCatalog
        parent: Controls.Overlay.overlay
        onChooseApplication: {
            applications.forEntry = true;
            editorCatalog.refresh();
            applications.open();
        }
    }
    Controls.Menu {
        id: addMenu
        Controls.MenuItem {
            text: "Installed application…"
            onTriggered: {
                applications.forEntry = false;
                editorCatalog.refresh();
                applications.open();
            }
        }
        Controls.MenuItem {
            text: "Built-in command…"
            onTriggered: entryDialog.begin("builtin", "", window.layoutDraft.parentId)
        }
        Controls.MenuItem {
            text: "Custom command…"
            onTriggered: entryDialog.begin("command", "", window.layoutDraft.parentId)
        }
        Controls.MenuItem {
            text: "Submenu…"
            onTriggered: entryDialog.begin("submenu", "", window.layoutDraft.parentId)
        }
        Controls.MenuItem {
            text: "Separator"
            onTriggered: editorSession.addItem(window.layoutDraft.parentId, "", JSON.stringify({
                separator: true
            }))
        }
    }
    Controls.Dialog {
        id: applications
        property bool forEntry: false
        objectName: "applicationPicker"
        title: "Choose an installed application"
        modal: true
        parent: Controls.Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(700, window.width - 40)
        height: Math.min(550, window.height - 40)
        standardButtons: Controls.Dialog.Close
        ColumnLayout {
            anchors.fill: parent
            Controls.TextField {
                id: appSearch
                objectName: "applicationSearch"
                Layout.fillWidth: true
                placeholderText: "Search applications"
                Accessible.name: "Search applications"
            }
            Controls.Label {
                id: appError
                text: ""
                visible: text.length > 0
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            ListView {
                objectName: "applicationList"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: Array.from(editorCatalog.applications).filter(row => (row.name + " " + row.genericName + " " + row.description).toLowerCase().includes(appSearch.text.toLowerCase()))
                delegate: Controls.ItemDelegate {
                    required property var modelData
                    objectName: "applicationEntry:" + modelData.id
                    width: ListView.view.width
                    text: modelData.name + (modelData.description ? " — " + modelData.description : "")
                    icon.name: modelData.icon
                    onClicked: {
                        const item = editorCatalog.applicationItem(modelData.id);
                        if (!item) {
                            appError.text = "The application is unavailable or the KDE desktop-file launcher is missing. Install the KDE command-line tools and refresh the list.";
                            return;
                        }
                        if (applications.forEntry) {
                            entryDialog.useApplication(JSON.parse(item));
                            applications.close();
                        } else if (editorSession.addItem(window.layoutDraft.parentId, "", item))
                            applications.close();
                        else
                            appError.text = editorSession.error;
                    }
                }
            }
        }
    }
    Controls.Dialog {
        id: confirmation
        objectName: "confirmationDialog"
        modal: true
        parent: Controls.Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(560, window.width - 40)
        standardButtons: Controls.Dialog.Yes | Controls.Dialog.Cancel
        Controls.Label {
            id: confirmationText
            textFormat: Text.PlainText
            width: parent.width
            wrapMode: Text.Wrap
        }
        onAccepted: {
            if (window.confirmAction === "remove")
                editorSession.removeItem(window.layoutDraft.selectedId);
            else if (window.confirmAction === "defaults")
                editorSession.resetLayout();
            else if (window.confirmAction === "restore")
                editorSession.restoreBackup(true);
            else if (window.confirmAction === "delete")
                editorSession.deleteBackup(editorSession.selectedProtected);
            else if (window.confirmAction === "reload")
                editorSession.reload(true);
        }
    }
    Controls.Dialog {
        id: unsaved
        title: "Unsaved changes"
        modal: true
        parent: Controls.Overlay.overlay
        anchors.centerIn: parent
        standardButtons: Controls.Dialog.NoButton
        ColumnLayout {
            Controls.Label {
                text: "Save your changes before closing?"
            }
            RowLayout {
                Controls.Button {
                    text: "Save"
                    onClicked: {
                        unsaved.close();
                        window.save(true);
                    }
                }
                Controls.Button {
                    text: "Discard"
                    onClicked: {
                        window.closingApproved = true;
                        window.close();
                    }
                }
                Controls.Button {
                    text: "Cancel"
                    onClicked: unsaved.close()
                }
            }
        }
    }
    Controls.Dialog {
        id: conflict
        title: "Configuration needs recovery"
        modal: true
        parent: Controls.Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(620, window.width - 40)
        standardButtons: Controls.Dialog.NoButton
        ColumnLayout {
            width: parent.width
            Controls.Label {
                text: editorSession.error
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Controls.Button {
                text: "Keep editing"
                onClicked: conflict.close()
            }
            Controls.Button {
                text: "Reload from disk…"
                onClicked: {
                    conflict.close();
                    window.confirm("reload", "Reload configuration", "Discard your draft and reload the current file?");
                }
            }
            Controls.Button {
                text: "Overwrite with a recovery copy…"
                onClicked: {
                    const preview = editorSession.prepareOverwrite();
                    if (preview) {
                        overwriteText.text = preview;
                        conflict.close();
                        overwrite.open();
                    }
                }
            }
        }
    }
    Controls.Dialog {
        id: overwrite
        title: "Overwrite current configuration"
        modal: true
        parent: Controls.Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(620, window.width - 40)
        height: Math.min(500, window.height - 40)
        standardButtons: Controls.Dialog.Yes | Controls.Dialog.Cancel
        Controls.ScrollView {
            Controls.ScrollBar.vertical.policy: Controls.ScrollBar.AsNeeded
            Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AlwaysOff
            anchors.fill: parent
            Controls.TextArea {
                id: overwriteText
                readOnly: true
                selectByMouse: true
                wrapMode: Text.Wrap
            }
        }
        onAccepted: editorSession.confirmOverwrite()
    }
}
