# AppInstall v1.9.0 — Premium UI release candidate gate

**Status: NO-GO for publication.** Preparation branch: `release/v1.9.0-premium-ui-prep`.
Source baseline: accepted UI merge `ad6e6ac3c625ced685bd283f05291143806f6452` on `main`.
Current published stable: [v1.8.0](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.8.0).

## Scope and owner decisions

- UI/UX-only release based on reviewed and merged PR #89; preserve all existing
  Python, QML, Bash, AppImage, Flatpak, DEB and RPM workflows.
- Proposed version: `1.9.0`, `pkgrel=1`; do **not** publish or merge the
  candidate merely because its tests pass.
- The separately versioned `install.sh` installer resolves the latest stable
  GitHub release; no need to change the installer itself to 1.9.0.
- No release publication workflow is enabled in this preparation PR.

## Acceptance checklist

- [x] UI redesign merged via PR #89 and accepted on CachyOS KDE.
- [x] v1.8.0 is already published; do not overwrite its tag or artifacts.
- [x] Candidate `appinstall`, `PKGBUILD`, release notes, changelog and
      release-candidate workflow use proposed v1.9.0 version.
- [x] PKGBUILD local-source BLAKE2b checksums refreshed for changed package
      source files (CI still needs to verify them independently).
- [ ] Run all automated tests on the **exact** candidate commit; record run IDs.
- [ ] Build and validate four artifacts with exact names:
      `appinstall-1.9.0-1-any.pkg.tar.zst`,
      `appinstall_1.9.0-1_all.deb`,
      `appinstall-1.9.0-1.noarch.rpm`,
      `appinstall-1.9.0-portable.tar.gz`.
- [ ] Verify exactly one SHA256SUMS with four entries; verify downloaded
      candidate artifacts again (archive integrity is not publisher signature).
- [ ] Verify packaged QML is the approved redesign; launch GUI with installed
      artifacts in disposable Arch, Debian 13, Ubuntu 24.04/26.04, Mint 22,
      and Fedora 44 CI environments, distinguishing virtual vs real desktops.
- [ ] Run v1.8.0 -> v1.9.0 -> v1.8.0 upgrade/rollback tests in disposable
      environments: settings, favorites, application records, MIME associations,
      launchers, no lost data or unexpected package actions.
- [ ] Validate portable source updates in a disposable non-native environment;
      never replace a host-native package with portable files.
- [ ] Inspect source/license/provenance and the final release notes.
- [ ] Owner approves candidate PR merge, exact post-merge commit, and **separate**
      tag/publication in an explicit go/no-go decision.

## Publication boundary

An automatically passing release-candidate job only builds review artifacts.
`publish-v1.7.0.yml` is locked to its older tag, and must not be altered or
used for v1.9.0. A newly reviewed, manual-only publication path must refuse
existing tags/releases, confirm exact build commit, archive names and SHA256SUMS,
and publish only after the owner explicitly authorizes it.

No GitHub release, git tag, package install or merge is performed by this plan.
