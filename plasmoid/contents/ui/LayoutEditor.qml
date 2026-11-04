// Rearrangement only: no command payloads, launch signals or direct file access.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import "LayoutDraft.js" as Draft

QQC2.Control {
    id: control
    objectName: "inMenuLayoutEditor"
    property var draft: null
    property bool busy: false
    property bool expired: false
    readonly property var rows: draft ? (Draft.children(draft.entries, draft.parentId) || []) : []
    readonly property int selectedIndex: draft ? rows.findIndex(entry => entry.id === draft.selectedId) : -1
    property string draggedId: ""
    property bool dragActive: false
    property bool dragCanceled: false
    property string dropRow: ""
    property bool dropBelow: false
    signal edited(var value)
    signal failed(string message)
    signal saveRequested()
    signal cancelRequested()
    signal closeRequested()
    implicitHeight: 356
    implicitWidth: 304
    focusPolicy: Qt.StrongFocus
    Accessible.name: "Power User Menu layout editing. Commands are inactive."

    function choose(id) {
        edited(Draft.select(draft, draft.parentId, id));
    }
    function move(id, parentId, beforeId) {
        if (busy || expired) return;
        try { edited(Draft.move(draft, id, parentId, beforeId)); }
        catch (e) { failed(String(e.message)); }
    }
    function reorder(direction) {
        const index = selectedIndex;
        if (index < 0 || index + direction < 0 || index + direction >= rows.length) return;
        const before = direction < 0 ? rows[index - 1].id : (rows[index + 2] ? rows[index + 2].id : "");
        move(draft.selectedId, draft.parentId, before);
    }
    function outdent() {
        if (!draft.parentId || selectedIndex < 0) return;
        const parent = Draft.find(draft.entries, draft.parentId);
        const sibling = parent.container[parent.index + 1];
        move(draft.selectedId, parent.parentId, sibling ? sibling.id : "");
    }
    function enter(id) {
        const children = Draft.children(draft.entries, id);
        if (children) edited(Draft.select(draft, id, children.length ? children[0].id : ""));
    }
    function back() {
        if (!draft || !draft.parentId) return;
        const parent = Draft.find(draft.entries, draft.parentId);
        edited(Draft.select(draft, parent.parentId, parent.entry.id));
    }
    function cancelDrag() {
        dragCanceled = true;
        dragActive = false;
        draggedId = "";
        dropRow = "";
    }
    function handleKey(event) {
        if (!draft || busy) return;
        const alt = (event.modifiers & Qt.AltModifier) !== 0;
        if (event.key === Qt.Key_Escape) {
            if (dragActive) cancelDrag();
            else if (draft.parentId) back();
            else closeRequested(); // Popup dismissal retains the draft.
        } else if (event.key === Qt.Key_Up || event.key === Qt.Key_Down) {
            const direction = event.key === Qt.Key_Up ? -1 : 1;
            if (alt) reorder(direction);
            else {
                const index = Draft.nextIndex(rows, selectedIndex, direction, true);
                if (index >= 0) { choose(rows[index].id); list.positionViewAtIndex(index, ListView.Contain); }
            }
        } else if (event.key === Qt.Key_Left) {
            if (alt) outdent(); else back();
        } else if (event.key === Qt.Key_Right || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (selectedIndex >= 0 && rows[selectedIndex].kind === "submenu") enter(rows[selectedIndex].id);
        } else return;
        event.accepted = true;
    }
    Keys.onPressed: event => handleKey(event)
    onDraftChanged: {
        if (!draft) cancelDrag();
    }
    onVisibleChanged: if (!visible) cancelDrag()

    contentItem: ColumnLayout {
        spacing: 4
        RowLayout {
            Layout.fillWidth: true
            QQC2.ToolButton {
                objectName: "layoutBack"
                text: "Back"
                icon.name: "go-previous"
                enabled: !!control.draft && !!control.draft.parentId && !control.busy
                onClicked: control.back()
                Accessible.name: "Back to parent menu"
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: "Parent menu (Left)"
            }
            QQC2.Label {
                Layout.fillWidth: true
                text: control.draft && control.draft.parentId ? Draft.find(control.draft.entries, control.draft.parentId).entry.title : "Top level"
                elide: Text.ElideMiddle
                font.bold: true
            }
        }
        QQC2.Label {
            Layout.fillWidth: true
            text: "Drag the handles to reorder. Open a submenu to arrange its entries."
            wrapMode: Text.WordWrap
        }
        ListView {
            id: list
            objectName: "layoutRows"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: control.rows
            interactive: !control.dragActive
            boundsBehavior: Flickable.StopAtBounds
            QQC2.ScrollBar.vertical: QQC2.ScrollBar {}
            delegate: QQC2.ItemDelegate {
                id: row
                required property var modelData
                required property int index
                property var entry: modelData
                objectName: "layoutRow-" + entry.id
                width: list.width
                height: 36
                leftPadding: 34
                rightPadding: 30
                text: entry.title
                highlighted: control.draft && entry.id === control.draft.selectedId
                enabled: !control.busy
                Accessible.name: entry.title + (entry.kind === "submenu" ? ", submenu" : ", rearrange only")
                onClicked: {
                    control.choose(entry.id);
                    control.forceActiveFocus();
                    if (entry.kind === "submenu") control.enter(entry.id);
                }
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: entry.title
                QQC2.Label {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.rightMargin: 12
                    text: row.entry.kind === "submenu" ? "›" : ""
                }
                QQC2.Label {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: 30
                    horizontalAlignment: Text.AlignHCenter
                    text: "≡"
                    Accessible.name: "Drag " + row.entry.title
                    MouseArea {
                        anchors.fill: parent
                        enabled: !control.busy && !control.expired
                        preventStealing: true
                        drag.target: dragProxy
                        drag.axis: Drag.YAxis
                        drag.smoothed: false
                        onPressed: mouse => {
                            control.dragCanceled = false;
                            control.draggedId = row.entry.id;
                            const point = mapToItem(control, mouse.x, mouse.y);
                            dragProxy.x = point.x - 8;
                            dragProxy.y = point.y - 18;
                            control.choose(row.entry.id);
                            control.forceActiveFocus();
                        }
                        onPositionChanged: if (drag.active && !control.dragCanceled) control.dragActive = true
                        onReleased: {
                            // Dropping rebuilds the model and can destroy this delegate.
                            const editor = control;
                            if (editor.dragActive && !editor.dragCanceled) dragProxy.Drag.drop();
                            editor.cancelDrag();
                        }
                        onCanceled: control.cancelDrag()
                    }
                }
                DropArea {
                    anchors.fill: parent
                    keys: ["opm-layout"]
                    onEntered: drag => {
                        if (drag.source !== dragProxy) { drag.accepted = false; return; }
                        control.dropRow = row.entry.id;
                        control.dropBelow = drag.y >= height / 2;
                    }
                    onPositionChanged: drag => control.dropBelow = drag.y >= height / 2
                    onExited: if (control.dropRow === row.entry.id) control.dropRow = ""
                    onDropped: drop => {
                        if (drop.source !== dragProxy || !control.draggedId) return;
                        const next = control.rows[row.index + 1];
                        const before = control.dropBelow ? (next ? next.id : "") : row.entry.id;
                        control.move(control.draggedId, control.draft.parentId, before);
                        drop.acceptProposedAction();
                    }
                }
                Rectangle {
                    width: parent.width
                    height: 2
                    y: control.dropBelow ? parent.height - height : 0
                    color: control.palette.highlight
                    visible: control.dragActive && control.dropRow === row.entry.id
                }
            }
            footer: Item {
                width: list.width
                height: list.count ? 24 : Math.max(32, list.height)
                QQC2.Label {
                    anchors.centerIn: parent
                    text: control.dragActive ? "Drop at end" : list.count ? "" : "Empty submenu"
                }
                DropArea {
                    anchors.fill: parent
                    keys: ["opm-layout"]
                    onDropped: drop => {
                        if (drop.source !== dragProxy || !control.draggedId) return;
                        control.move(control.draggedId, control.draft.parentId, "");
                        drop.acceptProposedAction();
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            QQC2.ToolButton {
                objectName: "layoutUp"
                text: "Up"
                icon.name: "go-up"
                enabled: control.selectedIndex > 0 && !control.busy && !control.expired
                onClicked: control.reorder(-1)
                Accessible.name: "Move selected entry up (Alt+Up)"
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: "Move up (Alt+Up)"
            }
            QQC2.ToolButton {
                objectName: "layoutDown"
                text: "Down"
                icon.name: "go-down"
                enabled: control.selectedIndex >= 0 && control.selectedIndex < control.rows.length - 1 && !control.busy && !control.expired
                onClicked: control.reorder(1)
                Accessible.name: "Move selected entry down (Alt+Down)"
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: "Move down (Alt+Down)"
            }
            Item { Layout.fillWidth: true }
            QQC2.ToolButton {
                objectName: "layoutOut"
                text: "Move out"
                enabled: !!control.draft && !!control.draft.parentId && control.selectedIndex >= 0 && !control.busy && !control.expired
                onClicked: control.outdent()
                Accessible.name: "Move out of submenu (Alt+Left)"
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: "Move out (Alt+Left)"
            }
        }
        RowLayout {
            Layout.fillWidth: true
            QQC2.ComboBox {
                id: destination
                objectName: "layoutDestination"
                Layout.fillWidth: true
                model: control.rows.filter(entry => entry.kind === "submenu" && (!control.draft || entry.id !== control.draft.selectedId))
                textRole: "title"
                valueRole: "id"
                Accessible.name: "Destination submenu"
                enabled: control.selectedIndex >= 0 && count > 0 && !control.busy && !control.expired
            }
            QQC2.Button {
                objectName: "layoutMoveInto"
                text: "Move into"
                enabled: destination.enabled && destination.currentIndex >= 0
                onClicked: control.move(control.draft.selectedId, destination.currentValue, "")
            }
        }
        RowLayout {
            Layout.fillWidth: true
            QQC2.Button {
                objectName: "saveLayout"
                text: "Save layout"
                enabled: !!control.draft && !control.busy && !control.expired
                onClicked: control.saveRequested()
            }
            Item { Layout.fillWidth: true }
            QQC2.Button {
                objectName: "cancelLayout"
                text: "Cancel"
                enabled: !control.busy
                onClicked: control.cancelRequested()
            }
        }
    }
    Rectangle {
        id: dragProxy
        width: control.width - 30
        height: 36
        z: 100
        visible: control.dragActive
        color: control.palette.highlight
        opacity: 0.85
        radius: 3
        Drag.active: control.dragActive
        Drag.source: dragProxy
        Drag.keys: ["opm-layout"]
        Drag.supportedActions: Qt.MoveAction
        Drag.hotSpot.x: 8
        Drag.hotSpot.y: 18
        QQC2.Label {
            anchors.fill: parent
            anchors.margins: 6
            color: control.palette.highlightedText
            text: control.draft && control.draggedId ? Draft.find(control.draft.entries, control.draggedId).entry.title : ""
            elide: Text.ElideRight
        }
    }
    Timer {
        interval: 70
        repeat: true
        running: control.dragActive
        onTriggered: {
            const y = dragProxy.mapToItem(list, 0, 18).y;
            if (y < 24) list.contentY = Math.max(list.originY, list.contentY - 12);
            else if (y > list.height - 24)
                list.contentY = Math.min(list.originY + Math.max(0, list.contentHeight - list.height), list.contentY + 12);
        }
    }
}
