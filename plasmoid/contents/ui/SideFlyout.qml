// SPDX-License-Identifier: MIT
// A reusable, launcher-independent Plasma-native cascading submenu.
// Anchor to a one-pixel proxy positioned from the active menu row, keeping
// right/left adaptive selection and a bottom-aligned, screen-clamped flyout.
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PC3

PlasmaCore.PopupPlasmaWindow {
    id: flyout
    visible: false
    popupDirection: Qt.RightEdge
    // CRITICAL: false widens the horizontal anchor to the ENTIRE parent
    // window (Plasma implementation), causing overlapping/misplaced flyouts.
    // true preserves the actual row's bounds; side selection happens below.
    floating: true
    margin: 0
    animated: false
    // Do not force Qt.Popup: that changes Wayland popup placement semantics.
    // PlasmaWindow already supplies its own frameless top-level flags.

    property var entries: []
    property var activeChild: null
    // The screen rectangle is provided by the Plasmoid, not inferred from
    // which edge the *panel* happens to occupy. This also handles multiple
    // monitors and non-corner launcher positions.
    property rect screenRect: Qt.rect(0, 0, 0, 0)
    signal triggered(string key)

    function chooseSide(anchor) {
        if (!anchor) return Qt.RightEdge;
        const point = anchor.mapToGlobal(0, 0);
        // Assigned from the visible parent row BEFORE showing this window.
        // Never calculate direction from this still-hidden flyout's Screen.
        if (screenRect.width <= 0 || !Number.isFinite(screenRect.width)) {
            console.warn("Open Power Menu: row screen geometry unavailable; defaulting right");
            return Qt.RightEdge;
        }
        const freeRight = screenRect.x + screenRect.width - (point.x + anchor.width);
        const freeLeft = point.x - screenRect.x;
        const required = width + 4;
        if (freeRight >= required) return Qt.RightEdge;
        if (freeLeft >= required) return Qt.LeftEdge;
        // Very narrow screens: prefer the side with more room.
        return freeRight >= freeLeft ? Qt.RightEdge : Qt.LeftEdge;
    }
    onEffectivePopupDirectionChanged: {
        if (visible) console.info("Open Power Menu: requested side",
            popupDirection === Qt.RightEdge ? "right" : "left",
            "effective side", effectivePopupDirection === Qt.RightEdge ? "right" :
                effectivePopupDirection === Qt.LeftEdge ? "left" : "other");
    }
    // Anchor side popups so their lower edge aligns with the parent item's
    // lower edge. Plasma centers RightEdge/LeftEdge popups on visualParent,
    // so a one-pixel-high proxy can be placed at the desired vertical center.
    // Keep the popup on its source screen even when the panel is on top/side.
    function positionAtRow(row, proxy, screen) {
        if (!row || !proxy) return;
        const rowGlobal = row.mapToGlobal(0, 0);
        const rowLocal = row.mapToItem(proxy.parent, 0, 0);
        const popupH = Math.max(1, height);
        const border = 4;
        const screenTop = screen.height > 0 ? screen.y + border : -100000;
        const screenBottom = screen.height > 0 ? screen.y + screen.height - border : 100000;
        const topLimit = Math.max(screenTop, screenBottom - popupH);
        // Prefer bottom-edge alignment; move down if that would run off top.
        const requestedTop = rowGlobal.y + row.height - popupH;
        const targetTop = Math.max(screenTop, Math.min(requestedTop, topLimit));
        proxy.x = rowLocal.x;
        proxy.y = rowLocal.y + targetTop + popupH / 2 - rowGlobal.y - 0.5;
        proxy.width = row.width;
        proxy.height = 1;
    }
    function rowsHeight(model) {
        let total = 8;
        for (const entry of model || [])
            total += entry.kind === "separator" ? 12 : 34;
        return Math.max(total, 40);
    }
    function closeChild() {
        if (activeChild) activeChild.visible = false;
        activeChild = null;
    }
    function showChild(child) {
        if (!child) return;
        if (activeChild && activeChild !== child)
            activeChild.visible = false;
        activeChild = child;
        child.visible = true;
    }
    onVisibleChanged: {
        if (!visible) closeChild();
    }

    // PlasmaWindow's mainItem is resized to the window's size minus its
    // theme padding. Set the window size, not mainItem's width or height.
    width: 260 + leftPadding + rightPadding
    height: Math.min(rowsHeight(entries), Math.max(180, Math.min(540,
        Screen.desktopAvailableHeight > 0 ? Screen.desktopAvailableHeight - 56 : 540)))
        + topPadding + bottomPadding

    mainItem: Rectangle {
        id: flyoutSurface
        color: "#27313D"
        border.color: "#53718A"
        border.width: 1
        radius: 3

        // Shared proxy for deeper cascading menus; each nested flyout is
        // positioned on the source row before it becomes visible.
        Item {
            id: childAnchor
            width: 1
            height: 1
        }

        QQC2.ScrollView {
            id: viewport
            anchors.fill: parent
            anchors.margins: 3
            clip: true
            contentWidth: availableWidth

            Column {
                id: column
                width: viewport.availableWidth
                spacing: 0
                Repeater {
                    model: flyout.entries
                    delegate: Item {
                        id: row
                        required property var modelData
                        property var entry: modelData
                        property var childPopup: null
                        readonly property rect menuScreen: Qt.rect(
                            Screen.virtualX, Screen.virtualY,
                            Screen.width, Screen.height)
                        width: column.width
                        height: entry.kind === "separator" ? 12 : 34

                        function openChild() {
                            if (row.entry.kind !== "submenu") return;
                            if (!childPopup) {
                                // Load deeper levels lazily. A static self-
                                // reference here would trigger recursive QML
                                // type-instantiation errors at compile time.
                                const factory = Qt.createComponent(Qt.resolvedUrl("SideFlyout.qml"));
                                if (factory.status !== Component.Ready) {
                                    console.warn("Open Power Menu nested flyout:", factory.errorString());
                                    return;
                                }
                                childPopup = factory.createObject(row, {
                                    "visualParent": childAnchor,
                                    "entries": row.entry.items || [],
                                    "screenRect": row.menuScreen
                                });
                                if (!childPopup) {
                                    console.warn("Open Power Menu: could not open nested flyout");
                                    return;
                                }
                                childPopup.triggered.connect(function(key) {
                                    flyout.triggered(key);
                                    flyout.visible = false;
                                });
                            }
                            childPopup.screenRect = row.menuScreen;
                            childPopup.positionAtRow(row, childAnchor, row.menuScreen);
                            childPopup.popupDirection = childPopup.chooseSide(childAnchor);
                            flyout.showChild(childPopup);
                        }
                        Component.onDestruction: {
                            if (childPopup) {
                                childPopup.visible = false;
                                childPopup.destroy();
                            }
                        }

                        Kirigami.Separator {
                            anchors.centerIn: parent
                            width: parent.width - 16
                            visible: row.entry.kind === "separator"
                        }
                        Rectangle {
                            anchors.fill: parent
                            anchors.leftMargin: 3
                            anchors.rightMargin: 3
                            radius: 2
                            color: Kirigami.Theme.highlightColor
                            opacity: (mouse.containsMouse && row.entry.kind !== "separator") ? 0.28 : 0
                        }
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 9
                            spacing: 8
                            visible: row.entry.kind !== "separator"
                            Kirigami.Icon {
                                source: row.entry.icon || "application-x-executable"
                                Layout.preferredWidth: 17
                                Layout.preferredHeight: 17
                            }
                            PC3.Label {
                                text: row.entry.title || ""
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                opacity: row.entry.enabled === false ? 0.5 : 1
                            }
                            Kirigami.Icon {
                                Layout.preferredWidth: 13
                                Layout.preferredHeight: 13
                                source: "go-next-symbolic"
                                visible: row.entry.kind === "submenu"
                            }
                        }
                        MouseArea {
                            id: mouse
                            anchors.fill: parent
                            hoverEnabled: true
                            enabled: row.entry.kind !== "separator" && row.entry.enabled !== false
                            onEntered: {
                                if (row.entry.kind === "submenu") row.openChild();
                                else flyout.closeChild();
                            }
                            onClicked: {
                                if (row.entry.kind === "submenu") row.openChild();
                                else {
                                    flyout.triggered(row.entry.key);
                                    flyout.visible = false;
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
