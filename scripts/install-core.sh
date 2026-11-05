#!/usr/bin/env bash
# User-local, reversible upgrade; leaves every existing panel widget untouched.
# Installs its own separate Plasma widget; does not change panel layout.
set -euo pipefail
[[ $EUID -ne 0 ]] || { echo "Run as your normal desktop user, WITHOUT sudo." >&2; exit 1; }
src="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
version=$(python3 - "$src/plasmoid/metadata.json" <<'PY_VERSION'
import json, sys
print(json.load(open(sys.argv[1]))['KPlugin']['Version'])
PY_VERSION
)
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
mkdir -p "$data_home" "$config_dir" "$bin_home" "$applications_dir" "$icons_dir" "$dbus_dir"
# Keep the previous installation usable if copying, KPackage or verification
# fails. Recovery snapshots stay outside this temporary rollback transaction.
transaction=$(mktemp -d "$data_home/.opm-install-XXXXXXXX")
managed=("$app_dir" "$widget_dir" "$bin_home/open-power-menu"
         "$applications_dir/org.openpowermenu.desktop"
         "$icons_dir/open-power-menu.svg" "$dbus_dir/org.openpowermenu.Service.service")
committed=false
prepared=false
new_config=false
finish_install() {
    result=$?
    rollback_ok=true
    trap - EXIT HUP INT TERM
    if [[ "$committed" == false && "$prepared" == true ]]; then
        printf 'Installation did not complete; restoring previous application files.\n' >&2
        for i in "${!managed[@]}"; do
            rm -rf -- "${managed[$i]}"
            if [[ -e "$transaction/old-$i" || -L "$transaction/old-$i" ]]; then
                mkdir -p -- "$(dirname -- "${managed[$i]}")"
                cp -a -- "$transaction/old-$i" "${managed[$i]}" || { result=1; rollback_ok=false; }
            fi
        done
        if [[ "$new_config" == true ]]; then rm -f -- "$config_dir/menu.json"; fi
    fi
    if [[ "$rollback_ok" == true ]]; then
        rm -rf -- "$transaction"
    else
        printf 'Rollback incomplete; preserved recovery files in %s\n' "$transaction" >&2
    fi
    exit "$result"
}
trap finish_install EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
for i in "${!managed[@]}"; do
    if [[ -e "${managed[$i]}" || -L "${managed[$i]}" ]]; then
        cp -a -- "${managed[$i]}" "$transaction/old-$i"
    fi
done
mkdir "$transaction/new-app"
cp -a "$src/openpowermenu" "$transaction/new-app/"
cp "$src/run.py" "$transaction/new-app/run.py"
prepared=true
if [[ -e "$app_dir" || -L "$app_dir" ]]; then mv -- "$app_dir" "$transaction/replaced-app"; fi
mv -- "$transaction/new-app" "$app_dir"
cp "$src/assets/open-power-menu.svg" "$icons_dir/open-power-menu.svg"
cat > "$bin_home/open-power-menu" <<'BIN'
#!/bin/sh
appdir="${XDG_DATA_HOME:-$HOME/.local/share}/open-power-menu"
exec python3 "$appdir/run.py" "$@"
BIN
chmod 755 "$bin_home/open-power-menu"
if [[ ! -e "$config_dir/menu.json" && ! -L "$config_dir/menu.json" ]]; then
    new_config=true
    python3 "$src/run.py" --default-config > "$config_dir/menu.json"
fi
cat > "$dbus_dir/org.openpowermenu.Service.service" <<SERVICE
[D-BUS Service]
Name=org.openpowermenu.Service
Exec=$bin_home/open-power-menu --service
SERVICE
# Desktop Entry Exec has two escaping layers (string, then quoted argument)
# and literal percent signs must not become field codes. Never use shell eval.
desktop_exec=$(python3 - "$bin_home/open-power-menu" <<'PY'
import sys
argument = sys.argv[1].replace('%', '%%')
for character in ('\\', '"', '`', '$'):
    argument = argument.replace(character, '\\' + character)
value = '"' + argument + '"'
value = value.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
print(value)
PY
)
cat > "$applications_dir/org.openpowermenu.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Version=1.0
Name=Open Power Menu
GenericName=Power User Menu
Comment=Standalone Windows-like Win+X system menu
Exec=$desktop_exec
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
# Validate the installed code/config before considering the transaction complete.
"$bin_home/open-power-menu" --check > /dev/null
committed=true
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 >/dev/null 2>&1 || true
fi
# Notify D-Bus about the user-local activation file without stopping the
# already-running service. Failure is non-fatal (e.g., installer outside KDE).
if command -v busctl >/dev/null 2>&1; then
    busctl --user call org.freedesktop.DBus /org/freedesktop/DBus \
        org.freedesktop.DBus ReloadConfig >/dev/null 2>&1 || true
fi
printf '\nOpen Power Menu v%s installed (no panel widgets or shortcuts changed).\n' "$version"
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
