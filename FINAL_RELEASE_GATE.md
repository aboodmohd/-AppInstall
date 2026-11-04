# AppInstall 1.0.0 — final release GO / NO-GO evidence

**Updated 2026-11-04. Decision: NO-GO for public Stable 1.0 until the
unverified acceptance and provenance items below are explicitly signed off.**

**Current main:** \`ba6ecd0a2ffba9d0663559ee9c5d140324d58600\`
(PR #12 merged; CLI version \`1.0.0\`; Arch \`pkgver=1.0.0\`).
**Only GitHub release currently published:** \`v1.0.0-beta.1\`.
The fact that the *source* says 1.0.0 does **not** mean stable is published.

## Machine-verifiable evidence already complete

| Gate | Evidence | Result |
|---|---|---|
| Final main CI | [Actions run 41822679574](https://github.com/aboodmohd/-AppInstall/actions/runs/41822679574) | Arch/Fedora checks green, including package build, package install/reinstall/remove, clean fresh user data-preservation test and license-path checks |
| Final main source test suite | GitHub Actions runs 41822679456 (Ubuntu), 41822679574 (Arch/Fedora) | Green; 147 cases per distribution, 2 skipped in each CI environment |
| Recovery | [Actions run 41822679539](https://github.com/aboodmohd/-AppInstall/actions/runs/41822679539) | Disposable tmpfs genuinely filled to ENOSPC; genuine SIGKILL after first replacement; next-process journal recovery; **not a power cut** |
| CachyOS checkout | User reported 147/147 Python tests passing from \`release/v1.0.0-final-preflight\` source with version output \`appinstall 1.0.0\` | Passed source tests without upgrading installed AppInstall |
| KDE UI smoke | User reported \`--manage\` and \`--diagnostics\` opened on KDE Wayland | Windows opened; does not prove all buttons, file associations or install workflows |
| Main package checksum | Same main Arch run 41822679574 | See below; generated and verified in runner |

**Current main CI build artifact** (NOT the earlier PR #12 build):

- Archive member: \`appinstall-1.0.0-1-any.pkg.tar.zst\`
- SHA-256: \`9feadd552cbb17967f9f34117f9f39eee5bede68e577442afed8d743e477aaf8\`
- Artifact: \`appinstall-package-ba6ecd0a2ffba9d0663559ee9c5d140324d58600\`
  in [Actions run 41822679574](https://github.com/aboodmohd/-AppInstall/actions/runs/41822679574).
- Also includes a \`SHA256SUMS\` text manifest, which \`sha256sum -c\` checked
  inside CI.

**Do not reuse the earlier PR candidate checksum** \`f7c309c6...\` or the
historical \`PACKAGE_CHECKSUM.md\` beta value. Rebuilding the same sources
may produce different compressed package bytes and a different SHA-256.
For a future published artifact, record and independently verify its *own*
SHA-256 and exact origin. These GitHub Actions artifacts expire after the
workflow's retention period.

## Source and image provenance: evidence vs permissions

1. The repository's \`LICENSE\` contains the MIT notice for
   \`Copyright (c) 2026 appinstall contributors\`.
   An MIT notice **does not by itself prove** that all code and imagery was
   authored by those contributors or received under compatible terms.
2. Eight screenshots appear under \`evidence/phase4/\`. The report
   \`evidence/phase4/RESULTS.md\` calls these app UI captures made using a
   headless Qt offscreen renderer and one real KDE Wayland manager window.
   Example history: [commit 49e4050](https://github.com/aboodmohd/-AppInstall/commit/49e4050ec4d3bf4c3d643d3445d8214c7ae5e095)
   added confirm/container screenshots together with \`tools/ui_evidence.py\`;
   [commit d24ce59](https://github.com/aboodmohd/-AppInstall/commit/d24ce5930ef55b5e5b82033689bc586a17eff421)
   added the live Wayland manager screenshot.
3. The eight screenshot PNGs are **not** listed as \`PKGBUILD\` source
   entries and are not installed by its \`package()\` function. However,
   they **are** in the public repository and will appear in default source
   archives: package exclusion is not the same as source redistribution
   clearance.
4. AppInstall invokes separately installed \`PySide6\`, \`flatpak\`,
   \`podman\`, \`distrobox\`, \`kdialog\`, \`unsquashfs\`, etc.; the
   Arch package does not vendor their libraries or executable binaries.
   Exact upstream notices and any other copied code/assets require a final
   owner review. See \`DEPENDENCY_LICENSE_AUDIT.md\`.
5. **Human confirmation required:** verify that the app source, screenshot
   captures, UI images and any copied snippets were authored by the
   contributor(s) or used with redistribution permission; note any required
   attributions. If unverified material is identified, remove or properly
   license it *before* the public stable release.

## Spare CachyOS / Arch KDE Wayland machine: manual acceptance

**DANGER: ONLY on a disposable VM/spare installation with a snapshot.**
Never copy installation/removal commands into the daily-use CachyOS host;
its AppInstall beta deployment, AppImage files, launchers, MIME defaults,
Distrobox containers and user data must remain untouched.

1. Create a VM snapshot. Verify this is a **fresh, separate system** and
   there is no existing source AppInstall under \`~/.local/bin\` and no
   installed \`appinstall\` pacman package. Record the system version,
   display/session (\`KDE / wayland\`), date, original MIME defaults, and
   whether optional dependencies are present. Save only redacted evidence.
2. From GitHub Actions **run 41822679574**, download the exact artifact
   named above into the VM and extract its ZIP in a fresh directory.
   Inspect the package contents with
   \`bsdtar -tf appinstall-1.0.0-1-any.pkg.tar.zst\`.
   Run \`sha256sum -c SHA256SUMS\`. Independently confirm the package's
   SHA-256 is the value listed above. **Stop if it differs.**
3. **In the VM only** install that package with pacman. Confirm
   \`/usr/bin/appinstall --version\` is \`appinstall 1.0.0\`, the
   MIT license is under \`/usr/share/licenses/appinstall/LICENSE\`,
   and the package was owned by pacman.
4. Under a non-root KDE Wayland session, open My Applications and
   Diagnostics. Confirm no crashes or missing modules. In Dolphin,
   select **Open With → AppInstall** for trusted local examples of
   AppImage, Flatpak, DEB and RPM. Review and cancel a confirmation,
   then repeat and approve install on a disposable test app; record
   whether launch, diagnostics, registry refresh and rollback work.
   DEB/RPM require Podman and Distrobox and may not support every app;
   test at least one representative package of each format or record
   that format as *not accepted*.
5. Test uninstall/reinstall and check for duplicate launchers, user
   data loss and changed MIME defaults. Confirm existing AppImage files
   and unrelated launchers/icons survive; any failing launch should
   show an actionable error rather than silent success. Check handling
   of a network failure and a missing runtime dependency.
6. On a **separate disposable** filesystem, exercise actual low-space
   and terminated source registration, restore adequate capacity, then
   verify next-run recovery of modules, file modes, MIME defaults and
   existing application data. The existing tmpfs CI provides automation
   evidence; do not deliberately fill a real production filesystem.
7. Remove only the **AppInstall pacman package in the VM**, verify that
   independent user application data and unaffected MIME choices
   remain intact, then revert the VM to its snapshot.
8. Record: OS/version, VM snapshot ID, downloaded artifact name and
   SHA-256, format/app names, pass/fail per step, screenshots or logs
   (redact personal identifiers), and person/date of sign-off.

## Public release decision

| Blocking requirement | As of 2026-11-04 |
|---|---|
| Final main build and CI | **PASS** on commit ba6ecd0a |
| Main build checksum and manifest | **PASS** in CI, specific to main build only |
| CachyOS isolated source tests and GUI opening | **PASS** (user-reported) |
| Clean package install on disposable Arch container | **PASS**, but not a desktop VM |
| Spare CachyOS KDE end-to-end install/upgrade/remove | **NOT VERIFIED** |
| Screenshot/code ownership and license provenance sign-off | **NOT VERIFIED** |
| Independent verification of exact asset to publish | **REQUIRED AT RELEASE TIME** |
| Explicit permission to publish/tag \`v1.0.0\` | **NOT GIVEN** |

**Decision: NO-GO.** A green CI run, a merge approval, and a stable-looking
version string are **not** permission to make a public release.

Once the human/VM blockers are resolved, verify the exact publication
artifact, update dated evidence, then request **explicit separate**
approval before creating the stable tag or GitHub release.
