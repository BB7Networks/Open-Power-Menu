import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2

ColumnLayout {
    id: setup
    signal retryRequested()
    property string documentationUrl: "https://github.com/BB7Networks/Open-Power-Menu/blob/feature/native-architecture-v1.1/native/packaging/README.md"
    property color foreground: "#202020"
    spacing: 8
    QQC2.Label {
        Layout.fillWidth: true
        color: setup.foreground
        text: "Open Power Menu needs its native backend"
        font.bold: true
        wrapMode: Text.WordWrap
    }
    QQC2.Label {
        Layout.fillWidth: true
        color: setup.foreground
        text: "The Store download installs the widget only. Install the complete native package for your distribution, then retry. If it is already installed, check the package dependencies and session service."
        wrapMode: Text.WordWrap
    }
    QQC2.Button {
        objectName: "backendInstructions"
        text: "Installation instructions"
        onClicked: Qt.openUrlExternally(setup.documentationUrl)
    }
    QQC2.Button {
        objectName: "backendRetry"
        text: "Retry connection"
        onClicked: setup.retryRequested()
    }
}
