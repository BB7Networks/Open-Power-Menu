#!/usr/bin/env bash
# Build a legacy compatibility fixture. Never publish it as native 2.1.
set -euo pipefail
root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
version="$(python3 - "$root" <<'PY_VER'
import json, pathlib, sys
root=pathlib.Path(sys.argv[1])
print(json.loads((root/'plasmoid/metadata.json').read_text())['KPlugin']['Version'])
PY_VER
)"
dist="$root/dist"
mkdir -p "$dist"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
stage="$tmp/OpenPowerMenu-LegacyFixture-v$version"
mkdir -p "$stage"
for n in install.sh uninstall.sh LICENSE README.md CHANGELOG.md run.py; do cp -a "$root/$n" "$stage/"; done
cp "$root/docs/history/releases/RELEASE-NOTES-v$version.md" "$stage/"
for n in assets examples openpowermenu plasmoid docs legacy; do cp -a "$root/$n" "$stage/"; done
find "$stage" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$stage" -type f -name '*.pyc' -delete
(
  cd "$tmp"
  zip -qr "$tmp/OpenPowerMenu-LegacyFixture-v$version.zip" "$(basename "$stage")"
  tar -czf "$tmp/OpenPowerMenu-LegacyFixture-v$version.tar.gz" "$(basename "$stage")"
)
# Replace complete archives; updating an existing ZIP retains obsolete filenames.
mv "$tmp/OpenPowerMenu-LegacyFixture-v$version.zip" "$dist/"
mv "$tmp/OpenPowerMenu-LegacyFixture-v$version.tar.gz" "$dist/"
(
  cd "$dist"
  sha256sum "OpenPowerMenu-LegacyFixture-v$version.zip" "OpenPowerMenu-LegacyFixture-v$version.tar.gz" > SHA256SUMS
)
printf 'Legacy fixture ZIP: %s\n' "$dist/OpenPowerMenu-LegacyFixture-v$version.zip"
printf 'Legacy fixture TAR: %s\n' "$dist/OpenPowerMenu-LegacyFixture-v$version.tar.gz"
printf 'Widget-only archive is NOT included; see docs/KDE-STORE.md.\n'
