# AppInstall v1.8.0 — Draft release notes (UNPUBLISHED)

> This document describes proposed v1.8.0 functionality on the stacked
> development branches. **Do not publish or present it as a released build**
> until final package acceptance and owner approval.

## Highlights

**Application Updates** — A dedicated Updates page for managed
Flatpak, AppImage, DEB and RPM applications. A source-qualified read-only
engine reports availability, uncertainty and actionable/manual states.
Updates require explicit review rather than automatic system-wide upgrades.

- **Flatpak:** opt-in, one-app-at-a-time updates tied to the exact user
  ref, remote origin and target commit, with confirmation and verification.
  Dependency/related upgrades are not silently included.
- **DEB/RPM:** for verified AppInstall-owned Debian 13 and Fedora 44
  Distrobox records, package-specific APT/DNF5 simulation is shown before
  approval; application updates occur in existing owned containers,
  not through an unreviewed host-wide package upgrade.
- **AppImage:** supported embedded zsync metadata and a separately
  installed `appimageupdatetool` enable reviewed download/replace with
  staging, format checks, atomic replacement and a recovery copy.
  Unsupported AppImages remain manual. zsync is **not a developer signature**.

**Discover improvements** — Source-qualified app metadata and locally
validated PNG/WebP artwork with safe fallbacks; optional developer,
license, version, category, homepage and AppStream IDs. Filter by real
provider categories and browse a horizontal **Featured** shelf backed
by Flathub's live popular collection, never fake popularity claims for
DEB/RPM or AppImageHub.

**Application Details** — A dedicated, responsive, centered application
page with icon, descriptive text, metadata and source identity, a clear
Install/Downloads or Managed state, optional publisher website, and Back
navigation to Discover. Existing install reviews remain in place.
Missing fields are presented as unavailable rather than fabricated.

## Packaging

Proposed native assets for Arch/CachyOS, Debian 13, Ubuntu 24.04/26.04,
Linux Mint 22, and Fedora 44, alongside an opt-in portable source bundle
for other supported runtimes. Verify exact generated filenames,
SHA256SUMS and test fixtures from a **final merged commit** before listing
any binaries on a public release page.

## Safety and limitations

- Not every app supplies developer metadata, verified artwork or an
  AppStream record. A letter fallback is expected in some catalogs.
- Flatpak, DEB/RPM and AppImage update mechanisms have different trust
  and dependency boundaries. Do not claim full universal update support.
- Distrobox is **not** a security sandbox. DEB/RPM application integration
  depends on the host/container and is not universally supported.
- Support for other distributions or desktop environments through a
  portable archive is conditional on local Qt/Python and integration
  prerequisites; native one-command installer is restricted to verified hosts.
- Preserve installed app data, favorites, existing user settings and explicit
  uninstall safeguards. Never promise zero migration risk without actual
  upgraded-device testing.
- These notes are **draft** until owner-approved release acceptance.
