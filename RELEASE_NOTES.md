# AppInstall v1.1.1 — Release Candidate (NOT PUBLISHED)

**Preparation only.** AppInstall v1.1.1 is not tagged or published. The
latest publicly available stable release remains
[v1.1.0](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.1.0).

## What's new — official AppInstall icon

- Ships the owner's selected blue-folder / white-download-arrow / green-checkmark
  logo in eight transparent PNG sizes: 16, 24, 32, 48, 64, 128, 256 and 512.
- KDE application launcher, AppInstall-owned desktop actions and native
  PySide6 windows request `Icon=appinstall` from the theme.
- Arch/CachyOS packages install icons in system hicolor directories; source
  installs track per-user icon files in the existing recovery/uninstall journal.
- No change to third-party managed application icons. All existing AppImage,
  Flatpak, DEB/RPM, Install from URL and diagnostics functionality is retained.

## Packaging, acceptance and limitations

Proposed Arch/CachyOS candidate: `appinstall-1.1.1-1-any.pkg.tar.zst`.
The separate one-command installer `install.sh` remains version 1.1.0 and
continues to select only the latest **published stable** application release.
The published v1.1.0 package must not be replaced or overwritten.

The eight official hicolor PNGs are the only permitted packaged PNG assets;
both release evidence gates reject unapproved images and screenshot evidence.
Rights to redistribute the approved artwork require explicit owner sign-off.
Automated CI and disposable package testing do not substitute for an actual
CachyOS KDE Plasma Wayland visual/functional acceptance check.

**Release gates:** verify the final source commit, build and inspect the exact
candidate package, independently generate its SHA-256 manifest, complete
KDE/app icon and upgrade/rollback acceptance, review rights and obtain separate
explicit owner approval before tagging or publishing v1.1.1.
No release artifact or checksum is claimed in this draft.

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
