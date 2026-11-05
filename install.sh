#!/usr/bin/env bash
# User-friendly setup wrapper for the user-local core installer.
set -euo pipefail
here="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
app_dir="$here"

fail() { printf '\nERROR: %s\n\n' "$*" >&2; exit 1; }

printf '\n================================================\n'
printf ' OPEN POWER MENU - EASY SETUP\n'
printf ' KDE Plasma 6 / Manjaro\n'
printf '================================================\n\n'

[[ $EUID -ne 0 ]] || fail "Run this as your normal desktop user, WITHOUT sudo. Example: bash install.sh"
[[ -f "$app_dir/scripts/install-core.sh" && -f "$app_dir/run.py" ]] || fail 'This package is incomplete. Extract the whole ZIP, not just install.sh.'
command -v python3 >/dev/null 2>&1 || fail 'Python 3 is required. Install python3 from your distribution.'
command -v kpackagetool6 >/dev/null 2>&1 || fail 'KDE Plasma 6 is required (kpackagetool6 not found). Please run this on a Plasma 6 desktop.'

if ! python3 -c 'from PySide6 import QtCore, QtDBus, QtWidgets' >/dev/null 2>&1; then
    printf 'A required Qt/Python component (PySide6) is missing.\n'
    if command -v pacman >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
        printf 'On Manjaro, the package is named pyside6.\n'
        printf 'Install it using your system package manager? This will ask for\n'
        printf 'your password and install a system package.\n'
        read -r -p 'Install PySide6 now? [y/N]: ' reply || reply=''
        if [[ "$reply" =~ ^[yY]([eE][sS])?$ ]]; then
            sudo pacman -S --needed pyside6 || fail 'PySide6 installation failed. Update Manjaro if necessary and retry.'
        else
            fail 'PySide6 is required. Install it when ready (sudo pacman -S --needed pyside6), then rerun bash install.sh.'
        fi
    else
        fail 'PySide6 is required. Install the PySide6 QtCore, QtDBus and QtWidgets modules with your distribution package manager and rerun.'
    fi
    python3 -c 'from PySide6 import QtCore, QtDBus, QtWidgets' >/dev/null 2>&1 || fail 'PySide6 is still unavailable to the current python3 interpreter.'
fi

cache_home="${XDG_CACHE_HOME:-$HOME/.cache}"
mkdir -p "$cache_home/open-power-menu"
log="$cache_home/open-power-menu/install-$(date +%Y%m%d-%H%M%S)-$$.log"
widget_home="${XDG_DATA_HOME:-$HOME/.local/share}/plasma/plasmoids/org.openpowermenu.start"
if [[ -d "$widget_home" ]]; then
    install_kind='upgraded'
else
    install_kind='installed'
fi

printf '\nInstalling Open Power Menu for: %s\n' "${USER:-$(id -un)}"
if ! bash "$app_dir/scripts/install-core.sh" >"$log" 2>&1; then
    printf '\nInstallation failed. Details from %s:\n\n' "$log" >&2
    tail -n 45 "$log" >&2
    exit 1
fi

bin_home="${XDG_BIN_HOME:-$HOME/.local/bin}"
if ! "$bin_home/open-power-menu" --check > /dev/null 2>&1; then
    printf '\nThe files were installed, but the application check failed.\n' >&2
    printf 'Installer details are in: %s\n' "$log" >&2
    exit 1
fi

printf '\nSUCCESS - Open Power Menu %s!\n' "$install_kind"
printf '%s\n' '---------------------------------------------'
printf '1. Right-click your KDE panel and choose Add Widgets.\n'
printf '2. Find "Open Power Menu Start Button" and drag it\n'
printf '   onto the SAME panel as your existing launcher.\n'
printf '3. Right-click your new button, click the gear icon,\n'
printf '   and use General to select the original launcher.\n'
printf '   Test it, then optionally hide the old button.\n\n'
printf 'If the widget is not yet listed, log out and back in\n'
printf 'LOCALLY (not when relying on remote desktop).\n'
printf '\nNever remove the original launcher: we only hide its button.\n'
printf 'Full instructions: %s/README.md\n' "$here"
printf 'Installer log: %s\n\n' "$log"
