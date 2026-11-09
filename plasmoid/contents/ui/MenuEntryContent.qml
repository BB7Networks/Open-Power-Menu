// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PC3

RowLayout {
    id: content
    property var entry: ({})
    property real iconSize: 18
    property bool showIcons: true
    property bool showHints: !!entry.access_hint
    property bool opensLeft: false
    property color foreground: Kirigami.Theme.textColor
    visible: entry.kind !== "separator"
    spacing: 8

    // Reserve both gutters even for commands. Opening/flipping a submenu must
    // never move the label or misalign it with adjacent command rows.
    Item {
        Layout.preferredWidth: 14
        Layout.preferredHeight: 18
        Kirigami.Icon {
            objectName: "leftIndicator"
            anchors.fill: parent
            source: "go-previous-symbolic"
            color: content.foreground
            visible: content.entry.kind === "submenu" && content.opensLeft
        }
    }
    Kirigami.Icon {
        objectName: "entryIcon"
        Layout.preferredWidth: content.iconSize
        Layout.preferredHeight: content.iconSize
        source: content.entry.icon || "application-x-executable"
        color: content.foreground
        visible: content.showIcons
        opacity: content.entry.enabled === false ? 0.4 : 1
    }
    PC3.Label {
        objectName: "entryLabel"
        font: Kirigami.Theme.defaultFont
        Layout.fillWidth: true
        text: content.entry.title || ""
        color: content.foreground
        elide: Text.ElideRight
        opacity: content.entry.enabled === false ? 0.5 : 1
    }
    Item {
        objectName: "accessKeyColumn"
        visible: content.showHints
        Layout.preferredWidth: Math.ceil("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789".split("").reduce((width, key) => Math.max(width, hintFont.advanceWidth(key)), 0)) + Math.ceil(hintFont.height / 4)
        Layout.minimumWidth: Layout.preferredWidth
        Layout.maximumWidth: Layout.preferredWidth
        Layout.preferredHeight: hint.implicitHeight
        FontMetrics { id: hintFont; font: hint.font }
        PC3.Label {
            id: hint
            objectName: "accessKeyHint"
            font: Kirigami.Theme.defaultFont
            anchors.fill: parent
            text: content.entry.access_hint || ""
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: content.foreground
            opacity: content.entry.enabled === false ? 0.4 : 0.7
            Accessible.name: text ? "Access key " + text : ""
        }
    }
    Item {
        Layout.preferredWidth: 14
        Layout.preferredHeight: 18
        Kirigami.Icon {
            objectName: "rightIndicator"
            anchors.fill: parent
            source: "go-next-symbolic"
            color: content.foreground
            visible: content.entry.kind === "submenu" && !content.opensLeft
        }
    }
}
