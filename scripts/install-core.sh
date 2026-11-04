#!/usr/bin/env bash
# User-local, reversible upgrade; leaves every existing panel widget untouched.
# Installs its own separate Plasma widget; does not change panel layout.
set -euo pipefail
src="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
bin_home="${XDG_BIN_HOME:-$HOME/.local/bin}"
app_dir="$data_home/open-power-menu"
config_dir="$config_home/open-power-menu"
applications_dir="$data_home/applications"
icons_dir="$data_home/icons/hicolor/scalable/apps"
dbus_dir="$data_home/dbus-1/services"
widget_dir="$data_home/plasma/plasmoids/org.openpowermenu.start"

# Snapshot/migration failure stops the upgrade before replacing installed files.
python3 "$src/openpowermenu/widget_snapshots.py" prepare "$data_home"
mkdir -p "$app_dir" "$config_dir" "$bin_home" "$applications_dir" "$icons_dir" "$dbus_dir"
cp -a "$src/openpowermenu" "$app_dir/"
cp "$src/run.py" "$app_dir/run.py"
cp "$src/assets/open-power-menu.svg" "$icons_dir/open-power-menu.svg"
cat > "$bin_home/open-power-menu" <<'BIN'
#!/bin/sh
appdir="${XDG_DATA_HOME:-$HOME/.local/share}/open-power-menu"
exec python3 "$appdir/run.py" "$@"
BIN
chmod 755 "$bin_home/open-power-menu"
if [[ ! -e "$config_dir/menu.json" ]]; then
    python3 "$src/run.py" --default-config > "$config_dir/menu.json"
fi
cat > "$dbus_dir/org.openpowermenu.Service.service" <<SERVICE
[D-BUS Service]
Name=org.openpowermenu.Service
Exec=$bin_home/open-power-menu --service
SERVICE
cat > "$applications_dir/org.openpowermenu.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Version=1.0
Name=Open Power Menu
GenericName=Power User Menu
Comment=Standalone Windows-like Win+X system menu
Exec=$bin_home/open-power-menu
Icon=open-power-menu
Terminal=false
Categories=System;Utility;
StartupNotify=true
DESKTOP

if command -v kpackagetool6 >/dev/null 2>&1; then
    if [[ -d "$widget_dir" ]]; then
        kpackagetool6 --type Plasma/Applet --upgrade "$src/plasmoid"
    else
        kpackagetool6 --type Plasma/Applet --install "$src/plasmoid"
    fi
else
    mkdir -p "$widget_dir"
    cp -a "$src/plasmoid/." "$widget_dir/"
    echo 'Warning: kpackagetool6 not found. Copied widget directly; log out/in if it does not appear.' >&2
fi
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 >/dev/null 2>&1 || true
fi
# Notify D-Bus about the user-local activation file without stopping the
# already-running service. Failure is non-fatal (e.g., installer outside KDE).
if command -v busctl >/dev/null 2>&1; then
    busctl --user call org.freedesktop.DBus /org/freedesktop/DBus \
        org.freedesktop.DBus ReloadConfig >/dev/null 2>&1 || true
fi
printf '\nOpen Power Menu v0.4.17 installed (no panel widgets or shortcuts changed).\n'
printf '  Widget:  Open Power Menu Start Button\n'
printf '  Backend: %s/open-power-menu\n' "$bin_home"
printf '  Config:  %s/menu.json (preserved)\n' "$config_dir"
printf '  DBus:    %s/org.openpowermenu.Service.service\n' "$dbus_dir"
if ! python3 -c 'from PySide6 import QtCore, QtDBus, QtWidgets' >/dev/null 2>&1; then
    printf '\nInstall missing Qt dependency on Manjaro: sudo pacman -S --needed pyside6\n'
fi
# Stop only an identified previous version of our own D-Bus backend; the
# user service will relaunch the new version automatically when requested.
# Never kill plasmashell, AppGrid, or any unrelated process.
python3 "$src/run.py" --restart-owned-service || true
# Retention runs only after successful installation. Cleanup failure preserves
# extra history and reports it without misreporting the completed upgrade.
if ! python3 "$src/openpowermenu/widget_snapshots.py" prune "$data_home"; then
    printf 'Warning: installed successfully, but old widget snapshots could not be pruned.\n' >&2
fi
printf '\nBefore testing widget, verify backend:\n'
printf '  %s/open-power-menu --check\n' "$bin_home"
printf '  qdbus6 org.openpowermenu.Service /OpenPowerMenu org.openpowermenu.Service.Ping\n'
printf '\nTest without changing your panel: QML_DISABLE_DISK_CACHE=1 plasmawindowed org.openpowermenu.start\n'
printf 'If successful, refresh the existing widget locally (not during remote access).\n'
printf 'Menu editor: %s/open-power-menu --edit\n' "$bin_home"
printf 'Other launchers are never removed or reconfigured. Optional hide is selected in Configure.\n'
