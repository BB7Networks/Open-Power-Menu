#!/bin/sh
# Create a checksum-pinned PKGBUILD from a clean, reviewed Git commit.
# Usage: prepare-pacman.sh REPOSITORY NEW_OUTPUT_DIRECTORY
set -eu
if [ "$#" -ne 2 ]; then
    echo 'Usage: prepare-pacman.sh REPOSITORY NEW_OUTPUT_DIRECTORY' >&2
    exit 2
fi
repository=$(git -C "$1" rev-parse --show-toplevel)
if ! git -C "$repository" diff --quiet || ! git -C "$repository" diff --cached --quiet; then
    echo 'Commit or preserve tracked changes before preparing the exact source archive.' >&2
    exit 2
fi
# Refuse existing outputs: never replace an earlier reviewed source package.
mkdir -p -- "$(dirname -- "$2")"
mkdir -- "$2"
out=$(CDPATH= cd -- "$2" && pwd)
git -C "$repository" archive --format=tar.gz --prefix=Open-Power-Menu/ \
    -o "$out/open-power-menu-source.tar.gz" HEAD
checksum=$(sha256sum < "$out/open-power-menu-source.tar.gz")
checksum=${checksum%% *}
git -C "$repository" show HEAD:native/packaging/PKGBUILD |
    sed "s/SOURCE_SHA256/$checksum/" > "$out/PKGBUILD"
git -C "$repository" rev-parse HEAD > "$out/SOURCE-COMMIT"
printf '%s  %s\n' "$checksum" 'open-power-menu-source.tar.gz' > "$out/SOURCE.sha256"
printf 'Prepared %s\n' "$out"
