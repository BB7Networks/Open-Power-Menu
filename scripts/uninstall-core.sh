#!/usr/bin/env bash
# Leaves the user's menu.json and other launchers untouched.
set -euo pipefail
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
bin_home="${XDG_BIN_HOME:-$HOME/.local/bin}"
widget_dir="$data_home/plasma/plasmoids/org.openpowermenu.start"
if command -v kpackagetool6 >/dev/null 2>&1 && [[ -d "$widget_dir" ]]; then
    kpackagetool6 --type Plasma/Applet --remove org.openpowermenu.start || true
fi
rm -rf "$widget_dir"
rm -f "$data_home/dbus-1/services/org.openpowermenu.Service.service"
rm -f "$data_home/applications/org.openpowermenu.desktop"
rm -f "$data_home/icons/hicolor/scalable/apps/open-power-menu.svg"
rm -f "$bin_home/open-power-menu"
rm -rf "$data_home/open-power-menu"
printf 'Removed Open Power Menu application and widget. Existing panel launchers and menu.json remain.\n'
printf 'Remove the Start Button widget from the panel first if it is still present.\n'
