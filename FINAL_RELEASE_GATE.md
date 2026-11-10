# Release preparation status — 2026-11-10

**Stable 1.0: HOLD / NO-GO.** The independent candidate artifact
verification and native fresh-CachyOS acceptance are recorded in issue #14,
but neither grants publication permission.

Main after PR #34: `8b99a0c06de473ec04d56495ef58d44ff93512f1`
with seven green CI jobs. Independently inspected candidate from
[GitHub Actions run 42800326093](https://github.com/aboodmohd/-AppInstall/actions/runs/42800326093):
ZIP SHA-256 `07bafdbfa3296f3a6460e14d76a18ed5184153710bc7513c52f5783472f0eeaf`;
inner package SHA-256
`d00489fcc668fbb6bcfa11a1a5f82e1ada450b8e7110c2c9ff8a8bcf4688d900`.
Both match their corresponding metadata/manifest. This is a historical
candidate hash, **not** the hash of a future rebuilt release.

Technical third-party review is recorded in DEPENDENCY_LICENSE_AUDIT.md:
no obvious bundled third-party executables/art was found in the inspected
source package; this does not close the human permissions and notice check.
Any prepared release-note edits require a new package and independent
checksum verification. Separate owner approval is required before stable
tagging/publication. No installed application is changed by this review.

---

# Fresh CachyOS acceptance addendum — 2026-11-10

**Fresh installed-system acceptance was performed after the older HOLD addenda below.** The repository owner installed CachyOS KDE Wayland cleanly, verified the exact local candidate from source commit `9cf51696f574dd80f7adf9336c33adff79ed30f3`, reported 44/44 real-app checks across AppImage/Flatpak/DEB/RPM, and passed the local Pacman install/remove/reinstall, user-settings and MIME comparisons, invalid-input tests, and package payload/license inspection. Full detailed scope and limitations: [fresh-system acceptance report](FRESH_CACHYOS_ACCEPTANCE_2026-11-10.md); owner terminal results are logged under [issue #14](https://github.com/aboodmohd/-AppInstall/issues/14).

**This supersedes the older claim below that a separate fresh CachyOS install had not been completed.** The fresh-host test confirms an important manual gate, but does not certify all applications, missing-dependency/network-failure behavior, physical power interruption or third-party rights. The owner-source and eight-screenshot ownership declarations have already been recorded; an independent third-party notice/asset review still needs sign-off.

**Release decision remains HOLD / NO-GO.** Before tagging or publishing Stable v1.0.0, complete the remaining applicable security/license review, ensure final release notes and audit match actual coverage, verify fresh CI and exact uploaded artifacts against the **final reviewed commit**, and obtain the owner's explicit separate publication approval. The locally built test package SHA-256 is `14cab16fe1dc3cc63c11526184b948deca2755499272830dcde48fa993b2a5e3`; it must **not** be assumed to be the final published asset checksum.

---

# AppInstall 1.0.0 — final release GO / NO-GO evidence

## Current release-gate addendum — 2026-11-06

**Decision: HOLD / NO-GO. Do not create a `v1.0.0` tag or publish Stable without a new, explicit owner instruction.** The owner expressly required clean testing on a **separate, freshly installed CachyOS KDE/Wayland system** before release ([issue #14: release hold](https://github.com/aboodmohd/-AppInstall/issues/14#issuecomment-6657128604)). Physical tests on the owner's *existing* dual-boot installation and tests on a live USB are useful evidence but do **not** meet that requirement.

### Current code, CI and exact candidate (supersedes older reference hashes below)

| Item | Verified status |
| --- | --- |
| GitHub `main` reference | `2737fadd360ab1089b0382f65e6ea32ee0acffb6`, after merged PR [#30](https://github.com/aboodmohd/-AppInstall/pull/30) |
| CI on that **main** commit | **7/7 PASS**, including Arch, Fedora, Ubuntu unit tests, GUI, Dolphin MIME, native Weston/Wayland smoke, and disposable tmpfs recovery |
| Arch artifact and workflow | `appinstall-package-2737fadd360ab1089b0382f65e6ea32ee0acffb6`, [Actions run 42208369538](https://github.com/aboodmohd/-AppInstall/actions/runs/42208369538), artifact ID `13497641722`; expires 2026-11-20 |
| Artifact ZIP digest | SHA-256 `af78db5c62f577e7e93b269e844fdc28a30439336911d5bda2cb29cce1139ed3` |
| **Package** digest (not ZIP) | `appinstall-1.0.0-1-any.pkg.tar.zst`: SHA-256 `35209d89dc5aa86fecf0ed80bd19697814f62d1901b9dbe96460cbb0725a9e0d`, matched bundled `SHA256SUMS` and CI evidence JSON on independent inspection ([issue #14 evidence](https://github.com/aboodmohd/-AppInstall/issues/14#issuecomment-6683585053)) |
| Asset classification | **`PUSH_CI_TEST_ONLY` / NO-GO**, not a release asset or owner authorization |

The 2026-11-06 package was inspected for metadata, the packaged MIT notice, source modules, and both absolute `/usr/bin/appinstall` desktop launchers; no third-party runtime binaries or repository screenshots were identified in the package payload. These are **technical observations**, not independent copyright or legal clearance. **If this documentation or any other source changes and produces a later commit, obtain and verify that later build's specific artifact rather than reusing this digest.**

### Current physical-host and live USB evidence

- Existing installed CachyOS KDE Wayland host: `appinstall 1.0.0` from `/usr/bin/appinstall`, `pacman -Qkk appinstall` reported **42 total files, 0 altered**; My Applications and Application Diagnostics windows opened.
- Owner-reported launch smoke: representative installed **AppImage, Flatpak, DEB and RPM** applications all opened (4/4). This is not arbitrary package compatibility.
- Isolated source regression run: **171 tests, OK, zero skips**, on the local test-patched checkout; PR #30 merged that test correction and all seven CI jobs passed again on `main`.
- Guarded real UI interaction on the existing host: review **Cancel** did not invoke the mock Flatpak installer; forced backend installation error returned code `1` with the expected diagnostic. Neither operation installed a real application.
- Disposable AppImage backend test: synthetic non-launchable image installed, reinstalled without duplicate menu entries, removed, and preserved the downloaded source. This is metadata/registry lifecycle evidence, **not a real AppImage launch**.
- Separate CachyOS **live USB**: exact earlier candidate `69302aa` checksum/extraction/Bash syntax/CLI verified; no live-session pacman installation or end-to-end GUI/package lifecycle was completed.
- [Issue #14](https://github.com/aboodmohd/-AppInstall/issues/14) contains dated owner-reported terminal outputs and distinctions between tested and untested behavior.

### Remaining blockers — keep all unchecked until verified

- [ ] **Separate freshly installed CachyOS/KDE Wayland**: actual clean pacman package install, dependency resolution, Dolphin four-format review/install/launch, manager/diagnostics, reinstall and removal, data/default MIME preservation, and recovery checks. A disposable system with backups is required; do not erase/modify the owner's daily-use system to satisfy this gate.
- [ ] **Third-party notice/redistribution check:** owner declared the AppInstall source original and eight repository screenshots owner-created/authorized ([issue #14 declaration](https://github.com/aboodmohd/-AppInstall/issues/14#issuecomment-6656840134)); independent code/asset inspection, external snippets and any applicable attribution/licensing obligations remain separate and must not be claimed complete.
- [ ] **Final publication artifact:** recheck *the exact files to be uploaded* and their SHA-256, code commit, license and complete CI on the final candidate; a CI artifact is not automatically the published file.
- [ ] **Separate owner approval** to create/push the stable tag and publish `v1.0.0`, only after the preceding gates.

**Historical material follows.** Old checksums, references to PR status, and dated gate counts below describe prior candidate snapshots; do not interpret them as the current release decision.

---

**Updated 2026-11-04. Decision: NO-GO for public Stable 1.0 until the
unverified acceptance and provenance items below are explicitly signed off.**

**Historical baseline from PR #12:** ba6ecd0a2ffba9d0663559ee9c5d140324d58600 (CLI 1.0.0; pkgver=1.0.0). **That commit is not current main.** Check the live GitHub main branch for the latest commit and CI artifact.
**Only GitHub release currently published:** \`v1.0.0-beta.1\`.
The fact that the *source* says 1.0.0 does **not** mean stable is published.

## Fresh CI candidate evidence (one bundle per build)

The package checksums and links later in this document are **historical**
and must not be used to identify a newer build. On each new Arch CI run,
the GitHub Actions artifact now includes a generated acceptance bundle:

- Exact package filename, SHA-256, checkout commit and workflow run URL
- For pull requests, the separate PR branch HEAD and GitHub's synthetic merge
  checkout commit (which can be different): PR artifacts are test builds only
- candidate-evidence.json and MANUAL_ACCEPTANCE.md with manual gates PENDING
- SHA256SUMS generated and verified against that exact package

This bundle is **not a signature, independent CachyOS verification or
copyright sign-off**. In a disposable VM or spare system, independently
compute SHA-256 and compare it to the matching CI run before acceptance.
Stable 1.0 remains NO-GO without explicit separate publication approval.

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
