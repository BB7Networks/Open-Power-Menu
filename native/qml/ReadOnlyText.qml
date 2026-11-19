// SPDX-License-Identifier: MIT
import QtQuick
import org.kde.kirigami as Kirigami

// These previews display configuration data, not editable documents. KDE's
// selectable label preserves selection/copy and avoids Breeze 6.7's TextArea
// mobile toolbar assigning a TextEdit to its TextInput-only target.
Kirigami.SelectableLabel {
    readOnly: true
    selectByMouse: true
    activeFocusOnTab: true
    textFormat: TextEdit.PlainText
    wrapMode: TextEdit.Wrap
    padding: Kirigami.Units.smallSpacing
}
