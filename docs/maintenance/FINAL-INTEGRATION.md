# Native 2.1.0 final integration review

This is a release-preparation record, separate from the stable-facing user guides.
The owner approved the content and screenshots at
`b385634e93face5e41062ce711352422ebfa2941`. Integration uses
`release/2.1.0-final-integration`, targeting `main`. It does not authorize merging,
tagging or publishing. The integration PR records the exact final source commit,
qualification run and downloadable artifact identities after qualification.

## Source ancestry and preservation

Every row is an ancestor of the next; the integration branch starts directly at
the last row. No cherry-pick or replay of the stacked work is needed.

| Source | Exact commit |
| --- | --- |
| `main`, stable 1.0.1 | `34058480b6e3bc1ecc1f19d420fb744f570eca34` |
| Historical PR #10 head | `5b1384832c19d3d1d9a5dbadf8421f6e9b612811` |
| Published RC2 | `2f889df3e5b29f49611f8cf37f41f15e86cad7c1` |
| Approved installer work, PR #11 | `0bf2f247ff6406d797112e8223dda4c9b4f0d59d` |
| Approved cleanup, PR #12 | `4e11393c4d289c453044130d79dc54a23049c32c` |
| Approved showcase, PR #13 | `b385634e93face5e41062ce711352422ebfa2941` |

The integration retains all native runtime/widget/editor/installer source, the
39 PNGs and capture manifest, historical galleries, compatibility tests, frozen
inventories and published release history. Its changes prepare public wording,
qualification evidence and stable asset retention. No ghosting work or new
application behavior is included. PRs #10–13 remain intact.

## GitHub visual acceptance

The owner approved the content and screenshots. The automated environment's
enforced allowlist still excludes `github.githubassets.com`, which serves GitHub
CSS and JavaScript. An unstyled HTML response is not desktop/mobile or light/dark
acceptance. `tools/showcase/review-github.py` explicitly rejects it. The final PR
records the attempted browser review; do not report it as passing if blocked.

Manual review checklist for the integration branch's rendered README:

1. Open it in desktop and narrow/mobile view, in GitHub light and dark modes.
2. Confirm readable captions, aligned two/three-column comparisons and no page-wide
   horizontal overflow. Wide reference tables may scroll within their container.
3. Confirm the hero is labeled customized; the default/example comparison clearly
   distinguishes installation defaults from rearranged entries and nested menus.
4. Open representative hero, default, Configure and editing images at full size;
   check sharp text, meaningful alt text and all 39 image destinations.
5. Check installation commands and distro filenames. Stable download destinations
   will return 404 until the separately approved release is published; that is
   expected during this review, not a successful public-download check.

## Qualification and physical scope

Qualification must use the final push commit, with all ten existing jobs and the
dependent collection job passing. Collection compares the source archive with
`git archive`, verifies sealed native payloads and package equivalence, rebuilds
all three EZ ZIPs byte-for-byte, checks minimal runtimes and installed X11/Wayland
activation, and verifies the exact stable manifest/checksums without publishing.
All automated power operations target private mocks.

The owner reported successful physical Manjaro EZ installation and normal-use
menu/Configure acceptance during installer preparation. This does not establish
real power-action or physical held-key safety, nor physical installation of the
final integrated source. The structured `physical_acceptance` section in
`QUALIFICATION.json` preserves these limits.

The intermittent Kubuntu X11 hidden-launcher timeout after deliberate key
release/repress remains unresolved. Earlier and subsequent passing runs of the
same source do not diagnose it. See [the exact failure and test scope](../TESTING.md#acceptance-scope-and-unresolved-results).
Deferred ghosting, responsiveness, Wayland observation and distribution/runtime
boundaries remain documented. Final results and failures must be recorded in the
integration PR rather than overwriting historical evidence.

## Exact stable release inventory

Each of these eight archives has a matching external `.sha256` sidecar:

| Format | Exact asset name |
| --- | --- |
| Manjaro EZ | `OpenPowerMenu-EZ-v2.1.0-Manjaro-x86_64.zip` |
| Debian EZ | `OpenPowerMenu-EZ-v2.1.0-Debian13-x86_64.zip` |
| Kubuntu EZ | `OpenPowerMenu-EZ-v2.1.0-Kubuntu26.04-x86_64.zip` |
| Manjaro bundle | `OpenPowerMenu-2.1.0-manjaro-rolling-x86_64.tar.gz` |
| Debian bundle | `OpenPowerMenu-2.1.0-debian-13-x86_64.tar.gz` |
| Kubuntu bundle | `OpenPowerMenu-2.1.0-ubuntu-26.04-x86_64.tar.gz` |
| Manjaro package | `open-power-menu-native-2.1.0-1-x86_64.pkg.tar.zst` |
| Source | `OpenPowerMenu-2.1.0-source.tar.gz` |

The other five files are `SOURCE-COMMIT`, `RELEASE-NOTES.md`, `QUALIFICATION.json`,
`RELEASE-MANIFEST.json` and `SHA256SUMS`: **21 stable assets total**.
The separate review artifact adds `REVIEW-STATUS.md`; it is not a stable asset.
Actions retention is 90 days. Persistent Release URLs are created only after
explicit publication approval.

## Publication boundary

The [stable publisher](../PUBLISHING.md) defaults to verification only. Its live
path requires an exact approved commit and explicit physical acceptance, reruns
qualification, uploads to a draft, downloads and verifies every asset, then
checks the tag before making the release Stable and Latest. Tests use a fake
GitHub transport; no live publication is part of this integration task.

Review the exact source, qualification, unresolved findings and acceptance scope
before authorizing a merge, stable tag or release. No additional RC is planned.
