# Power behavior and testing safety

Configure → General → **Power Actions** selects one of three policies for
native Shutdown, Restart and Sign out entries:

| Policy | Native behavior |
| --- | --- |
| Follow KDE system settings | Follow KDE's current confirmation preference; default for new configurations |
| Always show confirmation | Request KDE's native confirmation interface |
| Execute immediately | Use KDE's immediate dispatch without a confirmation step |

KDE authorization and availability still apply. Saved legacy Boolean settings
are migrated according to the existing native model; upgrades preserve choices.
Selection identities include the effective policy, and a changed policy before
dispatch fails closed. OPM does not implement a second shutdown countdown UI.

**Explicit custom commands keep their own semantics.** For example, a saved
`qdbus6 org.kde.Shutdown ... logoutAndShutdown` command is not a native built-in
and can act immediately even when Always show confirmation is selected. Inspect
its entry in Configure; do not test this by initiating another real operation.
Suspend, Hibernate and Lock also have their existing platform-specific handling.

Read-only backend diagnostics:

```sh
qdbus6 org.openpowermenu.Service /OpenPowerMenu   org.openpowermenu.Service.Ping
qdbus6 org.openpowermenu.Service /OpenPowerMenu   org.openpowermenu.Service.GetPowerDiagnostics
```

These do not dispatch an action. Review diagnostic paths and custom commands
before sharing output. All automated tests and manual power-key acceptance must
use [private mock services](TESTING.md#private-power-and-keyboard-tests).
Do not trigger shutdown, restart, sign-out, suspend, hibernate or lock on a working
session to check packaging or keyboard behavior.
