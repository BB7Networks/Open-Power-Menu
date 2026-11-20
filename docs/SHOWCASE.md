# Native 2.1 showcase: provenance and reproduction

The [README](../README.md) contains **39 real native captures** from approved
source **`4e11393c4d289c453044130d79dc54a23049c32c`**, version **2.1.0**.
No production code was changed to make these images. The existing historical
images and frozen historical inventories remain unchanged.

[Full manifest](images/2.1/manifest.json) · [Exact image inventory](images/2.1/image-inventory.csv) ·
[Feature audit](FEATURES.md) · [Historical gallery](images/README.md)

## What was actually captured

| Property | Recorded environment |
| --- | --- |
| Distribution | Debian GNU/Linux 13, x86-64 |
| Qt | `libqt6core6t64 6.8.2+dfsg-9+deb13u2` |
| Plasma | `plasma-workspace 4:6.3.6-2` |
| KWin | `kwin-x11 4:6.3.6-1` |
| Breeze | `4:6.3.5-1` |
| Font | Noto Sans 10 pt; `fonts-noto-core 20201225-2` |
| Display | Private Xvfb display, 1600×1000, 96 DPI, 100% scale |
| Desktop | Real KWin X11, plasmashell, Kickoff and panel spacers; 48-pixel bottom panel |
| Rendering | Qt Quick software backend; real native windows, no conceptual rendering |
| Isolation | New HOME/XDG profile and private session bus per case; system-bus address also points to that private bus; offline container |
| Power | Existing private recorder fixture owns KDE/logind endpoints. Lock uses a private recorder executable. **Zero menu power requests** in all capture cases. |
| Capture | `QScreen.grabWindow(0)`; crop only; lossless PNG encoding with no resampling, redrawing, labels, overlays or synthesized controls |

The widget and standalone are the **unmodified installed binaries/QML** from the
sealed native bundle. Configure is loaded by a separate documentation-only
QtTest driver linked to the actual `EditorSession`, `EditorCatalog` and unchanged
production QML/resources. It performs real form, selection and reorder operations;
it does not supply fake application models or replace controls. Its save calls
create genuine backup revisions in the disposable profile. It is not packaged
or added to the production CMake graph.

The **Out of the box** capture uses the exact native `--default-config` JSON,
without any preference or layout overrides. Its equality to the binary dump is
asserted by the asset check. Available rows reflect the installed fixture tools.
The other demonstration profile is intentionally customized: original button
hidden, custom OPM icon, a **Remote & Work → Tools** example submenu, and
**Always show confirmation**. These are supported choices, not claims about
new-install defaults. New defaults are in the [binary's JSON dump](images/2.1/native-defaults.json)
and [feature inventory](FEATURES.md). Installed desktop programs and an empty
`~/Network Locations` directory make those real entries available. Kickoff's
favorites refer to actual installed Dolphin, Konsole, Settings, Discover and
Info Center desktop entries. `builder` is the disposable account, not a person.
Any visible `/evidence/...` path belongs to this public demonstration fixture.

Default-off popup diagnostics are enabled only in the fixture to observe
readiness and geometry. They log lifecycle state without requesting focus or
adding a visible overlay. Real XTest input opens the widget, navigates flyouts
and edits the menu. Capture waits are readiness/paint waits in tooling, not
production timing changes. The cursor is moved outside the captured region.

## Gallery coverage

| Requested gallery | Delivered views |
| --- | --- |
| A — First impressions | Exact out-of-box defaults versus the clearly labelled customized example; customized hero with OPM button, Power User Menu, Remote & Work and nested Tools native flyouts |
| B — Launcher | Left / Center / Right with adaptive flyouts; original visible/hidden; adopted/custom icon; real Kickoff opened through OPM |
| C — Hints | Hidden versus shown, with equal geometry and all other menu settings unchanged |
| D — Icons | Hidden versus shown; same text, layout, hints, theme and geometry |
| E — Sizes | Small / standard / large icons; matching crop and layout |
| F — Density | Compact / standard / comfortable; equal canvas shows actual height differences |
| G — Geometry | Narrow / auto / wide; auto-fit / custom 360 logical pixels; actual geometry recorded |
| H — Appearance | Native Breeze Light / Dark, plus the implemented Aero Dark / Aero Light |
| I — Configure | General / Layout / Backups; launcher, appearance, icon size, keyboard/hover, built-in details, real app search, custom argv, submenu, power dropdown and recovery controls |
| J — Editing | Unlocked original, actual reorder, destination menu, moved entry inside submenu, Go Back and Save/Cancel; native Configure reorder too |
| K — EZ | Real ZIP checksum, runtime check, interactive confirmation and successful disposable installation; [unedited transcript](images/2.1/ez-transcript.txt) |
| Additional | Native Qt Widgets standalone with the same configured menu |

The standard menu image is reused for matching comparison states; density and
width have separate equal-canvas crops. The manifest stores settings per case,
raw-frame SHA-256, crop coordinates, final dimensions/bytes/SHA-256, runtime
versions, source commit and capture method. The CSV inventories every PNG.
Raw desktops and diagnostic logs remain outside the repository.

## Reproduce in a disposable container

Do not run these capture scripts against a working Plasma profile. They install
into their generated temporary HOME and launch their own private desktop. Build
and run only in a disposable container with no host display, D-Bus socket or
personal home mounted.

First check the approved native source boundary on the host:

```sh
python3 tools/showcase/check.py --baseline
python3 scripts/audit-repository.py
```

The [capture Dockerfile](../tools/showcase/Dockerfile) lists the Debian build,
Plasma, desktop-application and font dependencies. Its fresh image build was
qualified by rebuilding the native payload and capture driver, reproducing the
exact-default and Configure cases, and running the real EZ check/install. The
39 published images remain from the original isolated Debian capture sessions
recorded in the manifest. Exact recorded packages are above; later distro
snapshots may render differently and should get a new manifest.

Use an x86-64 Linux Docker host. In a managed network, preserve the supplied
HTTP(S) proxy and ensure its hostname resolves in Docker’s build namespace. The
recorded fresh build needed that existing proxy DNS mapping; it did not bypass
the managed proxy or change its allowed-host policy.

```sh
docker build -f tools/showcase/Dockerfile -t opm-showcase-debian .
mkdir -p work/showcase
chmod 755 work/showcase
docker run -d --name opm-showcase --network none \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/src:ro" -v "$PWD/work/showcase:/evidence" \
  opm-showcase-debian
```

Build the approved native payload and the separate capture driver. The source
commit below identifies the unchanged application code, not a later docs commit:

```sh
docker exec opm-showcase sh -lc '
  umask 022
  cmake -S /src -B /evidence/native-build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -DOPM_BUILD_PACKAGE=ON \
    -DOPM_SOURCE_COMMIT=4e11393c4d289c453044130d79dc54a23049c32c &&
  cmake --build /evidence/native-build --target native-package -j2 &&
  cmake -S /src/tools/showcase -B /evidence/driver-build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release &&
  cmake --build /evidence/driver-build --target opm-showcase-editor -j2
'
```

Capture all 24 cases, with up to two isolated seats at once. Output case
directories must not already exist. The installer rejects unsafe writable
ancestors; the scripts deliberately set a normal umask before creating them.

```sh
docker exec opm-showcase python3 /src/tools/showcase/run.py \
  --bundle /evidence/native-build/native-bundle \
  --editor-driver /evidence/driver-build/opm-showcase-editor \
  --output /evidence/captures --jobs 2

docker exec opm-showcase python3 /src/tools/showcase/installer.py \
  --bundle /evidence/native-build/native-bundle --output /evidence/ez
```

Each case gets a new X server and session bus. The mock system-bus address is
also explicitly exported into D-Bus activation, so an activated backend cannot
fall through to the container's system bus. KWin shortcuts and native capability
discovery become ready before capture. The fixture verifies real popup position;
the editor driver verifies the reorder and that Konsole is in the real app catalog.
No menu power command is activated.

On the host, with Pillow installed for lossless crop/encoding, generate new
review assets (use a separate output folder first):

```sh
python3 tools/showcase/export.py \
  --captures work/showcase/captures \
  --editor-captures work/showcase/captures/configure \
  --installer work/showcase/ez --output work/showcase/review-images
```

Inspect every image, then copy the reviewed outputs into `docs/images/2.1/`.
The committed default dump is not regenerated by export; obtain a replacement
from the corresponding native binary's `--default-config` if the source changes.
Run the asset and repository checks before proposing updated images. Remove only
the disposable container when finished; retain raw captures outside Git as needed.

## Validation and presentation review

`python3 tools/showcase/check.py` uses only Python's standard library. It checks
39 PNG identities/dimensions/hashes, the 4 MiB image budget, complete CSV inventory,
source/runtime consistency, zero power requests, the controlled setting differences,
equal hint/icon geometry, genuinely different width/density/height, adaptive flyout
direction, accessible clickable README images and successful EZ transcript steps.
The normal repository audit checks local links and Markdown anchors. Frozen
historical inventories are not regenerated.

`--baseline` additionally verifies both frozen CSV records against the approved
commit and confirms 219 runtime/test/build/legacy/historical-image paths remain
unchanged. This historical documentation-review boundary is separate from normal future
asset checks. CI runs the normal asset check alongside the existing portable
suite; application qualification remains enabled.

The [original showcase review record](maintenance/PHASE3-SHOWCASE.md) records local
and CI results, the GitHub review procedure, external-link limits and changed-file
inventory. [Final integration review](maintenance/FINAL-INTEGRATION.md) records the
current presentation acceptance status. The GitHub review requires `github.githubassets.com`
for actual site styling; the tool refuses unstyled pages instead of treating
missing CSS as a README layout defect. The capture infrastructure had preselection
setup issues (private activation environment, output permissions, panel spacers,
KDE menu prefix and one temporary driver lifetime bug); those were corrected and
the delivered captures/checks completed successfully. No application workaround
or production change was introduced.

## Limits and review findings

- This gallery is Debian/X11 at 100% scale, not a new Manjaro/Kubuntu physical
  qualification, GPU-compositor test or Wayland screenshot set.
- The private mocks advertise power capabilities for the flyout. They do not
  represent a real machine's suspend/hibernate authorization or hardware support.
- The simple clean panel has no task manager. These captures do not test or
  disprove the deferred translucent-taskbar ghosting issue.
- The native launcher picker currently lists other panel applets, including
  spacers, because its discovery is generic. Select the actual application
  launcher. That existing UX is visible in the screenshot and remains unchanged;
  narrower filtering can be reviewed separately.
- The full styled GitHub review needs its asset host allowed by the environment.
  Content/image decoding without CSS is not accepted as visual qualification.
- Capture provenance stays pinned to the original application source. Final
  integration preserves every image and its manifest; documentation and release
  evidence updates do not imply that the application UI was recaptured.
