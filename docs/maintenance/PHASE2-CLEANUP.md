# Phase 2 repository cleanup review

Approved baseline: `0bf2f247ff6406d797112e8223dda4c9b4f0d59d` (Phase 1).
Scope: repository organization, installation guidance and stable publication
preparation. Physical acceptance, Phase 3 documentation review and explicit
stable publication approval remain outstanding. No tag or release is created.

## Proposed structure (recorded before moving files)

The baseline has 279 tracked files and no tracked logs, compiled objects,
libraries, ZIPs or package archives. [The complete baseline inventory](phase2-inventory.csv)
classifies every file, records its approved SHA-256 and specifies its destination.

```text
native/                   Current C++/Qt source, tests and native packaging
plasmoid/                 Shared Plasma 6 UI; native bundle adds input plugin/version
openpowermenu/data/        Catalog/defaults used by the native build and compatibility tests
openpowermenu/, run.py     Retained Python compatibility/reference implementation
legacy/1.0.1/             Explicitly opted-in legacy installation/build fixtures
scripts/                  Native artifact verification, staging, stable publisher
.github/workflows/        Qualification and manually approved stable publication
docs/                     Active installation, configuration, safety, recovery and development
docs/architecture/        Current architecture decisions
docs/history/             Historical reports, release notes, measurements and old publisher text
docs/images/              Existing gallery and genuine captures, preserved byte-for-byte
docs/maintenance/         Cleanup inventory, link/provenance audit and review results
install.sh, uninstall.sh  Source-checkout guidance only; no installation side effects
```

Keep the Python module paths and shared catalogs: moving them would needlessly
change reference tests, native resource imports and legacy upgrade verification.
The source widget metadata remains a compatibility template; the native bundler
sets its installed version from `native/VERSION` and verifies it as 2.1.0.

Archive investigation reports and old publishers rather than deleting evidence.
Remove only the root `INTEGRATION.md` duplicate; its identical canonical document
is retained in history, and its regression assertion follows that document.
The old repair script is retained as historical text, not a current repair tool.
Root wrappers must not run the Python installer, download software or mutate a
profile. Actual released 1.0.1/RC1/RC2 source baselines stay pinned in CI.

## Publication boundary

Prepare a manually dispatched draft-then-publish workflow. It must qualify the
exact committed source, collect all three distribution-specific EZ archives,
verify native payloads and the complete checksum inventory, upload to a draft,
download and verify the uploaded assets, then mark the approved stable release
Latest with Prerelease false. Test the publisher with a fake GitHub transport;
do not invoke the real publisher during Phase 2.

## Result and qualification

The resulting structure matches the proposal: 300 source/documentation files.
The baseline inventory contains 231 kept files, 6 legacy fixture moves, 41
archives and one duplicate deletion. [The added-file inventory](phase2-added-files.csv)
records all 22 new files/replacement entrypoints, including this report and both
inventories. Existing screenshots and the side-by-side gallery are retained.

Root install/uninstall commands print native guidance and exit without downloads,
package-manager calls, profile writes or session changes. Legacy tests use moved
engines with explicit fixture opt-in; released upgrade baselines remain unchanged.
Native bundle documentation now contains the current release notes and a concise
source-pinned guide. No historical report is needed to install or run the package.

Local qualification before the CI run:

- Full local suite: 571 passed, 8 skipped, 18 subtests passed.
- 71 targeted legacy path, root entrypoint and stable-publisher tests passed.
- 241 local documentation links/anchors resolve; 53 distinct external URLs are
  inventoried separately. Historical external source/evidence links are preserved;
  Actions links can require sign-in or expire. GitHub's release API confirms
  v1.0.1, RC1 and RC2 remain available. The future v2.1.0 URL is explicitly labelled.
- 109 protected runtime/installer/gallery files match approved Phase 1 SHA-256s.
- Shell syntax, workflow YAML parsing and whitespace checks pass.

The full portable/Qt suite and ten-job CI matrix qualify the committed source.
The stacked draft PR is the live record of exact CI runs, final counts, failures
and the reviewed artifact link; no live publisher is run. The 21-file stable
asset set is prepared only after same-run source/payload/evidence checks, and
mock-API tests cover failure paths and Stable/Latest publication ordering.
No production power, keyboard, popup, session or transaction semantics may change.
The Phase 1 intermittent X11 focus-readiness timeout is an unconfirmed observation;
ghosting and responsiveness remain deferred. No physical workstation is modified.
