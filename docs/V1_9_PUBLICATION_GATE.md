# AppInstall v1.9.0 — Publication gate

**Not yet published.** The latest public stable remains v1.8.0 until an explicit
release publication approval and successful manual workflow dispatch.

## Source and artifacts

- Accepted final source: merged `main` commit `850b01c1fbcef2fdaff447d617e3d9b0917002ab`
- Expected source tree: `26f4b01b34c5f337a01272c4ec0395cc8b246b5e`
- Main push candidate build: [run 44307640711](https://github.com/aboodmohd/-AppInstall/actions/runs/44307640711)
- Release artifact: `appinstall-v1.9.0-release-candidate` containing exactly
  four native/portable packages and `SHA256SUMS`
- Prior v1.8.0 → v1.9.0 → v1.8.0 native upgrade/rollback checks must pass.
- Gate requires 29 successful post-merge checks **on the exact pinned commit**.

## Manual publication (requires a separate explicit owner approval)

After this publication workflow has been reviewed and merged to `main`,
open **Actions → Publish AppInstall v1.9.0 (manual only) → Run workflow**.
Select `main`, enter `PUBLISH_APPINSTALL_V1_9_0` as approval input, then run.
The workflow checks the merged source SHA, tree, existing version/tag,
post-merge checks, source-pinned build run, assets and SHA256SUMS before
creating a stable release targeted at the pinned source commit.

If any gate fails, the workflow stops. Do not change the embedded source
commit or run ID to bypass a failure without independently rebuilding and
re-reviewing the release. The workflow does not run on pushes or PR events.
Do not dispatch it before the owner expressly approves v1.9.0 publication.

The resulting stable release would be available from the GitHub Releases
page and via the existing latest-stable one-command installer on supported
native distributions. **This PR does not publish the release.**
