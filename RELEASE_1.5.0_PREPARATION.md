# AppInstall v1.5.0 — release preparation and verification gate

**Prepared:** 2026-11-15  
**Candidate baseline:** main at `7cd91148aa2d4dc749ee500af61d27a1caa2562e` (PR #69 merged).  
**Latest published stable:** [v1.4.0](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.4.0)
(tag resolves to `479d71f73e301936b7fc7b868028ff292e6e0fca`).  
**Candidate:** v1.5.0 (not tagged, not released).  
**Release decision:** HOLD until all final gates and owner approval.

## Scope

- [#66](https://github.com/aboodmohd/-AppInstall/pull/66): Qt Quick/QML My Applications redesign.
- [#67](https://github.com/aboodmohd/-AppInstall/pull/67): QML becomes the default, while `--widgets` preserves the original manager.
- [#68](https://github.com/aboodmohd/-AppInstall/pull/68): KDE Wayland QML runtime corrections for delegate indices, hover, icon paths, and text controls.
- [#69](https://github.com/aboodmohd/-AppInstall/pull/69): Status/Sort menus, QML interaction tests, and Qt `#AARRGGBB` hover color fixes.

## Evidence available before this release-preparation change

- [x] PR #69 at `61c02e3` passed **14/14 GitHub Actions jobs** and its unit
  suite reported **543 tests, 0 failures, 2 skipped**.
- [x] Owner confirmed on a real CachyOS KDE Wayland desktop that the yellow
  card highlight disappeared and Status/Sort controls worked.
- [x] Legacy Widgets fallback remains in source and automated coverage.
- [x] Published v1.4.0 is a separate, older release with its own assets; do
  not replace or re-label those assets as v1.5.0.

These are merge-candidate observations, **not** evidence for the new final
release-preparation commit's build output or a future GitHub release.

## Final v1.5.0 release gates — pending

- [ ] Review and merge the v1.5.0 version + documentation PR.
- [ ] Confirm `PKGBUILD pkgver=1.5.0` and `appinstall VERSION="1.5.0"`;
      `tools/build_deb.sh` inherits the package version from PKGBUILD.
- [ ] Run fresh **post-merge main CI** with all expected jobs successful,
      including Arch, Fedora, Debian-family, X11, Weston, virtual KWin,
      installer tests, desktop upgrade and filesystem recovery.
- [ ] Build Arch and Debian packages from the exact **final main source SHA**.
- [ ] Independently verify `b2sums`, `SHA256SUMS`, binary versions,
      package file lists, signatures/permissions (where applicable),
      `README`/release note content and exact source-to-asset provenance.
- [ ] Verify real CachyOS installed v1.5.0 package: Status/Sort menus with
      mouse and keyboard; no yellow hover; Widgets fallback; Diagnostics;
      existing installed apps/launchers/settings/MIME unchanged. Owner's
      prior candidate smoke is not a substitute for this exact package check.
- [ ] Decide whether to run fresh full AppImage/Flatpak/DEB/RPM lifecycle and
      URL installation tests or explicitly document the narrower scope.
- [ ] Reconfirm redistribution rights for project icon and dependencies;
      review security/known limitations. CI is not legal clearance.
- [ ] Confirm tag `v1.5.0` does not exist and prepare new **immutable**
      evidence: final commit SHA, package hashes and `SHA256SUMS`, plus
      `RELEASE_VERIFICATION.txt` if used.
- [ ] Obtain separate explicit owner authorization for public tag and release
      publication and verify both assets plus `releases/latest` afterwards.

## Expected assets (names only, no hashes yet)

- `appinstall-1.5.0-1-any.pkg.tar.zst`
- `appinstall_1.5.0-1_all.deb`
- `SHA256SUMS`
- Optional verification record tied to the exact final commit.

No package or checksum generated before the final approved build should be
misrepresented as a published release artifact. A new version tag and release
are intentionally not created as part of this preparation.
