import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// Plasma's settings loader supplies title and cfg_*Default properties.
// A Page accepts title; explicitly declared defaults prevent failed assignments.
Kirigami.Page {
    id: page
    title: "General"
    property alias cfg_buttonIcon: iconField.text
    property string cfg_buttonIconDefault: "start-here-manjaro"
    property string cfg_leftAction: "launcher"
    property string cfg_leftActionDefault: "launcher"

    Kirigami.FormLayout {
        anchors.fill: parent
        QQC2.TextField {
            id: iconField
            Kirigami.FormData.label: "Fallback icon:"
            placeholderText: "Icon theme name or file:///path/to/icon.png"
            Layout.preferredWidth: 320
        }
        QQC2.ComboBox {
            id: leftActionCombo
            Kirigami.FormData.label: "Left click:"
            currentIndex: page.cfg_leftAction === "power" ? 1 : 0
            onActivated: index => page.cfg_leftAction = index === 1 ? "power" : "launcher"
            textRole: "text"
            valueRole: "value"
            model: [
                { text: "Activate existing Plasma launcher (AppGrid, Kickoff...)", value: "launcher" },
                { text: "Open Power User menu on both buttons", value: "power" }
            ]
        }
        QQC2.Label {
            text: "For Meta+X, use this widget’s Keyboard Shortcuts setting. Right-click opens Open Power Menu. To adopt the existing launcher's icon, choose a custom icon, or hide/unhide the original button, use Configure in the Power User menu. This field is the fallback icon when none is available."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }
}
