import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Controls.Dialog {
    id: dialog
    objectName: "entryDialog"
    title: itemId ? "Edit menu entry" : "Add menu entry"
    modal: true
    width: Math.min(660, parent ? parent.width - 32 : 660)
    height: Math.min(600, parent ? parent.height - 32 : 600)
    anchors.centerIn: parent
    standardButtons: Controls.Dialog.NoButton
    property string itemId: ""
    property string parentId: ""
    property string entryKind: "command"
    property var original: ({})
    property var session
    property var catalog
    property string problem: ""
    property string desktopFile: ""
    property var pickedCommand: []
    property int powerRevision: 0
    property var builtin: (powerRevision, entryKind === "builtin" && actionField.currentIndex >= 0 ? catalog.builtinDetails(catalog.actions[actionField.currentIndex].id) : ({}))
    signal chooseApplication
    Connections {
        target: dialog.catalog
        function onPowerChanged() {
            dialog.powerRevision++;
        }
    }
    function setCommand(argv) {
        programField.text = argv[0] || "";
        argumentModel.clear();
        argv.slice(1).forEach(value => argumentModel.append({
                value: value
            }));
    }
    function useApplication(item) {
        entryKind = "command";
        nameField.text = item.label;
        iconField.text = item.icon;
        desktopFile = item.desktop_file;
        pickedCommand = item.command;
        setCommand(item.command);
    }
    function customizeBuiltin() {
        const details = builtin;
        if (!nameField.text.trim())
            nameField.text = details.title;
        if (!iconField.text.trim())
            iconField.text = details.icon;
        setCommand(details.command);
        desktopFile = "";
        entryKind = "command";
    }
    function begin(kind, id, container) {
        itemId = id || "";
        parentId = container || "";
        entryKind = kind;
        original = itemId ? JSON.parse(session.itemFields(itemId)) : {};
        desktopFile = original.desktop_file || "";
        pickedCommand = original.command || [];
        if (itemId)
            entryKind = original.kind;
        nameField.text = entryKind === "submenu" ? (original.submenu || "New submenu") : (original.label || "");
        iconField.text = original.icon || "";
        accessKeyField.text = original.access_key || "";
        actionField.currentIndex = Math.max(0, catalog.actions.findIndex(row => row.id === (original.action || "terminal")));
        const argv = original.command || [""];
        programField.text = argv[0] || "";
        argumentModel.clear();
        argv.slice(1).forEach(value => argumentModel.append({
                value: value
            }));
        problem = "";
        open();
    }
    function submit() {
        let changes = {};
        if (entryKind === "separator")
            changes = {
                separator: true
            };
        else if (entryKind === "submenu")
            changes = {
                submenu: nameField.text.trim(),
                icon: iconField.text.trim()
            };
        else if (entryKind === "builtin")
            changes = {
                action: catalog.actions[actionField.currentIndex].id,
                label: nameField.text.trim(),
                icon: iconField.text.trim()
            };
        else {
            const argv = [programField.text];
            for (let i = 0; i < argumentModel.count; ++i)
                argv.push(argumentModel.get(i).value);
            if (!nameField.text.trim()) {
                problem = "Give this entry a name.";
                nameField.forceActiveFocus();
                return;
            }
            changes = {
                label: nameField.text.trim(),
                icon: iconField.text.trim(),
                command: argv
            };
            if (desktopFile && desktopFile !== (original.desktop_file || "") && JSON.stringify(argv) === JSON.stringify(pickedCommand))
                changes.desktop_file = desktopFile;
        }
        if (entryKind !== "separator") changes.access_key = accessKeyField.text.trim().toUpperCase();
        if (itemId) {
            for (const key of Object.keys(changes))
                if (JSON.stringify(changes[key]) === JSON.stringify(original[key]))
                    delete changes[key];
        }
        const ok = itemId ? session.editItem(itemId, JSON.stringify(changes)) : session.addItem(parentId, "", JSON.stringify(changes));
        if (ok)
            close();
        else
            problem = session.error;
    }
    ListModel {
        id: argumentModel
    }
    contentItem: Controls.ScrollView {
        clip: true
        Controls.ScrollBar.vertical.policy: Controls.ScrollBar.AsNeeded
        Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AlwaysOff
        contentWidth: availableWidth
        ColumnLayout {
            width: parent.width
            spacing: 10
            Controls.Label {
                text: dialog.problem
                visible: text.length > 0
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                color: "#da4453"
            }
            Controls.Label {
                text: "Built-in action"
                visible: dialog.entryKind === "builtin"
            }
            Controls.ComboBox {
                id: actionField
                objectName: "entryAction"
                visible: dialog.entryKind === "builtin"
                model: dialog.catalog.actions
                textRole: "title"
                Layout.fillWidth: true
            }
            Controls.Label {
                visible: dialog.entryKind === "builtin"
                text: "Runs on this PC: " + (dialog.builtin.effective || "")
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Controls.TextArea {
                objectName: "builtinFallbacks"
                visible: dialog.entryKind === "builtin"
                text: dialog.builtin.candidates || ""
                readOnly: true
                selectByMouse: true
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                Accessible.name: "Fallback order"
            }
            Controls.Button {
                objectName: "customizeBuiltin"
                enabled: !dialog.builtin.native_power
                visible: dialog.entryKind === "builtin"
                text: "Customize this command…"
                onClicked: dialog.customizeBuiltin()
            }
            Controls.Label {
                text: dialog.entryKind === "builtin" ? "Name (leave empty to use the action's name)" : "Name"
                visible: dialog.entryKind !== "separator"
            }
            Controls.TextField {
                id: nameField
                objectName: "entryName"
                visible: dialog.entryKind !== "separator"
                Layout.fillWidth: true
                Accessible.name: "Menu entry name"
            }
            Controls.Label {
                text: "Theme icon or local image path"
                visible: dialog.entryKind !== "separator"
            }
            Controls.TextField {
                id: iconField
                objectName: "entryIcon"
                visible: dialog.entryKind !== "separator"
                Layout.fillWidth: true
                Accessible.name: "Menu entry icon"
            }
            Controls.Label { text: "Access key (A–Z or 0–9; empty disables this entry)"; visible: dialog.entryKind !== "separator" }
            Controls.TextField {
                id: accessKeyField
                objectName: "entryAccessKey"
                visible: dialog.entryKind !== "separator"
                maximumLength: 1
                validator: RegularExpressionValidator { regularExpression: /[A-Za-z0-9]?/ }
                Accessible.name: "Entry access key"
            }
            Controls.Label {
                text: "Program"
                visible: dialog.entryKind === "command"
            }
            Controls.TextField {
                id: programField
                objectName: "entryProgram"
                visible: dialog.entryKind === "command"
                Layout.fillWidth: true
                Accessible.name: "Program to run"
            }
            RowLayout {
                visible: dialog.entryKind === "command"
                Controls.Button {
                    text: "Choose installed application…"
                    onClicked: dialog.chooseApplication()
                }
                Controls.Button {
                    text: "Browse executable…"
                    onClicked: executablePicker.open()
                }
            }
            Controls.Label {
                visible: dialog.entryKind === "command" && !!dialog.desktopFile
                text: "Selected application: " + dialog.desktopFile
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Controls.Label {
                visible: dialog.entryKind === "command"
                text: "Each field below is one argument. Spaces stay within that argument; nothing is interpreted by a shell."
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Controls.Label {
                visible: dialog.entryKind === "command" && !!dialog.original.alternatives
                text: "This entry has alternative commands. They stay intact unless you change the program or arguments."
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Repeater {
                model: dialog.entryKind === "command" ? argumentModel : null
                RowLayout {
                    required property int index
                    required property string value
                    Layout.fillWidth: true
                    Controls.TextField {
                        text: value
                        Layout.fillWidth: true
                        Accessible.name: "Argument " + (index + 1)
                        onTextEdited: argumentModel.setProperty(index, "value", text)
                    }
                    Controls.Button {
                        text: "Remove"
                        onClicked: argumentModel.remove(index)
                    }
                }
            }
            Controls.Button {
                text: "Add argument"
                visible: dialog.entryKind === "command"
                onClicked: argumentModel.append({
                    value: ""
                })
            }
        }
    }
    footer: Controls.DialogButtonBox {
        Controls.Button {
            text: "Apply"
            objectName: "applyEntry"
            Controls.DialogButtonBox.buttonRole: Controls.DialogButtonBox.ActionRole
            onClicked: dialog.submit()
        }
        Controls.Button {
            text: "Cancel"
            Controls.DialogButtonBox.buttonRole: Controls.DialogButtonBox.RejectRole
            onClicked: dialog.close()
        }
    }
    FileDialog {
        id: executablePicker
        title: "Choose executable"
        onAccepted: programField.text = dialog.catalog.localFile(selectedFile)
    }
}
