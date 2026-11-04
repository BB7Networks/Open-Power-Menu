# Reviewing and preparing releases

The canonical repository is <https://github.com/BB7Networks/Open-Power-Menu>.
Use a feature branch and a pull request. Keep the widget ID
`org.openpowermenu.start` stable so existing users retain the same applet.

## Before a new beta

1. Merge prerequisite fixes in order after their checks and review: the
   Windows-safe installer change, backup retention, then dependent feature work.
2. Run [automated checks and the two-workstation matrix](TESTING.md). Review
   [process findings](PROCESS-LIFECYCLE.md) and capture [real screenshots](images/README.md).
3. Choose a new beta version only after successful review. Update Python,
   metadata, installer labels, documentation, archive references and notes
   consistently. Do not tag or publish merely because a local archive builds.
4. Check license/attribution, clean-account setup and upgrade/rollback from the
   actual prior release packages. Preserve user menu and launcher configuration.

## Build local review artifacts

Current version identifiers remain at 0.4.17:

```bash
bash scripts/build-release.sh
bash scripts/build-widget-only.sh
(cd dist && sha256sum -c SHA256SUMS)
unzip -t dist/OpenPowerMenu-EZ-v0.4.17.zip
tar -tzf dist/OpenPowerMenu-EZ-v0.4.17.tar.gz
```

The complete EZ ZIP and TAR.GZ include both backend and widget plus instructions.
The `.plasmoid` is a separate widget-only artifact. Build scripts do not publish
anything. After a new version is reviewed and explicitly approved for release,
attach its complete EZ archives and checksums to the corresponding GitHub beta
release with accurate notes. Do not overwrite an existing release's versioned
artifacts with unreleased changes.

## KDE Store

Read [KDE-STORE.md](KDE-STORE.md). Store setup remains separate future work: a
native widget archive does not install the Python/PySide6 backend. Do not claim
one-click operation or publish a Store listing before the complete user-driven
setup path has been implemented and tested in a clean Plasma 6 account.
