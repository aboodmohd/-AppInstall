# AppInstall v1.1.2 — Release Acceptance and Exception Record

**Prepared:** 2026-11-13. **Decision:** PENDING OWNER REVIEW.
**Public version at preparation:** v1.1.1. **Do not tag or publish yet.**

## Maintenance-release scope

Fix the "The managed desktop entry is missing" error when a monitored
AppInstall desktop shortcut is moved from the KDE applications menu to the
configured Desktop directory. No intended feature changes to package
installation, native DEB/RPM isolation, source registration, the official logo,
or MIME defaults.

## Evidence verified by GitHub CI

- PR #45 delivered the hash-and-launch-ID guarded relocation fix and tests.
- PR #46 delivered v1.1.2 packaging and a dedicated upgrade/rollback test.
- Main merge SHA `5044b748846906bebdfd6d443ec1262e8d4d552a`
  passed 8/8 post-merge CI checks (Arch/Fedora tests, Wayland/KDE smoke,
  filesystem recovery, MIME, UI and unit tests).
- The branch-scoped disposable Arch CI upgrade from the published v1.1.1
  package to v1.1.2 and back preserved test account files and MIME defaults.
  **The branch-scoped step did not run on main's push event.**
- The exact prior post-merge package and SHA256SUMS were reviewed. A docs
  follow-up rebuild has a **different** source SHA and likely a different
  package hash; repeat exact-artifact verification on the final merge.

## Owner-reported real CachyOS KDE smoke test

- CLI and pacman reported `appinstall 1.1.2` / `appinstall 1.1.2-1`.
- Previously broken qBittorrent Desktop shortcut opened without using Repair.
- My Applications displayed qBittorrent as Installed, and Open succeeded.
- `pacman -Qkk appinstall` showed zero altered files.
- Application Diagnostics Open produced no new qBittorrent errors.
- Prior verified v1.1.1 rollback package and a partial application state
  backup were kept. A full live-system rollback was **not** performed.

This user-reported smoke test validates the previously broken *existing*
shortcut. It is not independent evidence of every way KDE copies/moves a new
shortcut, nor a re-execution of each backend's install/uninstall lifecycle.

## Limitations not eliminated by these tests

- New full fresh-install/manual four-format lifecycle (AppImage, Flatpak,
  DEB, RPM), Install-from-URL, and deletion/error path acceptance is not
  repeated for this version. Cross-distribution compatibility is not assumed.
- A KDE-mutated desktop file may differ byte-for-byte from the recorded file
  and intentionally fail verification. Unit tests reject changed and symlink
  cases; do not treat them as a complete live hostile-file exercise.
- AppInstall source/package redistribution dependencies and the unchanged
  icon license require final owner reconfirmation.
- No user-machine rollback, physical power-loss test or all-desktop acceptance
  is claimed. Distrobox is not a security sandbox.

## Release decision (owner action required)

**Option A:** Complete broader manual testing before publication.

**Option B:** Explicitly approve the limited, documented maintenance-release
scope and authorize publication of a separately verified final artifact.
This is an exception for scope of manual tests, **not** a waiver of final CI,
hash checks, unchanged asset permissions, or a release tag/source match.

Before any public tag or release, obtain a separate specific approval naming
the exact **final main commit**, final package SHA256 and asset inventory.
No signature, authorization or approval is implied by this document.
