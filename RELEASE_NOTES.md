# AppInstall v1.1.2 — Release Notes (Publication Pending)

**Status on 2026-11-13:** This release has **not** been tagged or published.
The latest public stable version remains
[v1.1.1](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.1.1).
The v1.1.2 bug fix and release-preparation commits are merged in `main`.

## Fixed — moved KDE desktop shortcut

AppInstall-managed shortcuts could fail with **"The managed desktop entry is
missing"** after the original `.desktop` launcher was moved out of the
applications menu and onto the KDE Desktop. The initial report involved
qBittorrent on CachyOS.

- Recognize a relocated desktop entry only within the user's configured XDG
  Desktop directory, requiring the original recorded SHA-256 and launch ID.
- Reject changed, symlinked, or unrelated launcher files rather than trusting
  arbitrary desktop-entry commands.
- Keep recognized moved managed AppImage and DEB/RPM launchers visible as
  Installed within **My Applications**.
- Preserve other application installation backends and AppInstall's official
  icon; there are no intentional changes to them in this maintenance release.

## Verification completed

- PR #45 (launcher fix) and PR #46 (release preparation) were merged.
- Eight of eight required CI checks passed on merged source commit
  `5044b748846906bebdfd6d443ec1262e8d4d552a`.
- Disposable Arch CI built and inspected the v1.1.2-1 candidate, checked
  source hashes and performed package install/reinstall/remove. PR #46's
  dedicated Arch job verified published **v1.1.1 → candidate v1.1.2 →
  v1.1.1 rollback** while preserving unrelated files and MIME defaults.
- The owner reported installing v1.1.2 on an actual CachyOS KDE desktop:
  the previously failing qBittorrent desktop shortcut opened without repair,
  its entry showed Installed in My Applications, **Open** worked, Diagnostics
  showed no new launcher errors, and `pacman -Qkk appinstall` reported
  zero altered files.
- These real-device results are owner-reported. They demonstrate this shortcut
  scenario, **not** a full fresh-install, four-format or hostile-shortcut
  manual acceptance run.

## Limitations and publication controls

- The byte-identical and matching-launch-ID requirement may not accept
  shortcuts changed by KDE or edited by the user. Modified launchers require
  review and should not bypass AppInstall's integrity checks.
- Full manual AppImage, Flatpak, DEB, RPM and Install-from-URL lifecycle
  regression testing has **not** been repeated for this bug-fix release;
  automated tests and previous-version behavior do not establish all-distro
  compatibility. Distrobox containers are not security sandboxes.
- Keep a known-good v1.1.1 package and a backup before upgrading. The
  separately versioned `install.sh` remains v1.1.0 and installs only the
  latest **published stable** AppInstall application.
- Proposed Arch/CachyOS package name: `appinstall-1.1.2-1-any.pkg.tar.zst`.
  Final exact package hash, release verification record, source commit,
  manual-test scope, and redistribution permissions require review.
  **If the source changes after a verified CI package, rebuild and re-verify
  that exact new artifact; earlier hashes must not be reused.**
- Do not create a `v1.1.2` tag or public release without the owner's
  **separate explicit publication authorization**.

---

# AppInstall v1.1.1 — Release Notes (published November 12, 2026)

[v1.1.1](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.1.1)
introduced the owner's official AppInstall blue-folder/download/checkmark
icon in eight hicolor PNG sizes (16, 24, 32, 48, 64, 128, 256, 512).
The application launcher, desktop service menu, and native PySide6 windows
request `Icon=appinstall`, preserving installed third-party application icons.

The published Arch/CachyOS package was
`appinstall-1.1.1-1-any.pkg.tar.zst` with SHA256SUMS and release verification
assets. It was built from exact source commit
`311a7785f050c0a04b6d03bfee7ddb46692eced0` after 8/8 GitHub CI checks.
The owner reported successful side-by-side logo appearance on real CachyOS KDE;
a full native system-package desktop acceptance test was not performed.
The official artwork's redistribution was explicitly authorized by its owner.

---

# AppInstall v1.1.0 — Release Notes (published November 12, 2026)

[v1.1.0](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.1.0)
introduced secure **Install from URL** through My Applications and the CLI.
It supports AppImage, Flatpak bundles/references/repositories, DEB and RPM,
with HTTPS download progress, cancellation, package preview, optional SHA-256
comparison, and separate installation confirmation.

Downloads validate TLS hostnames, public-IP connections and redirects; they
block private destinations and enforce size limits with temporary-file cleanup.
The downloader's SHA-256 is a transfer checksum, not proof of publisher trust.
DEB/RPM depend on rootless Distrobox, which is not a security sandbox.

The published Arch/CachyOS asset is
`appinstall-1.1.0-1-any.pkg.tar.zst`, with its own SHA256SUMS at the
[v1.1.0 release](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.1.0).
The source commit was `f93ccd9c9f2cd9f4a473f92fe2323e248fd8ddda`,
with 8/8 post-merge CI checks passing. Full physical/disposable CachyOS KDE
desktop end-to-end acceptance was not verified and was explicitly waived.
Only the published exact package matches its published checksum.

---

# AppInstall 1.0.0 — Release Notes

**Publication:** AppInstall 1.0.0 was published as the Stable release
[`v1.0.0`](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.0.0) on
2026-11-10 from the final reviewed commit `adf44eb` after explicit owner
approvals recorded in [issue #14](https://github.com/aboodmohd/-AppInstall/issues/14).
The earlier public beta [`v1.0.0-beta.1`](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.0.0-beta.1)
remains unchanged. This does not certify arbitrary compatibility.

AppInstall integrates AppImage, Flatpak, DEB and RPM installation with the
Linux desktop. The primary tested desktop is **CachyOS KDE Plasma Wayland**.
Support for every third-party package or Linux distribution is not guaranteed.

## Highlights

- **My Applications:** search and filter installed apps, view details, open
  managed applications, and access supported reinstall/uninstall/launcher
  repair actions.
- **Application Diagnostics:** monitored launchers and actionable logs for
  startup failures; a surviving process is not proof the GUI works.
- **Safe AppImage preview:** passive SquashFS inspection avoids running
  untrusted AppImage code merely to show metadata. Invalid external
  symlinks are ignored and embedded desktop-entry text is sanitized.
- **User data protection:** preserve original AppImageLauncher payloads,
  unrelated themed icons, and pre-existing application records.
- **Source update recovery:** stage/fsync files and use a journal for
  interrupted registration; simulated errors, real disposable tmpfs ENOSPC,
  and genuine SIGKILL/restart have been exercised in isolated tests.
- **DEB/RPM applications:** installed inside rootless Debian/Fedora
  Distrobox containers, not through native host package managers.
  Containers are **not** a security sandbox.

## Supported file types

| File | Installation backend | Important limit |
| --- | --- | --- |
| .AppImage | Managed application generations under ~/Applications | Passive preview requires squashfs-tools; running the app is still untrusted execution |
| .flatpak / .flatpakref | Flatpak per-user install | Downloads and runtime dependencies may be needed |
| .flatpakrepo | Flatpak per-user repository addition | Adds a repository, not an application |
| .deb | Distrobox Debian container | Not all packages work; drivers/services unsupported |
| .rpm | Distrobox Fedora container | Not all packages work; drivers/services unsupported |

## Arch Linux / CachyOS stable package

The published Stable package for the final reviewed commit is named:

`appinstall-1.0.0-1-any.pkg.tar.zst`

Only the exact asset from the published
[`v1.0.0` release](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.0.0)
matches its published `SHA256SUMS` manifest (verified independently before
publication); earlier RC/beta packages have different bytes. Compare the
downloaded file with `sha256sum -c`, and inspect it with `pacman -Qip`
before installing in a **disposable or backed-up** environment.
`PACKAGE_CHECKSUM.md` describes a *historical beta package* and must
**never** be treated as the hash of this stable build.

The system package registers AppInstall as an **available** MIME handler; it
does not set all user file-type defaults. Source registration does set
per-user defaults and retains the previous associations for restoration.
If you previously installed from source, check `type -a appinstall` first
because `~/.local/bin/appinstall` may shadow `/usr/bin/appinstall`.

## Dependencies

On Arch, the package declares Bash, Python, PySide6, coreutils and
xdg-utils as mandatory, with feature-specific optional packages:
Flatpak; Podman and Distrobox; squashfs-tools; KDialog or Zenity; FUSE2
and other notification or inspection tools. Runtime libraries required by
individual applications can still be missing. Read
`DEPENDENCY_LICENSE_AUDIT.md` and `KNOWN_LIMITATIONS.md` for caveats.

The package installs AppInstall's MIT notice under
`/usr/share/licenses/appinstall/LICENSE`. Other dependencies retain their
separate upstream licenses. Repackaging Qt/PySide6 or other libraries into
an all-in-one binary would require a separate licensing review.

## Fresh CachyOS/KDE Wayland acceptance — 2026-11-10

On an actual newly installed CachyOS KDE Wayland system, the owner successfully built and installed the 1.0.0-1 candidate from commit `9cf51696f574dd80f7adf9336c33adff79ed30f3`. Source regression: 190 tests (one skipped after installation, zero failures); both graphical windows launched; real AppImage (Hayase), Flatpak (Stremio), DEB (Mousepad), and RPM (OpenCode) lifecycle checks were **owner-reported** successful (44/44). Package remove/reinstall, retained settings/MIME/container names, benign invalid-input rejection, packaged MIT license, and launchers were also verified by terminal checks. See [fresh-system acceptance report](FRESH_CACHYOS_ACCEPTANCE_2026-11-10.md) and [issue #14](https://github.com/aboodmohd/-AppInstall/issues/14).

These checks concern a locally built and tested candidate built from the
same source as the released artifact; 44/44 lifecycle checks are
**owner-reported**. They do not establish arbitrary application
compatibility or an independent copyright/security certification.

## Evidence recorded before this preflight

- **CachyOS host:** 144 Python tests passed in the previous RC1 checkout,
  and the My Applications and Diagnostics windows were opened under KDE
  Wayland. This does not establish final 1.0.0 GUI acceptance.
- **Ubuntu, Arch, Fedora 44:** 147 test cases per environment in the
  latest prior cross-distribution CI, with 2 expected skips each and no
  failures, plus Arch package build/reinstall/removal.
- **Real disposable tmpfs:** filled to 0 bytes free, failed safely, then
  retried; genuine SIGKILL mid-publication recovered the journal on restart.
  No physical power-cut scenario was verified.
- **Clean Arch container:** pacman installation/removal preserved a
  separate test user's MIME defaults and application data.

The final `v1.0.0` source/package must be rebuilt and re-tested before
these results can be attributed to the final artifact.

## Before Stable 1.0 publication (all completed 2026-11-10)

- [x] Record owner-reported fresh CachyOS/KDE Wayland clean-install,
      Dolphin and real four-format install/launch/reinstall/removal acceptance
      and Pacman package lifecycle evidence (see 2026-11-10 report)
- [x] Decide whether additional missing-dependency/network-failure and
      source-registration fault recovery manual tests are required — decision:
      confined CI fault-recovery coverage plus owner-recorded invalid-input
      behavior is accepted for v1.0.0; extension tracked without blocking
- [x] Record owner's original-source and eight-screenshot permissions declaration
      in issue #14 (already completed)
- [x] Confirm no additional externally sourced snippets/assets need attribution,
      or document their permission and required notices (owner confirmation, issue #14 2026-11-10)
- [x] Review unresolved issues, security boundaries and dependency provenance
      (no open issues besides #14; single-author provenance recorded; DEPENDENCY_LICENSE_AUDIT.md updated)
- [x] Check final GitHub CI runs and inspect the exact package and manifest
      (7/7 on `adf44eb`; package + manifest re-verified independently)
- [x] Obtain explicit approval for merge, then separately for tag/publication
      (both granted 2026-11-10, recorded in issue #14)

Published on 2026-11-10 as
[`v1.0.0`](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.0.0).
The earlier public release remains `v1.0.0-beta.1`, unchanged.
