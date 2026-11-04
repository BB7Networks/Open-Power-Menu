# Review: default actions, lifecycle and release readiness

## Base and scope

The fetched `main` at `ed5c9aa` is the initial 0.4.17 beta. On this review,
PR [#1](https://github.com/BB7Networks/Open-Power-Menu/pull/1)
(`fix/windows-installer-filenames`, `4ab1046`) and PR
[#2](https://github.com/BB7Networks/Open-Power-Menu/pull/2)
(`feature/config-backup-retention`, `8888039`) are open and unmerged, with
successful existing portable checks. PR #2 includes PR #1's commits. This work
is stacked on #2 rather than reimplementing either feature; merge order remains
#1, #2, then this branch. No version bump, release tag or Store listing is made.

The initial checkout baseline had 123 passing tests, 7 historical-baseline skips
and one failure caused by the missing lowercase installer. On the dependency
branch the baseline is **133 passed, 8 skipped, 18 subtests passed**. Historical
baseline trees under `/mnt/data` are not present; skips are reported separately.

## Action resolution

- **Logs:** `ksystemlog` first, then Konsole, then XTerm. Both terminal candidates
  require `journalctl` individually, so a missing journal does not hide the GUI.
  The fallback keeps the existing current-boot/warning filter and adds
  `-n 1000 --follow --no-pager`. No shell pipeline, sudo or installed-package
  mutation is involved. Access is limited by the user's normal journal rights.
- KDE's KSystemLog desktop entry uses `-qwindowtitle %c`; `%c` is a desktop-entry
  name substitution, not a valid literal argv value. Direct `ksystemlog` avoids
  passing an unexpanded code or forcing root. The upstream desktop entry also
  has `X-KDE-SubstituteUID`; OPM does not synthesize a privilege wrapper. Confirm
  the distro's normal interactive behavior during live acceptance.
- **Printers:** KDE `kcmshell6 kcm_printer_manager` first, then
  `system-config-printer`. The native module name is confirmed in KDE Print
  Manager's CMake source. Availability requires an exact module token from a
  successful, bounded `kcmshell6 --list`, not only the executable's presence.
  Results are cached for up to 30 seconds; probe failure falls back cleanly.
- The editor and resolver share per-candidate availability checks. New default
  layouts include Printers; existing saved `menu` arrays are preserved verbatim.
  Built-ins remain available through the editor's existing catalog selector.

Sources: [KSystemLog desktop entry](https://github.com/KDE/ksystemlog/blob/master/src/org.kde.ksystemlog.desktop),
[Print Manager module](https://github.com/KDE/print-manager/blob/master/src/kcm/CMakeLists.txt).

## Process and UI findings

[PROCESS-LIFECYCLE.md](PROCESS-LIFECYCLE.md) records the launch-path audit,
parent/session/cgroup distinctions and test evidence. Detached sessions already
let programs survive backend exit. Two narrower defects were addressed: exited
children awaiting reaping, and children retaining inherited standard streams.
No systemd scope policy or double-fork was introduced.

The existing editor design is retained: searchable installed apps, command
previews, independent built-in customization, nested menus and General/Layout
tabs. Actual offscreen modal interactions now verify picker search, populated
name/icon/command, save, real GIO/direct desktop application launch, backup setting
and Cancel. Qt tests do not establish the panel's visual or focus behavior.

XDG discovery already enforces directory precedence, Hidden/NoDisplay overrides,
desktop visibility, TryExec and localized labels. Additional corrections handle
locale modifiers and Desktop Entry string escaping before conservative Exec
parsing. Native KDE activation remains the preferred path for terminal apps,
working directories, D-Bus activation and desktop-specific behavior. Direct Exec
fallback now refuses to drop a required working directory. GIO versions that
load desktop-file contents can omit `%k`; that fallback is rejected for entries
requiring the field rather than silently changing their arguments. Direct
fallback expands `%k` explicitly. Picker argv preserves literal `$`, `~` and
`{home}` in names/paths; custom commands retain their documented path expansion.

Loaded configurations now validate the menu tree before the UI/dispatcher uses
it. Invalid commands, embedded NUL arguments, unknown actions and malformed
submenus fail with a configuration error rather than reaching subprocess or
partially constructing an editor. Saves still validate before writing.

## Backup retention review

PR #2's 10-backup default and General-tab control remain intact. Tests cover
0–1,000 validation (including bool rejection), old files missing the field,
retention counts, lowering the limit, zero preserving history, manual files,
symlink/directory exclusion, failed saves and nonfatal cleanup failures.

The automatic-name matcher remains limited to
`menu.json.bak-YYYYMMDDTHHMMSSffffffZ`; pruning runs only after `os.replace`.
Backup creation now uses exclusive creation with mode 0600, so a timestamp
collision cannot overwrite a prior backup or follow a planted symlink. Backup
write failures remove their partial output, leave the target unchanged and do
not prune. Manual backups should use distinct names, not the automatic pattern.

## Installers and packaging

PR #1's wrapper/core separation is retained. Real scripts run in temporary XDG
directories in regression tests; a KPackage stand-in exercises install/upgrade/
remove branching without touching a desktop. Existing menus and panel sentinel
files survive upgrades and removal, and prior widget contents are snapshotted.
Synthetic old-widget fixtures cover 0.4.16/0.4.17 metadata; actual old archived
installers still require workstation acceptance.

ZIP/TAR tests check integrity, identical file membership, Windows case-fold
safety, required backend/install scripts, version consistency, extraction from
a directory with spaces, and absence of bytecode/private menu data. Release
archives now include `docs/`, so their README links work offline. Wrappers are
invoked through Bash; the generated user launcher is executable. Every shell
script is checked individually: `bash -n file1 file2` only parses the first file,
so CI now loops over scripts. A separate Qt/D-Bus CI job exercises the runtime.

The source documentation is updated for the real repository, the current EZ
archive layout and the absence of a Store-ready backend package. Real screenshots
are pending; [the capture guide](images/README.md) lists filenames without
fabricating images. [KDE-STORE.md](KDE-STORE.md) proposes a user-driven setup flow
as separate future work.

## Regression boundary and remaining acceptance

Local validation on the prepared Python 3.12 / Node 24 cloud machine completed
with **177 passed, 8 historical-baseline skips, 18 subtests passed**, including
all eight real Qt/D-Bus runtime modes. Python compilation, individual Bash syntax
checks, whitespace checks, documentation links, ZIP/widget integrity and ZIP/TAR
checksums passed. GitHub CI runs the portable suite on Node 22 and the runtime/
installer checks with Qt in a separate job; consult the PR checks for their
current status rather than inferring remote CI from local results.

No files under `plasmoid/` are changed. Native/AppGrid dispatch, launcher status
masking, same-panel selection, icon inheritance, flyout placement and popup focus
handoff remain byte-identical to the dependency base. Existing Node model tests
exercise them. `--show-launcher-button` remains available; no operation writes
the Plasma panel configuration, removes another launcher or restarts Plasma.

Run the [desktop matrix](TESTING.md) on both workstations before release. The
cloud environment cannot validate KSystemLog authorization, a real printer KCM,
KPackage registration, compositor pointer/focus behavior, actual old-release
rollback, or grouped System Monitor display on Manjaro. Record failures and
screenshots before proposing a consistently versioned new beta.
