# AppInstall v1.8.0 — Release candidate acceptance gate

> **Status: NO-GO until the owner explicitly approves each merge and the final publication.**
> Prepared 2026-11-17 from the stacked v1.8 development work. This is a
> **development-branch candidate**, not an installed upgrade or a published release.

## Change and approval boundary

| Order | PR | Purpose | Base |
| --- | --- | --- | --- |
| 1 | #78 | Read-only update discovery | main |
| 2 | #79 | Updates page and reviewed Flatpak updates | #78 branch |
| 3 | #80 | Reviewed DEB/RPM Distrobox updates | #79 branch |
| 4 | #81 | Reviewed eligible AppImage updates with recovery | #80 branch |
| 5 | #82 | Source-aware metadata and safe artwork | #81 branch |
| 6 | #83 | Categories and live Flatpak Featured shelf | #82 branch |
| 7 | #84 | Application Details page and approved visual redesign | #83 branch |
| 8 | Phase 8 draft PR | Candidate packaging and release readiness | #84 branch |

As checked on 2026-11-17, #78–#84 each had **13 successful CI
workflows**; all seven PRs remained drafts and unmerged. The user visually
accepted the Phase 6 Discover view and the revised Phase 7 Details UI on
CachyOS KDE. **CI success and visual feedback are not merge approvals.**

Merge only in the numbered dependency order after separate owner approval,
retesting the eventual integrated HEAD on main. **Never merge the stack in
reverse order or merge all eight just because CI passed.**

## Required go/no-go gates

- [x] Phase 6 Discover and Phase 7 redesigned Details preview user review.
- [x] Baseline stacked PR #84: 13/13 successful workflows, 752 tests run,
      two skipped and zero failures, on its checked commit.
- [ ] Phase 8 candidate HEAD: all required CI workflows must pass on the
      **exact** commit. Previous PR runs are not interchangeable.
- [ ] Verify PKGBUILD `pkgver=1.8.0`, appinstall CLI `VERSION="1.8.0"`,
      native package metadata, and portable archive version all agree.
- [ ] Verify one SHA256SUMS covers exactly the 4 expected v1.8.0 artifacts:
      `appinstall-1.8.0-1-any.pkg.tar.zst`,
      `appinstall_1.8.0-1_all.deb`,
      `appinstall-1.8.0-1.noarch.rpm`,
      `appinstall-1.8.0-portable.tar.gz`.
      No signed/developer provenance can be inferred from checksum validity.
- [ ] Verify the four assets from a single clean, **post-merge commit**,
      not PR synthetic merge SHA or outdated run. Record exact Git SHA, run
      ID, artifact SHA-256 hashes, and immutable destination tag.
- [ ] On a disposable host/profile, test clean install and upgrade from
      published v1.7.0 to candidate 1.8.0, and verify settings, MIME handlers,
      app records, favorites, and uninstall preservation. Repeat rollback
      checks before publication.
- [ ] Live **CachyOS KDE Wayland** checks: My Applications, Discover,
      categories, Featured, details/back/resize, Flatpak update rejection &
      acceptance, update progress and one-click actions. Do not perform a
      real package upgrade on the owner's main system without explicit consent.
- [ ] Live **DEB/RPM-owned containers** on an approved test fixture:
      exact provenance, simulated transaction, explicit confirmation, verified
      resulting version, cancellation/recovery and no host package change.
      Mock/CI container acceptance is not identical to live production use.
- [ ] Eligible AppImage update: actual supported upstream with
      `appimageupdatetool`, two reviews, checksum/format validation,
      atomic replacement and recovery. Also check manual-only fallbacks.
      Do not assert that all AppImages have automated updates.
- [ ] Source/user-installed portable archive test on at least one distinct
      desktop and architecture. Other distributions remain a **conditional
      portable option**, not guaranteed native/desktop support.
- [ ] Review and approve final v1.8 release notes and known limitations.
- [ ] Owner explicitly approves each stacked PR merge, final release
      commit, version tag, and publication. **None is implied here.**

## Supported packaging scope (not a universal compatibility promise)

| Artifact | Validated target family |
| --- | --- |
| pacman .pkg.tar.zst | Arch Linux / CachyOS |
| APT .deb | Debian 13, Ubuntu 24.04/26.04, Linux Mint 22 |
| DNF .noarch.rpm | Fedora 44 |
| Portable .tar.gz source | Other Linux desktops with supplied runtime prerequisites |

All four packaging formats have dedicated CI coverage on development
branches. For real-world acceptance, hardware, desktop environments,
container backends and optional system tools still matter.

## Release safety

The existing `.github/workflows/publish-v1.7.0.yml` is **locked to v1.7.0**
and must not be repurposed to publish 1.8. A new v1.8 publication gate
must be written and individually reviewed after the final verified build
has a fixed immutable commit and assets. It must require manual
`workflow_dispatch` and a separate explicit owner approval; it must
refuse duplicate tags/releases and verify exact artifact hashes, versions
and provenance before publishing. Do not enable a publish-on-push trigger.

For now the only permitted outputs are: a draft PR, a candidate package
artifact in GitHub Actions, and this acceptance document. No merge, no
tag, no GitHub Release, no automatic user installation or update.
