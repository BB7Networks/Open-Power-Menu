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
    // The adjacent editor pane is not a second native window: Wayland keeps
    // the entire drag inside the one, existing Plasma popup.
    property string flyoutId: ""
    readonly property bool flyoutVisible: !!draft && !!flyoutId &&
        !!Draft.find(draft.entries, flyoutId) &&
        Draft.find(draft.entries, flyoutId).parentId === draft.parentId
    readonly property var flyoutEntries: flyoutVisible ? (Draft.children(draft.entries, flyoutId) || []) : []
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
    implicitWidth: flyoutVisible ? 606 : 304
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
        flyoutId = "";
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
            // Keep both panes open when the drop crosses the visible boundary.
            // Only data references are saved; this is purely visual navigation.
            if (flyoutVisible && (parentId === flyoutId || parentId === draft.parentId))
                next.parentId = draft.parentId;
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
    function openFlyout(id) {
        if (!draft) return;
        const found = Draft.find(draft.entries, id);
        if (!found || found.entry.kind !== "submenu") return;
        if (found.parentId === draft.parentId) {
            flyoutId = id;
        } else if (flyoutVisible && found.parentId === flyoutId) {
            // Advance one step deeper while keeping its parent in the left pane.
            navigate(flyoutId, id);
            flyoutId = id;
        } else {
            navigate(found.parentId, id);
            flyoutId = id;
        }
    }
    function enter(id) {
        const children = Draft.children(draft.entries, id);
        if (children) navigate(id, children.length ? children[0].id : "");
    }
    function back() {
        if (flyoutVisible) { flyoutId = ""; return; }
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
    function containsPointer(pane, x, y) {
        if (!pane.visible) return false;
        const point = rowPointer.mapToItem(pane, x, y);
        return point.x >= 0 && point.y >= 0 &&
               point.x < pane.width && point.y < pane.height;
    }
    function pointerPane(x, y) {
        if (flyoutVisible && containsPointer(flyoutList, x, y)) {
            const point = rowPointer.mapToItem(flyoutList, x, y);
            if (point.x < flyoutList.width - (flyoutScrollBar.visible ? flyoutScrollBar.width : 0))
                return {list: flyoutList, parentId: flyoutId, entries: flyoutEntries};
        }
        if (containsPointer(list, x, y)) {
            const point = rowPointer.mapToItem(list, x, y);
            if (point.x < list.width - (layoutScrollBar.visible ? layoutScrollBar.width : 0))
                return {list: list, parentId: draft.parentId, entries: rows};
        }
        return null;
    }
    function rowUnderPointer(x, y) {
        const pane = pointerPane(x, y);
        if (!pane) return null;
        const point = rowPointer.mapToItem(pane.list.contentItem, x, y);
        const index = pane.list.indexAt(point.x, point.y);
        return index >= 0 && index < pane.entries.length ?
            {entry: pane.entries[index], parentId: pane.parentId} : null;
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
        const pane = pointerPane(rowPointer.mouseX, rowPointer.mouseY);
        if (!pane) { clearTarget(); return; }
        const point = rowPointer.mapToItem(pane.list.contentItem, rowPointer.mouseX, rowPointer.mouseY);
        const index = pane.list.indexAt(point.x, point.y);
        if (index < 0) { target("end:" + pane.parentId, "end", pane.parentId, "", false); return; }
        const row = pane.list.itemAtIndex(index);
        if (!row) { clearTarget(); return; }
        const entry = pane.entries[index];
        const y = point.y - row.y;
        if (entry.kind === "submenu" && y >= row.height * .25 && y < row.height * .75) {
            target(entry.id, "inside", entry.id, "", true);
        } else {
            dropBelow = y >= row.height / 2;
            const next = pane.entries[index + 1];
            target(entry.id, dropBelow ? "after" : "before", pane.parentId,
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
    function scrollDuringDrag(wheel) {
        if (!dragActive || dragCanceled) { wheel.accepted = false; return; }
        // ListView is deliberately noninteractive while we own the drag grab.
        // Qt deltas already incorporate the device's natural-scroll setting.
        // Pixel deltas preserve smooth touchpad motion; a wheel notch moves
        // three 36px rows. Consume even at bounds so the outer popup stays put.
        const delta = wheel.pixelDelta.y || wheel.angleDelta.y / 120 * 108;
        if (Number.isFinite(delta) && delta !== 0) {
            const pane = pointerPane(rowPointer.mouseX, rowPointer.mouseY);
            const view = pane ? pane.list : list;
            view.contentY = Math.max(view.originY, Math.min(view.contentY - delta,
                view.originY + Math.max(0, view.contentHeight - view.height)));
            view.forceLayout();
            updateDragTarget();
        }
        wheel.accepted = true;
    }
    function showMoves(x, y) {
        if (!draft || selectedIndex < 0 || busy || expired || dragActive) return;
        movesMenu.popup(x, y);
    }
    function showDestinations() {
        if (!draft || selectedIndex < 0 || busy || expired || dragActive || destinations.count === 0) return;
        movesMenu.close();
        destinationMenu.popup(12, navigationBar.height);
    }
    function handleKey(event) {
        if (!draft || busy) return;
        const alt = (event.modifiers & Qt.AltModifier) !== 0;
        if (event.key === Qt.Key_Menu || (event.key === Qt.Key_F10 && (event.modifiers & Qt.ShiftModifier))) {
            showMoves(12, navigationBar.height);
        } else if (event.key === Qt.Key_Right && alt) {
            showDestinations();
        } else if (event.key === Qt.Key_Escape) {
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
        syncView();
        // Closing or reparenting a submenu must never leave a stale target.
        if (!draft || (flyoutId && !flyoutVisible)) flyoutId = "";
    }
    Component.onCompleted: { viewReady = true; syncView(); }
    onVisibleChanged: {
        if (!visible) { rememberView(); cancelDrag(); movesMenu.close(); destinationMenu.close(); }
        else if (viewReady && draft) Qt.callLater(() => restoreView(false));
    }

    QQC2.Menu {
        id: movesMenu
        objectName: "layoutMovementMenu"
        parent: control
        QQC2.MenuItem {
            text: "Move up (Alt+Up)"
            enabled: control.selectedIndex > 0 && !control.busy && !control.expired
            onTriggered: control.reorder(-1)
        }
        QQC2.MenuItem {
            text: "Move down (Alt+Down)"
            enabled: control.selectedIndex >= 0 && control.selectedIndex < control.rows.length - 1 && !control.busy && !control.expired
            onTriggered: control.reorder(1)
        }
        QQC2.MenuItem {
            text: "Move out (Alt+Left)"
            enabled: !!control.draft && !!control.draft.parentId && control.selectedIndex >= 0 && !control.busy && !control.expired
            onTriggered: control.outdent()
        }
        QQC2.MenuItem {
            text: "Move into submenu… (Alt+Right)"
            enabled: destinations.count > 0 && !control.busy && !control.expired
            onTriggered: control.showDestinations()
        }
        onClosed: if (control.visible) control.forceActiveFocus()
    }
    QQC2.Menu {
        id: destinationMenu
        objectName: "layoutDestinationMenu"
        parent: control
        title: "Move into submenu"
        Instantiator {
            id: destinations
            model: control.rows.filter(entry => entry.kind === "submenu" && (!control.draft || entry.id !== control.draft.selectedId))
            delegate: QQC2.MenuItem {
                required property var modelData
                text: modelData.title
                enabled: !!control.draft && !control.busy && !control.expired &&
                         Draft.moveError(control.draft, control.draft.selectedId, modelData.id, "").length === 0
                onTriggered: {
                    const target = modelData.id;
                    destinationMenu.close();
                    control.move(control.draft.selectedId, target, "");
                }
            }
            onObjectAdded: (index, object) => destinationMenu.insertItem(index, object)
            onObjectRemoved: (index, object) => destinationMenu.removeItem(object)
        }
        onClosed: if (control.visible) control.forceActiveFocus()
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
            text: "Drag between the menu and its flyout. Hover to open a submenu; Back moves up."
            wrapMode: Text.WordWrap
        }
        RowLayout {
            id: cascadingEditorRow
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 5
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
                    visible: control.dragActive && control.dropKind === "end" &&
                             control.dropParent === control.draft.parentId
                }
            }
        }
        QQC2.Frame {
            id: flyoutPane
            objectName: "layoutCascadingPane"
            visible: control.flyoutVisible
            Layout.preferredWidth: Math.min(292, Math.max(200, control.width * .48))
            Layout.fillHeight: true
            padding: 5
            background: Rectangle {
                color: control.palette.window
                border.color: control.palette.mid
                radius: 4
            }
            contentItem: ColumnLayout {
                spacing: 4
                QQC2.Label {
                    Layout.fillWidth: true
                    font.bold: true
                    text: control.flyoutVisible ? Draft.find(control.draft.entries, control.flyoutId).entry.title : ""
                    elide: Text.ElideMiddle
                    Accessible.name: "Open submenu"
                }
                ListView {
                    id: flyoutList
                    objectName: "layoutFlyoutRows"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: control.flyoutEntries
                    interactive: !control.dragActive
                    boundsBehavior: Flickable.StopAtBounds
                    QQC2.ScrollBar.vertical: QQC2.ScrollBar { id: flyoutScrollBar }
                    onModelChanged: Qt.callLater(() => {
                        if (!control.flyoutVisible) return;
                        const saved = Draft.view(control.draft, control.flyoutId);
                        if (saved) contentY = Math.max(originY, Math.min(originY + saved.position,
                            originY + Math.max(0, contentHeight - height)));
                    })
                    onContentYChanged: {
                        if (!control.flyoutVisible || !control.draft || control.restoringView) return;
                        const saved = Draft.view(control.draft, control.flyoutId) || {};
                        Draft.rememberView(control.draft, control.flyoutId, {
                            anchorId: saved.anchorId || "",
                            offset: 0, position: contentY - originY,
                            selectedId: saved.selectedId || ""
                        });
                    }
                    delegate: QQC2.ItemDelegate {
                        id: childRow
                        required property var modelData
                        required property int index
                        property var entry: modelData
                        objectName: "layoutFlyoutRow-" + entry.id
                        width: flyoutList.width
                        height: 36
                        text: entry.title
                        highlighted: control.draft && entry.id === control.draft.selectedId
                        enabled: !control.busy
                        Accessible.name: entry.title + (entry.kind === "submenu" ? ", submenu" : ", rearrange only")
                        QQC2.Label {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.rightMargin: 9
                            text: childRow.entry.kind === "submenu" ? "›" : ""
                        }
                        Rectangle {
                            width: parent.width
                            height: control.dropKind === "inside" ? parent.height : 2
                            y: control.dropKind !== "inside" && control.dropBelow ? parent.height - height : 0
                            color: control.dropValid ? control.palette.highlight : "#da4453"
                            opacity: control.dropKind === "inside" ? .25 : 1
                            visible: control.dragActive && control.dropRow === childRow.entry.id
                        }
                    }
                    footer: Item {
                        width: flyoutList.width
                        height: flyoutList.count ? 24 : Math.max(32, flyoutList.height)
                        QQC2.Label {
                            anchors.centerIn: parent
                            text: control.dragActive ? "Drop at end" : flyoutList.count ? "" : "Empty submenu"
                        }
                        Rectangle {
                            width: parent.width
                            height: 2
                            color: control.dropValid ? control.palette.highlight : "#da4453"
                            visible: control.dragActive && control.dropKind === "end" &&
                                     control.dropParent === control.flyoutId
                        }
                    }
                }
            }
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
        property string pressedParent: ""
        property bool suppressClick: false
        preventStealing: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        drag.target: (pressedButtons & Qt.LeftButton) ? dragPosition : null
        drag.smoothed: false
        onPressed: mouse => {
            const hit = control.rowUnderPointer(mouse.x, mouse.y);
            if (!hit) { mouse.accepted = false; return; }
            pressedId = hit.entry.id;
            pressedParent = hit.parentId;
            control.choose(pressedId);
            control.forceActiveFocus();
            if (mouse.button === Qt.RightButton) return;
            suppressClick = false;
            control.dragCanceled = false;
            control.draggedId = pressedId;
            control.dragOriginParent = pressedParent;
            dragPosition.x = mouse.x - 8;
            dragPosition.y = mouse.y - 18;
        }
        onPositionChanged: {
            if (drag.active && !control.dragCanceled) {
                control.dragActive = true;
                control.updateDragTarget();
            }
        }
        onReleased: mouse => {
            if (mouse.button === Qt.RightButton) return;
            suppressClick = control.dragActive || control.dragCanceled;
            control.updateDragTarget();
            const accepted = control.dragActive && !control.dragCanceled && control.dropValid;
            if (accepted) control.move(control.draggedId, control.dropParent, control.dropBefore);
            control.cancelDrag(!accepted);
        }
        onClicked: mouse => {
            if (mouse.button === Qt.RightButton) {
                if (pressedParent !== control.draft.parentId)
                    control.navigate(pressedParent, pressedId);
                control.showMoves(mouse.x, mouse.y); return;
            }
            if (suppressClick || !control.draft) return;
            const entry = Draft.find(control.draft.entries, pressedId);
            if (entry && entry.entry.kind === "submenu") control.openFlyout(pressedId);
            else if (pressedParent !== control.draft.parentId)
                control.navigate(pressedParent, pressedId);
        }
        onCanceled: { suppressClick = true; control.cancelDrag(); }
        onWheel: wheel => control.scrollDuringDrag(wheel)
    }
    Item { id: dragPosition }
    Rectangle {
        id: dragProxy
        objectName: "inMenuDragPreview"
        x: Math.max(0, Math.min(dragPosition.x, control.width - width))
        y: dragPosition.y
        width: Math.min(292, control.width - 30)
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
            if (control.dropKind === "parent") {
                control.navigate(parentId, "");
            } else {
                control.openFlyout(parentId);
            }
        }
    }
    Timer {
        interval: 70
        repeat: true
        running: control.dragActive
        onTriggered: {
            const pane = control.pointerPane(rowPointer.mouseX, rowPointer.mouseY);
            if (!pane) return;
            const view = pane.list;
            const point = rowPointer.mapToItem(view, rowPointer.mouseX, rowPointer.mouseY);
            if (point.y < 24) view.contentY = Math.max(view.originY, view.contentY - 12);
            else if (point.y > view.height - 24)
                view.contentY = Math.min(view.originY + Math.max(0, view.contentHeight - view.height), view.contentY + 12);
            control.updateDragTarget();
        }
    }
}
