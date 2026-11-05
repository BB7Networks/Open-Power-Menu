#!/usr/bin/env bash
# Leaves the user's menu.json and other launchers untouched.
set -euo pipefail
[[ $EUID -ne 0 ]] || { echo "Run as your normal desktop user, WITHOUT sudo." >&2; exit 1; }
src="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
bin_home="${XDG_BIN_HOME:-$HOME/.local/bin}"
widget_dir="$data_home/plasma/plasmoids/org.openpowermenu.start"
# Preserve legacy rollback history before removing any installed files.
python3 "$src/openpowermenu/widget_snapshots.py" migrate "$data_home"
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
printf 'Widget recovery snapshots remain in %s/open-power-menu-recovery/widget-backups/\n' "$data_home"
printf 'Remove the Start Button widget from the panel first if it is still present.\n'
