# Python installation compatibility fixtures

These files retain the former Python installation engines for regression tests.
They are **not the native 2.1 installer**, and archives built here are labelled
`LegacyFixture`, not public EZ releases. Current shared Python/catalog/widget
sources remain at the repository root to preserve reference tests and imports.
The fixture is therefore not a reconstruction of the released 1.0.1 tree.

Fixture execution requires `OPM_LEGACY_FIXTURE=1` and explicit private XDG
configuration, data, cache and binary directories. The automated tests provide
these and fake desktop/package tools. Do not opt in on a working desktop.

Actual native upgrade/rollback qualification uses exact released source commits:
1.0.1 `34058480b6e3bc1ecc1f19d420fb744f570eca34`, RC1
`2384a9d03947b9a2e5de8f0ef72ae57e556bc29c`, and RC2
`2f889df3e5b29f49611f8cf37f41f15e86cad7c1`. Those archives and snapshots retain
their original installers. No historical tag, asset or rollback implementation
is changed by this directory move.

Use [native installation](../../docs/INSTALLATION.md) and
[recovery](../../docs/RECOVERY.md) for current user instructions.
