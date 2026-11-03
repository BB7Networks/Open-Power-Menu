#!/usr/bin/env bash
# Save a private, read-only point-in-time copy before experimenting with Plasma
# panel layout. This script deliberately never edits a live Plasma config.
set -euo pipefail
if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
    printf 'Run this as your desktop user, not root.\n' >&2
    exit 2
fi
config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
backup_root="$data_home/open-power-menu/panel-backups"
mkdir -p "$backup_root"
chmod 700 "$backup_root"
backup_dir="$(mktemp -d "$backup_root/pre-launcher-move-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")"
chmod 700 "$backup_dir"
files=(plasma-org.kde.plasma.desktop-appletsrc kglobalshortcutsrc kwinrc plasmashellrc)
copied=0
for name in "${files[@]}"; do
    source="$config_home/$name"
    if [[ -f "$source" && ! -L "$source" ]]; then
        cp -- "$source" "$backup_dir/$name"
        chmod 600 "$backup_dir/$name"
        copied=$((copied+1))
    fi
done
printf 'Private Plasma configuration snapshot: %s\n' "$backup_dir"
printf 'Configuration files copied: %s\n' "$copied"
if [[ -f "$backup_dir/plasma-org.kde.plasma.desktop-appletsrc" ]]; then
    printf '\nLauncher-related plugins found in panel configuration (read-only):\n'
    if ! grep -inE '^plugin=.*(appgrid|kickoff|kicker|launcher|simplemenu)' \
            "$backup_dir/plasma-org.kde.plasma.desktop-appletsrc"; then
        printf '  No launcher plugin matched common names. Other launchers may still be installed.\n'
    fi
else
    printf 'No Plasma panel file was found under %s. Nothing to migrate yet.\n' "$config_home"
fi
printf '\nNo panel layout, widget, shortcut, or session settings were changed.\n'
printf 'Keep this snapshot; do not overwrite live Plasma config files during a running session.\n'
