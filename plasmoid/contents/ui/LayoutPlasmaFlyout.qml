// SPDX-License-Identifier: MIT
// Plasma-native edit flyout. Uses the SAME visualParent/proxy positioning
// as the normal Power User Menu, not QtQuick.Controls.Popup.Window.
// Loaded dynamically only by the Plasma widget; Qt headless editor tests keep
// the separate non-Plasma fallback.
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore

PlasmaCore.PopupPlasmaWindow {
    id: flyout
    visible: !!editor && editor.visible && editor.flyoutVisible && editor.plasmaFlyoutActive
    floating: true
    margin: 0
    animated: false
    popupDirection: Qt.RightEdge

    property var editor: null
    property var entries: []
    property rect screenRect: Qt.rect(0, 0, 0, 0)

    // Keep the source row's bounds as the anchor. As with SideFlyout.qml,
    // the one-pixel proxy is shifted so the flyout's bottom is level with
    // the parent item's bottom, within the available screen.
    function positionAtRow(row, proxy, screen) {
        if (!row || !proxy) return;
        const rowGlobal = row.mapToGlobal(0, 0);
        const rowLocal = row.mapToItem(proxy.parent, 0, 0);
        const popupH = Math.max(1, height);
        const border = 4;
        const screenTop = screen.height > 0 ? screen.y + border : -100000;
        const screenBottom = screen.height > 0 ? screen.y + screen.height - border : 100000;
        const topLimit = Math.max(screenTop, screenBottom - popupH);
        const requestedTop = rowGlobal.y + row.height - popupH;
        const targetTop = Math.max(screenTop, Math.min(requestedTop, topLimit));
        proxy.x = rowLocal.x;
        proxy.y = rowLocal.y + targetTop + popupH / 2 - rowGlobal.y - 0.5;
        proxy.width = row.width;
        proxy.height = 1;
    }
    function chooseSide(anchor) {
        if (!anchor || screenRect.width <= 0) return Qt.RightEdge;
        const point = anchor.mapToGlobal(0, 0);
        const freeRight = screenRect.x + screenRect.width - (point.x + anchor.width);
        const freeLeft = point.x - screenRect.x;
        if (freeRight >= width + 4) return Qt.RightEdge;
        if (freeLeft >= width + 4) return Qt.LeftEdge;
        return freeRight >= freeLeft ? Qt.RightEdge : Qt.LeftEdge;
    }

    onVisibleChanged: {
        if (!visible && editor) editor.setFlyoutPointer(false);
    }

    width: 280 + leftPadding + rightPadding
    height: Math.max(72, Math.min(410, (entries.length * 36) + 94))
        + topPadding + bottomPadding

    mainItem: Rectangle {
        id: surface
        color: editor ? editor.palette.window : Kirigami.Theme.backgroundColor
        border.color: editor ? editor.palette.mid : Kirigami.Theme.textColor
        border.width: 1
        radius: 4
        focus: true

        HoverHandler {
            onHoveredChanged: if (flyout.editor) flyout.editor.setFlyoutPointer(hovered)
        }

        Keys.onPressed: event => {
            if (event.key === Qt.Key_Escape || event.key === Qt.Key_Left) {
                if (flyout.editor) flyout.editor.back();
                event.accepted = true;
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 6
            spacing: 3
            QQC2.Label {
                Layout.fillWidth: true
                font.bold: true
                text: flyout.editor && flyout.editor.flyoutVisible && flyout.editor.draft
                    ? flyout.editor.flyoutTitle : ""
                color: flyout.editor ? flyout.editor.palette.windowText : Kirigami.Theme.textColor
                elide: Text.ElideRight
            }
            QQC2.Button {
                Layout.fillWidth: true
                text: "Move selected item here"
                enabled: !!flyout.editor && flyout.editor.canMoveSelectionIntoFlyout()
                onClicked: flyout.editor.moveSelectedIntoFlyout()
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: "Select an item in the parent menu, then hover over this submenu."
            }
            QQC2.ScrollView {
                id: viewport
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: availableWidth
                Column {
                    id: menuRows
                    width: viewport.availableWidth
                    spacing: 0
                    Repeater {
                        model: flyout.entries
                        delegate: Item {
                            id: childRow
                            required property var modelData
                            property var entry: modelData
                            width: menuRows.width
                            height: 36
                            Rectangle {
                                anchors.fill: parent
                                radius: 2
                                color: Kirigami.Theme.highlightColor
                                opacity: pointer.containsMouse ? 0.23 : 0
                            }
                            QQC2.Label {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 12
                                verticalAlignment: Text.AlignVCenter
                                text: childRow.entry.title || ""
                                color: flyout.editor ? flyout.editor.palette.windowText : Kirigami.Theme.textColor
                                elide: Text.ElideRight
                            }
                            MouseArea {
                                id: pointer
                                anchors.fill: parent
                                hoverEnabled: true
                                onEntered: {
                                    if (flyout.editor && childRow.entry.kind === "submenu")
                                        flyout.editor.openFlyout(childRow.entry.id);
                                }
                                onClicked: {
                                    if (!flyout.editor) return;
                                    if (childRow.entry.kind === "submenu")
                                        flyout.editor.openFlyout(childRow.entry.id);
                                    else flyout.editor.navigate(flyout.editor.flyoutId, childRow.entry.id);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
