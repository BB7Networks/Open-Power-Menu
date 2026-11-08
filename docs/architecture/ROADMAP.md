# Native architecture and 2.1 roadmap

Stable release: **1.0.1**. Development: **2.1.0-dev**. Next public release:
**2.1.0**, directly from 1.0.1. Continue branch `feature/native-architecture-v1.1`
and draft PR #10 without rewriting history. `2.0.0-dev` was an internal architecture
milestone, not a public release; do not publish 2.0.0 or reserve a 2.0.1 release.

The 2.1 target combines the implemented Core/DBus backend, Qt Quick/Kirigami editor,
Qt Widgets standalone menu, guarded storage/recovery, complete native packaging and
reversible upgrades with:

1. Shared configurable entry access keys, nested sequences and optional hints in
   both menus; master enable and independent default-key reset in the editor.
2. Configurable pointer-leave delay, 0.5–5.0 seconds in 0.1-second increments,
   default 1.2 seconds. Preserve the saved toggle and disabled default.
3. Native Sleep/Hibernate with dynamic KDE/logind capability and policy checks,
   Polkit authorization and inhibitors, retaining existing KDE confirmation prompts.
4. Optional, read-only PySide6 dependency review after successful legacy upgrade;
   default Keep, separate one-time notice state and unchanged rollback protection.
5. Matching distribution builds, prioritizing Manjaro/Arch alongside Debian 13;
   safe direct 1.0.1 upgrades and no Python/compiler requirement for native installs.
6. Regression CI and explicit physical Plasma Wayland/X11 acceptance before release.

See [2.1 configuration and physical gates](../OPM-2.1.md),
[current development-pass results](../OPM-2.1-RESULTS.md), and
[historical native migration/performance evidence](native-migration-status.md).
The Store widget continues to require a separately installed native backend.
No frontend rewrite or self-contained Store claim is part of this release.

The current feature checkpoint adds configurable submenu hover delay, density/width/
icon presets and portable JSON import/export to the existing native architecture.
Implementation and focused tests are saved; full qualification is still pending.
See [feature checkpoint and next steps](../OPM-2.1-FEATURE-CHECKPOINT.md).
A self-contained Store edition remains outside this pass.

No merge, tagging, release publication, KDE Store update or active-desktop changes
are authorized by development preparation. Stable remains 1.0.1 until explicit
release approval, even if automated tests pass. Physical acceptance and supervised
power-action tests cannot be substituted with virtual compositor results.
