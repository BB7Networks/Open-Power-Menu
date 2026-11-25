// Loaded dynamically so a missing native module fails closed for keyboard
// activation without making the widget's pointer/configuration UI unloadable.
import QtQuick
import "nativeinput" as Native
Native.InputGuard {}
