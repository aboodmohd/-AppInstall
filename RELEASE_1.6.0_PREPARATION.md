# AppInstall v1.6.0 — Three-format release preparation

**Prepared:** 2026-11-15
**Source baseline:** main at `c7d6f5febda0a75b3dee9cd33a383cc93e1fa479` (PR #71 merged)
**Latest publicly published release at preparation:** v1.5.0
**Candidate tag:** `v1.6.0` (not published)
**Decision:** HOLD PUBLIC RELEASE until final artifacts, post-merge CI and
explicit owner authorization are recorded.

## Product scope and changes

- [PR #71](https://github.com/aboodmohd/-AppInstall/pull/71):
  Fedora 44 x86_64 native RPM and safe DNF installer workflow.
- Continue support for Arch Linux/CachyOS pacman and Debian 13,
  Ubuntu 24.04/26.04, Linux Mint 22 APT.
- Preserve default QML manager, Widgets fallback and existing app state.
- No promise of universal DEB/RPM third-party application compatibility,
  nor support for Fedora 43/45, RHEL or openSUSE.
- Keep published v1.5.0 tag, packages and `SHA256SUMS` unchanged.

## Evidence before this version bump (not final release evidence)

- [x] PR #71 feature head `fe44bcc9` had **11/11 successful workflows,
  17/17 jobs, 551 tests, 0 failures, 2 skipped**.
- [x] Fedora 44 CI built `appinstall-1.5.0-1.noarch.rpm`, installed
  through DNF, loaded `main.qml` offscreen, checked package integrity,
  removed the RPM preserving unrelated user files/MIME, and tested
  the installer against a simulated stable release.
- [x] Arch/CachyOS, Debian-family, X11 and virtual Wayland tests passed
  on the Fedora feature PR.
- [x] v1.5.0 QML UI passed owner-reported native CachyOS acceptance.

This is **prior-commit evidence**; a v1.6.0 RPM cannot reuse the earlier
test binary's hash.

## Final v1.6.0 gates — not yet complete

- [ ] Review PR and merge version/documentation changes to main.
- [ ] Confirm `appinstall VERSION="1.6.0"` and `PKGBUILD pkgver=1.6.0`,
      `pkgrel=1`, `rpm spec` placeholders, source checksums, and
      installer version independently 1.3.0.
- [ ] Obtain **post-merge main** CI success across every expected job.
- [ ] Build all three packages from **one exact final main commit**:
      Arch, Debian and Fedora. Preserve evidence of source-to-asset origin.
- [ ] Independently extract each package, inspect names, versions,
      permissions, dependencies and relevant QML/launcher/installer contents,
      and verify both generated and final release `SHA256SUMS` entries.
- [ ] Check current third-party/icon licenses, no unapproved bundled
      executables, known limitations and security review.
- [ ] Native CachyOS v1.6.0 package acceptance: QML dropdowns, neutral
      hover, Widgets fallback, existing apps and MIME unchanged.
- [ ] Native Fedora 44 graphical desktop acceptance; if unavailable,
      explicitly disclose CI-only support and do not claim physical
      Fedora GNOME/KDE testing.
- [ ] Check selected AppImage/Flatpak/DEB/RPM end-to-end cases, or
      explicitly document the narrower verification scope.
- [ ] Confirm `v1.6.0` tag absent, final owner approval for public
      tag/release, no overwrite of v1.5.0, and public downloads rechecked.

## Expected release assets (not yet published)

- `appinstall-1.6.0-1-any.pkg.tar.zst`
- `appinstall_1.6.0-1_all.deb`
- `appinstall-1.6.0-1.noarch.rpm`
- `SHA256SUMS`
- `RELEASE_VERIFICATION.txt` (optional evidence record)

**Do not claim success or hashes for new v1.6.0 packages until the exact
source and final release artifacts have been independently verified.**
