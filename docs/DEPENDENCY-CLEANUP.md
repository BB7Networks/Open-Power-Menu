# Optional PySide6 review after a native upgrade

Open Power Menu 2.1 uses C++/Qt and does not require Python or PySide6 for normal
native installation, menus, configuration or removal. **Keep PySide6 is the default
and recommended choice.** Other applications may still need it. Returning to OPM
1.0.1 also needs that release's Python/PySide6 runtime.

After an identified legacy installation is successfully upgraded and its native
activation checks pass, the installer offers a one-time notice if system PySide6
packages are detected. Terminal choices are Keep, Review, and Don't show this again.
Unattended installs never wait for input: they keep packages and print the review
command. Reinstalls and minor updates do not repeat the offer.

Review at any time with `open-power-menu --review-dependencies`; suppress reminders
with `open-power-menu --dismiss-dependency-review`. This state lives in
`$XDG_DATA_HOME/open-power-menu-recovery/dependency-review/native-2.1.json`, separately
from menu configuration and transaction snapshots. State writes use a separate cooperative lock and the installer's
no-follow, owner/mode-checked filesystem operations. A concurrent review cannot
replace another review's temporary state file. A failed query/state write does
not fail a successful installation.

On Arch/Manjaro the review reads `pacman -Qi pyside6` and displays install reason,
Required By and Optional For. On Debian it reads installed `python3-pyside6.*`
packages through dpkg-query, explicit status through apt-mark, and installed reverse
dependencies through apt-cache, including a separate broader optional/recommended
view. Query arguments are literal arrays; returned package names must match a narrow
package-name grammar. Folded pacman dependency lists are preserved in full. Queries have a shared
five-second budget and one-second per-process timeout; oversized or timed-out
responses remain incomplete. The review never invokes a removal transaction or sudo.

No declared reverse dependencies is **not proof of safe removal**. pip packages,
virtual environments, scripts and applications outside the package database can
still use PySide6. OPM does not claim that the package manager knows every consumer.
Incomplete/unsupported queries recommend keeping it. Do not remove Python itself.

For manual review, `pacman -Qi pyside6` is read-only. On Debian the report provides
`apt-get --simulate remove` with the detected package names; simulation is for review
only and OPM does not execute it. Any later real transaction is a separate informed
user action resolved by the system package manager. Inspect required and optional
consumers and keep the original runtime while legacy rollback is needed.

If you already removed it, restore the legacy runtime **before** rolling back:

- Arch/Manjaro: `sudo pacman -S pyside6`
- Debian: `sudo apt install python3-pyside6.qtwidgets python3-pyside6.qtdbus`

The installer checks those Python modules before replacing a native installation
with a legacy snapshot. If unavailable, rollback stops before replacement. Existing
configuration, launcher/shortcut settings and retained transaction snapshots remain
available. Native-to-native rollback has no Python requirement.
