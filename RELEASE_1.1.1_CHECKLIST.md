# AppInstall v1.1.1 — Official Icon Release Checklist

**HOLD: NOT TAGGED OR PUBLISHED.** Merge, tag and publication require distinct
explicit owner approvals. This is preparation work only.

- Base main: `05c178cfdfac6410e7a78e11637909216ce5ab2f` (PR #43 logo integration)
- Candidate branch: `release/1.1.1-logo-prep`
- Candidate CLI version: `1.1.1`
- Candidate Arch package: `appinstall-1.1.1-1-any.pkg.tar.zst`
- Latest published stable: [v1.1.0](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.1.0)
- Separate one-command installer script: `install.sh` version 1.1.0,
  which continues to install latest **published** stable AppInstall.

## Branding scope

Official eight-size PNG logo: blue folder, white download arrow, green checkmark.
KDE desktop launcher, service menu, native Qt windows, and user/system hicolor
icon installation are in scope. Third-party application icons and all existing
AppImage, Flatpak, DEB/RPM, URL installation, diagnostics and management
behavior must remain unchanged. Canceled v1.2.0 UI redesign is excluded.

## Release gates (all unchecked until verified)

- [ ] All eight required CI checks pass on the final release-preparation commit.
- [ ] `python3 -m unittest discover -s tests -v` and shell syntax checks pass.
- [ ] `makepkg --verifysource` verifies all 43 sources and BLAKE2b digests.
- [ ] Disposable Arch build and package license/image evidence checks pass.
- [ ] Inspect eight icons at exact hicolor installed paths, dimensions,
      transparency, file permissions and icon theme lookup.
- [ ] Confirm KDE application launcher, taskbar/window and Dolphin integration
      with the new logo on a disposable/spare desktop or document owner waiver.
- [ ] Recheck icon at small sizes (16, 24, 32) and 256 in light/dark KDE themes.
- [ ] Test genuine published v1.1.0 → candidate v1.1.1 → v1.1.0 rollback
      in disposable Arch CI, preserving user files and MIME defaults.
- [ ] Review and explicitly approve redistribution rights for the owner-supplied
      logo; do not package screenshot evidence assets.
- [ ] Generate SHA256SUMS from the **exact final build**; inspect `pacman -Qip`
      and `pacman -Qlp` without installing on the owner's live system.
- [ ] Obtain **separate explicit owner authorization to merge** the preparation PR.
- [ ] After merging, verify post-merge CI and final source SHA.
- [ ] Obtain **separate explicit owner authorization to tag and publish** v1.1.1.

Expected eventual release assets (not yet generated): package, SHA256SUMS,
RELEASE_VERIFICATION.txt. Do not reuse v1.1.0 hashes or overwrite v1.1.0
release assets. No changes to the owner's installed AppInstall or managed apps.
