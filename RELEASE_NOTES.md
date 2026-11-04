# AppInstall 1.0.0 — Stable Release Notes (DRAFT, NOT PUBLISHED)

**Release status: BLOCKED pending final human acceptance and publication approval.**
This file describes the intended final `v1.0.0` build, not an already
published release. Do not create a tag, release, or overwrite the beta.

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

## Arch Linux / CachyOS candidate package

The **not-yet-published** Arch package, once the final build passes, is named:

`appinstall-1.0.0-1-any.pkg.tar.zst`

The exact file must be obtained from the verified GitHub Actions run for
the **final reviewed commit**, not from a previous RC/beta package. Compare
its `SHA256SUMS` manifest with the downloaded package using `sha256sum -c`,
and check its contents before installing in a **disposable or backed-up**
environment. `PACKAGE_CHECKSUM.md` describes a *historical beta package*
and must **never** be treated as the hash of this stable build.

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

## Before Stable 1.0 publication

- [ ] Obtain real spare-system CachyOS/KDE clean install, double-click,
      UI/launch, source upgrade, uninstall and recovery acceptance evidence
- [ ] Confirm contributor and screenshot/source-asset redistribution rights
- [ ] Review unresolved issues, security boundaries and dependency provenance
- [ ] Check final GitHub CI runs and inspect the exact package and manifest
- [ ] Obtain explicit approval for merge, then separately for tag/publication

Until then, this is **a draft stable build only**. The public release remains
`v1.0.0-beta.1`.
