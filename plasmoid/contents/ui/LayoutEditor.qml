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
    property string dropKind: ""
    property bool dropValid: false
    property string dropReason: ""
    property string dropParent: ""
    property string dropBefore: ""
    property string hoverKey: ""
    property string hoverParent: ""
    property string dragOriginParent: ""
    property int submenuHoverDelay: 450
    property bool viewReady: false
    property bool restoringView: false
    property bool revealSelection: false
    property string displayedParent: ""
    property string displayedToken: ""
    property int viewEpoch: 0
    signal edited(var value)
    signal failed(string message)
    signal saveRequested()
    signal cancelRequested()
    signal closeRequested()
    implicitHeight: 356
    implicitWidth: 304
    focusPolicy: Qt.StrongFocus
    Accessible.name: "Power User Menu layout editing. Commands are inactive."

    ListModel { id: rowModel }
    function rowIndex(id) {
        for (let index = 0; index < rowModel.count; index++)
            if (rowModel.get(index).itemId === id) return index;
        return -1;
    }
    function rememberView() {
        if (!viewReady || restoringView || !draft || displayedToken !== draft.token
                || displayedParent !== draft.parentId) return;
        const index = list.indexAt(1, list.contentY + 1);
        const item = index >= 0 ? list.itemAtIndex(index) : null;
        Draft.rememberView(draft, displayedParent, {
            anchorId: item ? rowModel.get(index).itemId : "",
            offset: item ? item.y - list.contentY : 0,
            position: list.contentY - list.originY, selectedId: draft.selectedId
        });
    }
    function restoreView(reveal) {
        if (!draft) return;
        list.forceLayout();
        const saved = Draft.view(draft, draft.parentId);
        const anchor = saved ? rowIndex(saved.anchorId) : -1;
        let position = list.originY + (saved ? saved.position : 0);
        if (anchor >= 0) {
            list.positionViewAtIndex(anchor, ListView.Beginning);
            list.forceLayout();
            const item = list.itemAtIndex(anchor);
            if (item) position = item.y - saved.offset;
        }
        list.contentY = Math.max(list.originY, Math.min(position,
            list.originY + Math.max(0, list.contentHeight - list.height)));
        if (reveal && selectedIndex >= 0) list.positionViewAtIndex(selectedIndex, ListView.Contain);
    }
    function syncView() {
        if (!viewReady) return;
        if (!draft) {
            rowModel.clear(); displayedToken = ""; cancelDrag(); return;
        }
        const entries = Draft.children(draft.entries, draft.parentId) || [];
        const changedLevel = displayedToken !== draft.token || displayedParent !== draft.parentId;
        const changedRows = rowModel.count !== entries.length || entries.some((entry, index) =>
            index >= rowModel.count || rowModel.get(index).itemId !== entry.id);
        if (!changedLevel && !changedRows) { revealSelection = false; rememberView(); return; }
        restoringView = true;
        displayedToken = draft.token;
        displayedParent = draft.parentId;
        if (changedLevel) rowModel.clear();
        // Stable ListModel rows avoid resetting the view/delegates on each move.
        for (let index = 0; index < entries.length; index++) {
            const entry = entries[index];
            const existing = rowIndex(entry.id);
            if (existing < 0) rowModel.insert(index, {itemId: entry.id, itemTitle: entry.title, itemKind: entry.kind});
            else if (existing !== index) rowModel.move(existing, index, 1);
        }
        if (rowModel.count > entries.length) rowModel.remove(entries.length, rowModel.count - entries.length);
        const reveal = revealSelection;
        revealSelection = false;
        const epoch = ++viewEpoch;
        Qt.callLater(() => {
            if (epoch !== viewEpoch || !draft) return;
            restoreView(reveal);
            restoringView = false;
            rememberView();
            if (dragActive) updateDragTarget();
        });
    }
    function navigate(parentId, selectedId) {
        rememberView();
        edited(Draft.select(draft, parentId, Draft.selection(draft, parentId, selectedId)));
        if (visible) forceActiveFocus();
    }

    function choose(id) {
        edited(Draft.select(draft, draft.parentId, id));
    }
    function move(id, parentId, beforeId) {
        if (busy || expired) return;
        try {
            const next = Draft.move(draft, id, parentId, beforeId);
            rememberView();
            revealSelection = true;
            edited(next);
            if (visible) forceActiveFocus();
        }
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
        if (children) navigate(id, children.length ? children[0].id : "");
    }
    function back() {
        if (!draft || !draft.parentId) return;
        const parent = Draft.find(draft.entries, draft.parentId);
        navigate(parent.parentId, parent.entry.id);
    }
    function clearTarget() {
        dropRow = ""; dropKind = ""; dropValid = false; dropReason = "";
        hoverKey = "";
        springOpen.stop();
    }
    function target(row, kind, parentId, beforeId, hover) {
        dropRow = row;
        dropKind = kind;
        dropParent = parentId;
        dropBefore = beforeId;
        dropReason = Draft.moveError(draft, draggedId, parentId, beforeId);
        dropValid = dropReason.length === 0;
        // A full parent can still be traversed to reach another submenu.
        const key = hover && Draft.canEnter(draft, draggedId, parentId) ? kind + ":" + row : "";
        if (key !== hoverKey) {
            hoverKey = key;
            hoverParent = parentId;
            if (key) springOpen.restart(); else springOpen.stop();
        }
    }
    function updateDragTarget() {
        if (!dragActive || dragCanceled || !draft || restoringView) return;
        const backPoint = rowPointer.mapToItem(navigationBar, rowPointer.mouseX, rowPointer.mouseY);
        if (draft.parentId && backPoint.x >= 0 && backPoint.x < navigationBar.width
                && backPoint.y >= 0 && backPoint.y < navigationBar.height) {
            const parent = Draft.find(draft.entries, draft.parentId);
            const next = parent.container[parent.index + 1];
            target("parent:" + draft.parentId, "parent", parent.parentId, next ? next.id : "", true);
            return;
        }
        const point = rowPointer.mapToItem(list, rowPointer.mouseX, rowPointer.mouseY);
        if (point.x < 0 || point.x >= list.width - (layoutScrollBar.visible ? layoutScrollBar.width : 0)
                || point.y < 0 || point.y >= list.height) { clearTarget(); return; }
        const content = rowPointer.mapToItem(list.contentItem, rowPointer.mouseX, rowPointer.mouseY);
        const index = list.indexAt(content.x, content.y);
        if (index < 0) { target("end", "end", draft.parentId, "", false); return; }
        const row = list.itemAtIndex(index);
        if (!row) { clearTarget(); return; }
        const entry = rows[index];
        const y = content.y - row.y;
        if (entry.kind === "submenu" && y >= row.height * .25 && y < row.height * .75) {
            target(entry.id, "inside", entry.id, "", true);
        } else {
            dropBelow = y >= row.height / 2;
            const next = rows[index + 1];
            target(entry.id, dropBelow ? "after" : "before", draft.parentId,
                   dropBelow ? (next ? next.id : "") : entry.id, false);
        }
    }
    function cancelDrag(restoreOrigin) {
        const returnToOrigin = restoreOrigin !== false && dragActive && draft;
        dragCanceled = true;
        dragActive = false;
        clearTarget();
        if (returnToOrigin) navigate(dragOriginParent, draggedId);
        draggedId = "";
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
    onDraftChanged: syncView()
    Component.onCompleted: { viewReady = true; syncView(); }
    onVisibleChanged: {
        if (!visible) { rememberView(); cancelDrag(); }
        else if (viewReady && draft) Qt.callLater(() => restoreView(false));
    }

    contentItem: ColumnLayout {
        spacing: 4
        RowLayout {
            id: navigationBar
            Layout.fillWidth: true
            QQC2.ToolButton {
                objectName: "layoutBack"
                text: "Back"
                icon.name: "go-previous"
                icon.color: control.dragActive && control.dropKind === "parent" ? control.palette.highlight : control.palette.buttonText
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
                color: control.dragActive && control.dropKind === "parent" ? control.palette.highlight : control.palette.windowText
            }
        }
        QQC2.Label {
            Layout.fillWidth: true
            text: "Drag an entry. Pause over a submenu or Back to move between levels."
            wrapMode: Text.WordWrap
        }
        ListView {
            id: list
            objectName: "layoutRows"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: rowModel
            interactive: !control.dragActive
            onContentYChanged: control.rememberView()
            boundsBehavior: Flickable.StopAtBounds
            QQC2.ScrollBar.vertical: QQC2.ScrollBar { id: layoutScrollBar }
            delegate: QQC2.ItemDelegate {
                id: row
                required property string itemId
                required property string itemTitle
                required property string itemKind
                required property int index
                property var entry: ({id: itemId, title: itemTitle, kind: itemKind})
                objectName: "layoutRow-" + entry.id
                width: list.width
                height: 36
                leftPadding: 12
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
                Rectangle {
                    width: parent.width
                    height: control.dropKind === "inside" ? parent.height : 2
                    y: control.dropKind !== "inside" && control.dropBelow ? parent.height - height : 0
                    color: control.dropValid ? control.palette.highlight : "#da4453"
                    opacity: control.dropKind === "inside" ? .25 : 1
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
                Rectangle {
                    width: parent.width
                    height: 2
                    color: control.dropValid ? control.palette.highlight : "#da4453"
                    visible: control.dragActive && control.dropKind === "end"
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
    // One stable pointer owner survives row moves and submenu navigation. Qt's
    // native drag threshold distinguishes a click from movement; no hold delay.
    MouseArea {
        id: rowPointer
        anchors.fill: parent
        z: 50
        enabled: !control.busy && !control.expired
        property string pressedId: ""
        property bool suppressClick: false
        preventStealing: true
        drag.target: dragProxy
        drag.smoothed: false
        onPressed: mouse => {
            const point = mapToItem(list, mouse.x, mouse.y);
            const content = mapToItem(list.contentItem, mouse.x, mouse.y);
            const index = list.indexAt(content.x, content.y);
            if (point.x < 0 || point.y < 0 || point.y >= list.height || index < 0
                    || point.x >= list.width - (layoutScrollBar.visible ? layoutScrollBar.width : 0)) {
                mouse.accepted = false; return;
            }
            pressedId = rowModel.get(index).itemId;
            suppressClick = false;
            control.dragCanceled = false;
            control.draggedId = pressedId;
            control.dragOriginParent = control.draft.parentId;
            dragProxy.x = mouse.x - 8;
            dragProxy.y = mouse.y - 18;
            control.choose(pressedId);
            control.forceActiveFocus();
        }
        onPositionChanged: {
            if (drag.active && !control.dragCanceled) {
                control.dragActive = true;
                control.updateDragTarget();
            }
        }
        onReleased: {
            suppressClick = control.dragActive || control.dragCanceled;
            control.updateDragTarget();
            const accepted = control.dragActive && !control.dragCanceled && control.dropValid;
            if (accepted) control.move(control.draggedId, control.dropParent, control.dropBefore);
            control.cancelDrag(!accepted);
        }
        onClicked: {
            if (suppressClick || !control.draft) return;
            const entry = Draft.find(control.draft.entries, pressedId);
            if (entry && entry.entry.kind === "submenu") control.enter(pressedId);
        }
        onCanceled: { suppressClick = true; control.cancelDrag(); }
        onWheel: wheel => wheel.accepted = false
    }
    Rectangle {
        id: dragProxy
        width: control.width - 30
        height: 36
        z: 100
        visible: control.dragActive
        color: !control.dropValid ? "#da4453" : control.palette.highlight
        opacity: 0.85
        radius: 3
        QQC2.Label {
            anchors.fill: parent
            anchors.margins: 6
            color: control.palette.highlightedText
            text: !control.dropValid ? "Cannot drop here" : control.draft && control.draggedId ? Draft.find(control.draft.entries, control.draggedId).entry.title : ""
            elide: Text.ElideRight
        }
    }
    Timer {
        id: springOpen
        interval: control.submenuHoverDelay
        onTriggered: {
            if (!control.dragActive || !control.hoverKey) return;
            const parentId = control.hoverParent;
            control.clearTarget();
            control.navigate(parentId, "");
        }
    }
    Timer {
        interval: 70
        repeat: true
        running: control.dragActive
        onTriggered: {
            const point = rowPointer.mapToItem(list, rowPointer.mouseX, rowPointer.mouseY);
            if (point.x < 0 || point.x > list.width || point.y < 0 || point.y > list.height) return;
            if (point.y < 24) list.contentY = Math.max(list.originY, list.contentY - 12);
            else if (point.y > list.height - 24)
                list.contentY = Math.min(list.originY + Math.max(0, list.contentHeight - list.height), list.contentY + 12);
            control.updateDragTarget();
        }
    }
}
