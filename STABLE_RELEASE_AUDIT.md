# AppInstall v1.0.0 Stable Release Audit

**Audit date:** 2026-11-04  
**Reference main commit:** `f96f5e5b03b98d0c3325522996defe87f7174bcc`  
**Current published release:** `v1.0.0-beta.1` (prerelease)  
**Release decision:** **NO-GO YET**. Complete the gates below and obtain explicit publication approval.

## Scope and evidence

Reviewed source registration, journaling and recovery, AppImage passive metadata,
legacy launcher migration, Arch PKGBUILD, CI configuration, release notes,
installation instructions and security limitations.

Previously verified on the main branch:

- Ubuntu/Arch/Fedora CI: 139 source tests on each distribution, two expected skips
  per environment; Arch `makepkg` build and install/reinstall/removal checks.
- Reported CachyOS KDE: AppImage, Flatpak, DEB and RPM double-click workflows,
  application launch, uninstall/reinstall, duplicate launcher prevention,
  automatic My Applications inventory refresh.
- Reported CachyOS isolated recovery test: eight tests passed, including simulated
  disk-full, failed uninstall, abrupt process exit and clean source registration.

These are samples, not proof of compatibility for every package or desktop.

## Security and data integrity findings

| Finding | Severity | Resolution/status |
|---|---|---|
| An untrusted AppImage desktop file can contain indented multiline metadata. Writing `StartupWMClass` directly into a new launcher can introduce unexpected desktop-file keys. | High | Fix proposed: flatten control characters and regression-test generated desktop entries. |
| Passive preview considered `.desktop` symlinks without checking whether their targets remain inside the unpacked AppDir. | Medium | Fix proposed: only parse files whose resolved paths remain inside the AppDir, including nested metadata fallback. |
| Legacy AppImageLauncher migration could remove its original AppImage payload while the documentation promised preservation. | High (user data) | Fix proposed: retire/back up the shortcut, **retain** the pre-existing AppImage file; regression test. |
| Multi-file source registration is not globally atomic while publishing. Recovery depends on the journal, source checkout and writable filesystem. | Residual | Already mitigated by staged fsynced writes, rollback, journal and fault-injection tests; keep documented and test real hardware. |
| Distrobox is not a security sandbox; untrusted software retains access allowed by the user's container configuration. | Residual | Preserve prominent user-facing warnings. Do not imply security isolation. |

## Release gates

- [x] All four package formats exercised on a real CachyOS KDE machine with a sample of applications
- [x] Installation, launch, uninstall, reinstall, no duplicates and manager-refresh smoke tests reported
- [x] Isolated source upgrade and recovery tests reported on CachyOS
- [x] Cross-distribution CI and Arch package checks passed for reference main commit
- [ ] Review and merge the AppImage metadata / payload preservation fixes after CI and real-device checks
- [ ] Actual clean installation and rollback on a spare Arch/CachyOS environment, not just an isolated HOME
- [ ] Real disk-full / abruptly terminated upgrade on a disposable filesystem and verify recoverability, permissions and MIME associations
- [ ] Recheck UI dialogs, Dolphin double-click and launch/failure diagnostics after final changes on KDE Wayland
- [ ] Validate support claims for GNOME/Xfce or explicitly limit stable compatibility claims to tested desktops
- [ ] Review third-party copyright/license notices, source provenance and package dependencies
- [ ] Produce `v1.0.0` version bump, updated changelog and stable-specific release notes
- [ ] Produce a fresh package and confirm its contents/checksums against the exact release commit (do not reuse beta checksum)
- [ ] Run CI on the final release commit and require explicit approval before tagging or publishing

## Release policy

This audit does not authorize a release, a tag, a merge, or an update to a
working user's installation. The previous beta release is unchanged.
