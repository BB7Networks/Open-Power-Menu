# Phase 3 README and native showcase review

Approved application baseline: **`4e11393c4d289c453044130d79dc54a23049c32c`**.
Documentation branch: **`docs/2.1.0-readme-showcase`**, stacked on
**`maintenance/2.1.0-repository-cleanup`**. [Draft PR #13](https://github.com/BB7Networks/Open-Power-Menu/pull/13) records the
exact reviewed documentation commit, live GitHub rendering evidence and CI runs.
PRs 10–12 and historical releases remain unchanged. No merge, release, tag or
workstation installation is part of this phase.

## Delivered scope

- Rewritten product/technical README with early distro-specific EZ installation,
  future stable links explicitly marked unpublished, complete visual comparisons,
  keyboard/editing/power/recovery guidance and links to the active technical guides.
- **Out of the box versus customized example** shown separately. The default
  capture's entire configuration equals the native binary's `--default-config`
  JSON. The hero and comparison/editing profile are explicitly customized.
- 39 genuine PNG captures, **2,249,827 bytes** total, from 24 isolated cases;
  manifest, image inventory, actual default dump and a real EZ transcript.
- Complete [feature inventory](../FEATURES.md) including all significant settings,
  values/defaults, 23 built-in tools, keyboard behavior and implementation references.
- [Reproducible capture procedure](../SHOWCASE.md), unchanged production UI/models,
  documentation-only editor driver, controlled-comparison asset check and actual
  GitHub browser-review tool. The two-line CI addition runs only the asset check;
  existing application qualification and stable publishing logic are preserved.
- Historical gallery retained with original PNG bytes and filenames. Both frozen
  Phase 2 CSV inventories remain byte-for-byte identical.

[Exact changed-file inventory](phase3-changed-files.csv) ·
[Exact image inventory](../images/2.1/image-inventory.csv) ·
[Capture manifest](../images/2.1/manifest.json)

## Local qualification

- Existing full available Python suite: **571 passed, 9 skipped, 18 subtests
  passed**. Run with the retained Qt-capable development virtual environment and
  `QT_QPA_PLATFORM=offscreen`; host system Python alone did not contain pytest.
- Native production payload and separate capture-driver Release builds passed.
  All 24 final capture cases passed; every recorded power-request list is empty.
  A freshly built capture image independently rebuilt both targets, reproduced
  the default/Configure cases and completed EZ check/install with no power request.
- Real Debian EZ external SHA-256, runtime `--check` and interactive install each
  returned 0 in a disposable profile. The [full transcript](../images/2.1/ez-transcript.txt)
  preserves the actual prompt and successful installation output.
- Asset check: 39 PNG hashes/dimensions, complete CSV coverage, source/runtime
  provenance, exact defaults, controlled preference deltas, equal hint/icon
  geometry, visible width/density/height changes and adaptive flyout direction.
- Baseline check: both frozen inventories and **219** runtime/test/build/legacy/
  historical-image paths unchanged. No capture driver is in the production build.
- Normal repository audit: **479 local links/anchors** pass. Six current README
  web links return 200; six explicitly unpublished stable asset destinations return
  the expected 404. The remaining historical external URLs are inventoried, not
  claimed requalified.
- Markdownlint: **0 issues across 8 guides**, with long lines, raw HTML and table
  column padding permitted for the requested GitHub image tables. Whitespace,
  Python compilation, workflow YAML and shell syntax checks pass.

The full CI matrix remains enabled on the documentation branch. Its final results
and exact run URLs are recorded in the draft PR rather than copied into a frozen
source-baseline inventory. A green virtual test does not certify a physical desktop.

## GitHub presentation review

Use `tools/showcase/review-github.py` against the pushed branch's actual GitHub
README. It uses verified TLS and records 1440×1000 desktop and 390×844 mobile
views in both GitHub automatic light and dark modes. It visits every image,
checks decoding, full-size links, alt text and page overflow, and saves genuine
browser screenshots of the opening, defaults, appearance and editing sections.
It rejects blocked stylesheets and missing GitHub theme variables before treating
a view as qualified. GitHub requires access to `github.githubassets.com`; an
unstyled HTML response is not a successful visual review.

The draft PR carries the completed render findings and review evidence. Long
reference/download tables may scroll within their table container on narrow
screens; the page itself should not require horizontal scrolling. Full-size
image links retain native-resolution pixels. Future stable asset links are
expected to be unavailable before publication; historical source/evidence URLs
are not rewritten merely because an Actions artifact expires.

## Remaining gates and findings

- Review this documentation branch, the default/example distinction and actual
  native captures before merging the stacked work.
- Complete physical acceptance on supported desktops, including display scaling,
  launcher variants and compositor/shortcut behavior. Power tests use private mocks.
- X11 translucent-panel ghosting and minor responsiveness differences remain
  deferred. Wayland release-observation and distro binary boundaries are documented.
- The existing launcher picker includes non-launcher applets such as spacers;
  select the actual application launcher. Any narrower filtering is separate
  production work, not a hidden change in this documentation branch.
- Published captures remain tied to their original Debian fixture provenance.
  The new capture image and a fresh reproduction subset also passed; this does
  not extend the supported physical hardware or distribution claims.
- Final stable publication still requires explicit review and approval. Stable
  v1.0.1 remains Latest; RC1 and RC2 remain historical prereleases.
