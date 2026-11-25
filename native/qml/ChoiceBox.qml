// SPDX-License-Identifier: MIT
import QtQuick
import QtQuick.Controls as Controls

// Settings choices are string arrays. Measure their labels independently of
// the style's contentItem width: Breeze's TextField and Qt's WidestText policy
// otherwise form an implicitWidth cycle on current rolling Qt/Breeze builds.
Controls.ComboBox {
    id: control
    FontMetrics { id: labelMetrics; font: control.font }
    function labelsWidth(entries, currentFont) {
        // The font argument keeps this binding responsive to theme/font changes.
        let result = 0;
        if (!entries) return result;
        for (const entry of entries)
            result = Math.max(result, labelMetrics.advanceWidth(String(entry)));
        return result;
    }
    // Reserve font-scaled space for the arrow and both frame/text margins;
    // reading deferred style items here would recreate the sizing cycle.
    implicitWidth: Math.ceil(labelsWidth(model, labelMetrics.font) + labelMetrics.height * 4)
}
