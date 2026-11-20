# Preparing and publishing native 2.1.0

Phase 2 prepares this process; it does **not** authorize a tag, merge or release.
Cleanup review, Phase 3 documentation review, physical workstation acceptance and
explicit owner approval must precede final publication. The next public version
is **2.1.0 Stable**, not RC3. Keep v1.0.1, RC1 and RC2 unchanged.

## Source and qualification

Use a clean checkout of the exact reviewed commit. `native/VERSION` is `2.1.0`;
the native packager stamps the installed widget with that version. The source
widget's 1.0.1 metadata is retained for legacy compatibility tests. Root
`install.sh`/`uninstall.sh` only explain supported native installation.

The Tests workflow qualifies Manjaro, Debian 13 and Kubuntu 26.04 separately;
Arch is an additional compatibility fixture, not a fourth advertised EZ target.
Released 1.0.1/RC1/RC2 upgrade baselines stay pinned. All power endpoints are mocks.
See [testing](TESTING.md) and [compatibility limits](COMPATIBILITY.md).

Review branches produce `opm-2.1.0-review-<commit>` Actions artifacts. These are
review downloads with a retention period, not persistent public releases. To
collect completed same-run evidence locally, use a **new** output directory:

```sh
python3 scripts/stage-native-ez.py --evidence qualification-evidence \
  --output review-assets --commit "$(git rev-parse HEAD)"
```

`--publication` produces release content instead of `REVIEW-STATUS.md`. Collection
never publishes or tags. It verifies source archive equality with `git archive`,
package/bundle equivalence, sealed payload inventories, exact OS/version/CPU,
complete keyboard/greeter/distribution evidence, minimal runtime and installed
EZ activation, then reconstructs each EZ ZIP byte-for-byte from that committed
wrapper and qualified native bundle. It rejects a nonempty output directory.

## Complete stable asset set

- Three EZ ZIPs: Manjaro, Debian13 and Kubuntu26.04, x86_64.
- Three matching native `.tar.gz` bundles and the Manjaro `.pkg.tar.zst`.
- Source `.tar.gz` and an external `.sha256` for each of the eight archives.
- `SOURCE-COMMIT`, `RELEASE-NOTES.md`, `QUALIFICATION.json`,
  `RELEASE-MANIFEST.json` and aggregate `SHA256SUMS`.

The 21-file set is enforced, including matching distribution payload hashes in
qualification evidence. `QUALIFICATION.json` records actual package inventories,
mock request counts, held-key cases, greeter results and the qualification run.
It explicitly does not claim that automation establishes physical acceptance.
Native bundles contain a concise installation guide with source-pinned links,
license and current release notes. Historical reports remain in the source
archive rather than masquerading as current installed instructions.

## Approved stable publication (do not run during Phase 2)

After reviews and physical acceptance, merge only with owner approval. GitHub
must have the manually dispatched **Publish approved 2.1.0 Stable** workflow on
the default branch before it can be dispatched. Select the reviewed source ref,
enter its exact 40-character commit, type `Publish v2.1.0 Stable`, and affirm
physical acceptance. The workflow refuses a ref/approval mismatch, reruns the
complete qualification matrix and consumes only artifacts from that same run.
There is no push/tag/commit-message publication trigger.

`scripts/publish-stable-release.py` defaults to verification only. Actual
publication additionally requires `--publish`, an exact `--approved-commit` and
`--physical-acceptance-approved`. The workflow is its supported invocation.

The publisher refuses an existing stable tag or release, creates a draft with
Prerelease false, uploads exactly the qualified set, downloads every uploaded
asset and verifies bytes/checksums again. After verification it pins the tag to
the approved commit, rechecks draft state and assets, then publishes with
`draft=false`, `prerelease=false`, `make_latest=true`. It verifies GitHub's Latest
response. Published links are persistent GitHub Release downloads:

`https://github.com/BB7Networks/Open-Power-Menu/releases/tag/v2.1.0`

That URL is the planned final destination, not a claim that stable is published.

## Failure handling and readiness limits

A failed upload/download/verification leaves a draft, never a partial public
release. No automatic deletion, forced tags or overwrite is allowed. If a final
API call fails, inspect the release and tag before retrying: the tag may already
exist, or GitHub may have accepted publication despite a response failure.
Review and explicitly authorize any cleanup; the normal rerun refuses existing
state. Restore permissions/network access rather than treating HTTP errors as
an absent release.

Tests substitute a fake GitHub transport for missing approval, existing history,
403s, corrupt/incomplete assets, upload/download failures and concurrent metadata
or tag changes. These tests verify the mutation order and Stable/Latest flags;
they do not prove a live publication. No real publisher, tag or release is invoked
in this phase. Phase 3 and workstation acceptance remain release gates.

Archived [legacy](history/releases/publish-legacy-release.yml.txt) and
[prerelease](history/releases/publish-native-prerelease.yml.txt) publishers are
historical text. Their original tags retain the original workflows. See the
[Phase 2 review](maintenance/PHASE2-CLEANUP.md) for current CI evidence.
