# AppInstall v1.1.2 — KDE Desktop Shortcut Fix Release Checklist

**PREPARATION ONLY: NOT TAGGED OR PUBLISHED.**
Merge and publication require separate explicit owner approvals.

- Base main commit: `8e6ff8182f24194782672d887df81c435922015f`
  (PR #45 merged; 8/8 post-merge checks passed).
- Preparation branch: `release/1.1.2-kde-shortcut-fix`
- Candidate CLI and Arch package: `1.1.2`, `appinstall-1.1.2-1-any.pkg.tar.zst`
- Latest published stable: [v1.1.1](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.1.1)
- Independent one-command installer: `install.sh` v1.1.0 (unchanged).
- No change to owner's installed AppInstall, source worktrees, managed applications,
  official logo, or existing v1.1.1 release.

## Required release gates

- [ ] Eight required GitHub CI checks pass on the release-preparation PR HEAD.
- [ ] Unit tests (including the new move/altered launcher/desktop location cases)
      and bash syntax checks pass.
- [ ] All 43 PKGBUILD source hashes verify; build `1.1.2-1` as a non-root
      Arch CI user; package contains exactly expected files/license/icons.
- [ ] Disposable Arch container verifies the published v1.1.1 package
      against its own published SHA256SUMS, upgrades to candidate v1.1.2,
      rolls back to v1.1.1 and confirms unrelated files and MIME defaults
      were preserved.
- [ ] Manual test on actual CachyOS KDE: install/use a candidate only with
      an explicitly approved testing method; move a monitored launcher
      from menu to Desktop, then open it successfully; confirm other apps
      and existing managed records are unaffected.
- [ ] Confirm modified launcher, symlink and unrelated launcher remain
      untrusted; changing a desktop entry intentionally requires review.
- [ ] Check packaged default installer/version behavior and retention of
      official icon and user MIME association handling.
- [ ] Explicit approval to merge release preparation PR into main.
- [ ] Verify all eight post-merge CI checks on exact final main commit.
- [ ] Independently verify exact package hash, provenance, asset inventory,
      and draft release content.
- [ ] Obtain separate explicit owner approval to tag and publish v1.1.2.

**Owner acceptance:** a passing automated test of exact moved launchers
does not prove every KDE drag-and-drop mutation. Retest on real hardware.
Never publish a PR artifact, draft asset or candidate as stable without
post-merge verification and owner authorization.
