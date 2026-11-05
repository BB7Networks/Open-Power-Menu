# Reviewing and preparing releases

Version **1.0.1** is the first public release. Keep the widget ID
`org.openpowermenu.start` stable and preserve existing menu/panel settings.
GitHub Releases is the source of truth for published versions and assets.

## Review gates

1. Confirm `main` includes merged PRs #8 and #9, with the current 1.0.1
   gallery. PR #7 was reviewed and closed as superseded; do not replace the
   newer captures with its historical gallery.
2. Run [automated and physical checks](TESTING.md), including the
   [1.0.1 release checklist](RELEASE-1.0.1.md). Verify real Manjaro Wayland
   Desktop toggling, cross-window pointer dismissal and launcher/shortcut behavior.
3. Test clean installation, upgrade, failure rollback and uninstall from the
   extracted EZ package. Preserve custom menus, widget instances and recovery
   history. Review exact archive checksums and contents before distribution.
4. Publishing must be explicitly approved. The approved release commit uses
   `release: publish v<version>` to trigger the guarded GitHub Actions release
   workflow, which builds archives, verifies checksums, creates the tag and
   uploads the complete EZ assets. KDE Store remains a separate process.

## Build review artifacts

```bash
bash scripts/build-release.sh
bash scripts/build-widget-only.sh
(cd dist && sha256sum -c SHA256SUMS)
unzip -t dist/OpenPowerMenu-EZ-v1.0.1.zip
tar -tzf dist/OpenPowerMenu-EZ-v1.0.1.tar.gz
```

The metadata version controls archive names, top-level directory and release-note
selection. Python/CLI/D-Bus report the matching package version, covered by tests.
The complete ZIP/TAR contain backend, widget, assets, screenshots, documentation
and both installer wrappers. Widget-only packaging remains separate.

The release workflow creates the tag from the exact approved source commit
and attaches the complete EZ ZIP, TAR.GZ and SHA256SUMS. Do not replace
published versioned assets with different contents. The widget-only archive
is separate and must not be advertised as a complete installer.

See [KDE Store](KDE-STORE.md) before considering that separate distribution path.
