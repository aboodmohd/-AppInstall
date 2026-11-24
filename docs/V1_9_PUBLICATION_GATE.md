# AppInstall v1.9.0 — Publication gate (completed)

**Published:** [v1.9.0](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.9.0)
on 2026-11-18 from merged `main` commit `850b01c1fbcef2fdaff447d617e3d9b0917002ab`.
This document records the publication gate that was completed.

## Source and artifacts

- Accepted final source: merged `main` commit `850b01c1fbcef2fdaff447d617e3d9b0917002ab`
- Expected source tree: `26f4b01b34c5f337a01272c4ec0395cc8b246b5e`
- Main push candidate build: [run 44307640711](https://github.com/aboodmohd/-AppInstall/actions/runs/44307640711)
- Release artifact: `appinstall-v1.9.0-release-candidate` containing exactly
  four native/portable packages and `SHA256SUMS`
- Prior v1.8.0 → v1.9.0 → v1.8.0 native upgrade/rollback checks passed in disposable hosts.
- Gate requires 29 successful post-merge checks **on the exact pinned commit**.

## Manual publication (completed after explicit owner approval)

The reviewed workflow was dispatched on `main` with the approval input below.
The original procedure is retained for the record:

After this publication workflow has been reviewed and merged to `main`,
open **Actions → Publish AppInstall v1.9.0 (manual only) → Run workflow**.
Select `main`, enter `PUBLISH_APPINSTALL_V1_9_0` as approval input, then run.
The workflow checks the merged source SHA, tree, existing version/tag,
post-merge checks, source-pinned build run, assets and SHA256SUMS before
creating a stable release targeted at the pinned source commit.

If any gate fails, the workflow stops. Do not change the embedded source
commit or run ID to bypass a failure without independently rebuilding and
re-reviewing the release. The workflow does not run on pushes or PR events.
Publication proceeded only after the owner expressly approved v1.9.0.

The resulting stable release is available from the
[v1.9.0 release page](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.9.0)
and via the existing latest-stable one-command installer on supported native
distributions. **This documentation change does not publish another release.**
