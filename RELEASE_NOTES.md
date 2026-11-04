# AppInstall 1.0.0-rc.1 — Release Candidate Notes

**Status:** Candidate for testing only. **Not a published stable release.**
The published `v1.0.0-beta.1` release is unchanged. A stable `v1.0.0` tag
requires a separate final audit, release package checksum and explicit approval.

## Improvements since the beta

- Safer desktop registration with staged writes and a crash recovery journal
  for source upgrades; simulated disk-full and abrupt-exit tests cover rollback.
- Improved live refresh of the Installed Applications Manager and preservation
  of stale AppImage launchers if ownership records are missing.
- Hardened AppImage metadata parsing: reject escaping symlinks, sanitize
  potentially multiline launcher values, protect existing themed icons, and
  retain original AppImageLauncher payloads during migration.
- Verified upgrade, uninstall and data preservation flows in isolated HOME/XDG
  test directories; all four package formats exercised on a sampled CachyOS
  KDE setup.

## Packaging

The **testing-only** Arch/CachyOS build is
`appinstall-1.0.0rc1-1-any.pkg.tar.zst`. Obtain the exact candidate
package from the PR's GitHub Actions **Stable readiness compatibility**
artifact, then independently verify the SHA-256 reported in that same
workflow run. Do **not** install on a daily-use system without a backup.
Do not use the checksum in `PACKAGE_CHECKSUM.md`: it belongs to the
historical beta artifact, not this candidate.

- Source review branch: `release/v1.0.0-rc1-preparation`.
- This Arch package only registers an *available* desktop handler. A source
  user-level installation, unlike the package, may change MIME defaults.
- Candidate package versions do not guarantee future automatic upgrade order
  under pacman; manually check the installed package version before any
  transition to the eventual stable package.

## Supported workflows and limits

| Format | Implementation | Important limit |
| --- | --- | --- |
| AppImage | Copied to managed generation under `~/Applications` | Preview is passive, but executing third-party code is not inherently safe |
| Flatpak | Per-user Flatpak installation | Automatic update support applies to Flatpak only |
| DEB | Rootless Debian Distrobox installation | Applications requiring services, drivers or missing dependencies may fail |
| RPM | Rootless Fedora Distrobox installation | Containers are not security sandboxes |

The application may be opened through `appinstall --manage` and failures
reviewed through `appinstall --diagnostics`.

## Still required before stable v1.0.0

1. Final source and dependency/license review.
2. Clean installation and uninstall on a disposable CachyOS/Arch system,
   including preservation of existing user application data.
3. Real KDE Wayland dialog, Dolphin double-click, manager and launch checks
   after the candidate code is installed in the disposable test environment.
4. A physical/disposable low-space and interrupted-update verification.
5. Final version metadata, rebuilt stable-specific package, independent
   checksum/contents review, and explicit release authorization.

See `STABLE_RELEASE_AUDIT.md` and `STABLE_READINESS.md`.

## Historical beta

The previous release and its unchanged checksum manifest remain available as
`v1.0.0-beta.1` and `PACKAGE_CHECKSUM.md`. Do not re-tag the beta.
