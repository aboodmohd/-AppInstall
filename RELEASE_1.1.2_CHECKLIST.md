# AppInstall v1.1.2 — Release Approval Checklist

**Status on 2026-11-13: NOT TAGGED OR PUBLISHED.** Final owner approval is
required for publication. This checklist records *previously verified*
evidence; if the source or package changes, re-run final verification.

## Completed evidence for the merged bug-fix build

- [x] PR #45 merged: moved KDE desktop launcher handling with integrity checks.
- [x] PR #46 merged: v1.1.2 version and packaging preparation.
- [x] Main source `5044b748846906bebdfd6d443ec1262e8d4d552a`
      passed all eight post-merge GitHub CI checks.
- [x] Regression unit tests cover exact moved, altered and wrong-ID launchers
      and the user's configured XDG Desktop directory.
- [x] Arch CI checked 43 source digests, built the package as non-root,
      inspected package license/icon inventory, and performed package
      install/reinstall/remove.
- [x] PR #46 Arch CI verified published v1.1.1 -> candidate v1.1.2 ->
      v1.1.1 rollback in a disposable environment, retaining unrelated user
      files and MIME defaults. This branch-scoped step was not re-run on main.
- [x] A post-merge CI package from `5044b748` was independently checked
      against its SHA256SUMS and inspected for version and bundled files.
- [x] Owner reported a successful v1.1.2 installation on real CachyOS KDE:
      qBittorrent's previously broken Desktop shortcut opened without
      repair; My Applications showed Installed and Open succeeded;
      `pacman -Qkk appinstall` showed zero altered files;
      Diagnostics Open produced no new qBittorrent launcher errors.
- [x] The owner previously verified and saved the published v1.1.1 package
      for rollback and backed up selected AppInstall application records.
      This is not a full-system backup.

## Open checks and explicit decisions

- [ ] Re-run all eight CI checks on the **final source commit** after
      documentation clean-up is merged. Inspect that final CI package,
      SHA256SUMS, asset inventory and release verification record. Do not
      reuse `5044b748` artifact hashes for a rebuilt package.
- [ ] Confirm unchanged official logo and other redistributed content
      still have sufficient source/licensing authorization for release.
- [ ] Complete fresh on-device tests across AppImage, Flatpak, DEB, RPM,
      Install from URL, negative paths and full rollback **or explicitly
      accept** a narrower maintenance-release test scope. The owner-reported
      qBittorrent acceptance is not a complete four-format regression.
- [ ] Obtain **separate explicit owner authorization** to merge any final
      documentation PR.
- [ ] Obtain **separate explicit owner authorization** to create `v1.1.2`,
      publish the final approved release package, SHA256SUMS, and
      RELEASE_VERIFICATION.txt.
- [ ] After publication, verify public tag SHA, exact asset names, downloaded
      package hash, and that the existing one-command installer selects
      the newly published stable v1.1.2. Check rather than reinstall
      anything on the owner's system.

**User-system status:** AppInstall 1.1.2-1 is already installed and the
reported qBittorrent fix works. No additional install or rollback is
required for this release-preparation documentation task.
