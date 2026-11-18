# AppInstall v1.9.0 — Premium UI/UX Release Candidate (NOT PUBLISHED)

This document describes a **candidate**, not a published GitHub release. The current
published stable version is **v1.8.0**. Do not treat draft PR artifacts as final
downloadable packages or upgrade the owner's daily-use installation without consent.

## What's new

- **One uncluttered app header:** My apps, Discover, Updates, Menu and Install app
  occupy one consistent horizontal navigation row.
- **Cleaner My Applications:** compact icon/name/format rows, Installed and
  Needs attention grouping, one Open or Review action, and contextual Details,
  Favorites, repair and removal actions. Missing launchers never enable Open.
- **Refined Discover Apps:** prominent search, source tabs for Flatpak,
  AppImage, DEB and RPM, responsive catalog cards, source-specific category
  and sorting controls, Featured pages showing three cards at a time,
  keyboard-accessible Previous/Next, and preserved View more pagination.
- **Clearer Updates:** model-backed summary counts, compact per-app update
  rows and one status filter. Existing opt-in review, cancellation and
  confirmation rules remain unchanged.
- **Layout reliability:** first catalog load/search/source/category changes
  begin at the top; pagination and metadata refreshes preserve the user's
  current scroll offset. Separate scrollbar gutters keep cards and actions
  unobstructed. Compact aligned self-update notice is distinct from warnings.
- **Desktop polish:** coherent dark/light palettes, system fonts, reduced-motion
  behavior, accessible keyboard interactions and responsive Qt Quick layouts.

No Rust rewrite, new package-install backend, new privilege boundary or
automatic update policy is part of this release.

## Candidate artifacts — NOT YET PUBLISHED

- Arch Linux / CachyOS: `appinstall-1.9.0-1-any.pkg.tar.zst`
- Debian 13 / Ubuntu 24.04 and 26.04 / Linux Mint 22: `appinstall_1.9.0-1_all.deb`
- Fedora 44: `appinstall-1.9.0-1.noarch.rpm`
- Other environments with portable prerequisites: `appinstall-1.9.0-portable.tar.gz`
- A single `SHA256SUMS` manifest must verify all four files.

The portable source bundle is **not** a universal binary; it requires host
Python/Bash/XDG/Qt dependencies. DEB/RPM applications still use AppInstall-
managed rootless Distrobox containers, which are **not** security sandboxes.

## Evidence and remaining release gates

- Source: redesign PR #89, merged to main as `ad6e6ac3c625ced685bd283f05291143806f6452`.
- Before this version bump: 767 local tests ran, one skipped, no failures.
  The accepted QML branch had 29/29 passing GitHub checks at commit `4367df5`.
- Real Qt desktop acceptance: CachyOS KDE Wayland and XWayland for reviewed UI
  fixtures and read-only managed-app/catalog rendering. This does **not** prove
  all real package transactions or every desktop/distro.
- **Still required:** build all four v1.9.0 formats from the finalized source;
  verify exact archive contents and SHA-256 manifest; pass all CI on the
  candidate; verify upgrade and rollback from the published v1.8.0 packages
  in disposable hosts; obtain final owner approval to merge/tag/publish.
- An old one-time `publish-v1.7.0.yml` workflow must not be repurposed.
  Publication must be a separately reviewed manual operation; no tag or
  release may be created just because the candidate CI succeeds.

Previous stable: [AppInstall v1.8.0 — Updates & Discover](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.8.0).

---

---

# AppInstall v1.7.0 — Discover Apps

**Release preparation notes — publishing requires completed packaging checks,
uploaded matching assets, checksums, and owner acceptance.** A version-number
change or merged pull request is not by itself a published GitHub release.

## What's new

- **Discover Apps** alongside **My Applications**. A responsive, multi-column
  card grid retains the accepted horizontal View / Tools / Settings / Help menu.
  Browse first, search by name, and use **View more** for 24 more cards at a time.
- **Flatpak:** live Flathub metadata, icons, and search; click Install to open
  AppInstall's existing download, review, and confirmation dialogue.
- **AppImage:** live AppImageHub metadata; supported direct HTTPS AppImage
  artifacts enter the normal reviewed installer. Other listings open the
  AppImageHub downloads page; no fabricated download URLs.
- **DEB:** browse Debian 13 APT application metadata and search actual packages
  from an AppInstall-owned rootless Debian Distrobox.
- **RPM:** browse Fedora 44 DNF5 repository metadata and search actual packages
  from an AppInstall-owned rootless Fedora Distrobox. DNF5 record formatting,
  empty-query fallbacks, and a live Fedora package-catalog regression check
  protect against the previously empty RPM tab.
- Preparing DEB/RPM repositories requires explicit authorization to create
  or refresh the appropriate container. Installing a selected package requires
  a separate transaction preview and confirmation. No app installs by clicking
  a card or searching a repository.
- Real application artwork is best-effort; packages without a published
  AppStream icon keep their letter placeholder.
- The accepted **My Applications** view, favorites, menu layout and settings
  remain intact.

## Installation options

| Host | Installation method | Verified boundary |
| --- | --- | --- |
| Arch Linux / CachyOS | native `appinstall-1.7.0-1-any.pkg.tar.zst` through pacman | Arch CI + CachyOS desktop preview |
| Debian 13, Ubuntu 24.04/26.04, Linux Mint 22 | native `appinstall_1.7.0-1_all.deb` through APT | distro-specific container CI |
| Fedora 44 | native `appinstall-1.7.0-1.noarch.rpm` through DNF | Fedora 44 CI, including live repoquery; no physical desktop acceptance |
| Other Linux desktops | `appinstall-1.7.0-portable.tar.gz` source bundle and `./install-user.sh` | works only where prerequisites and desktop integration are available; not a universal compatibility guarantee |

The native one-command installer **refuses unsupported hosts**; it will not
try to force Debian, Arch or Fedora binaries onto another distribution.
For other Linux systems, extract the portable archive and install as a
normal, non-root user. Python 3, Bash, freedesktop desktop integration,
PySide6/Qt Quick for the Discover GUI, and optional Flatpak/Podman/Distrobox
backends must be supplied by the host distro. Its QML UI and DEB/RPM
container workflows may not work on every desktop or architecture.

Once the v1.7.0 release is published with the relevant host-native assets
and a matching `SHA256SUMS`, users of verified hosts can run:

```bash
curl -fsSL https://raw.githubusercontent.com/aboodmohd/-AppInstall/main/install.sh | bash
```

For portable installation, obtain the **matching published v1.7.0 archive**,
verify its checksum, extract it, enter its directory and run:

```bash
./install-user.sh
~/.local/bin/appinstall --version
~/.local/bin/appinstall --manage
```

Portable removal: `~/.local/bin/appinstall-uninstall`. This uninstalls
AppInstall's user-level integration, not managed application packages or data.
The source installation asks before creating a copy that would shadow a
pacman, dpkg or RPM installation. Do not run both package modes without an
intentional decision.

## Release and safety boundaries

- Distributions not included in the native CI list have a **portable source
  option**, not a guarantee of all-features/all-apps compatibility.
- Distrobox is not a security sandbox. DEB/RPM packages can need unsupported
  services, system integration, or dependencies.
- DEB/RPM third-party installation and uninstall need a separate real-desktop
  lifecycle acceptance before advertising them as universally validated.
- Exact GitHub release packages/portable archive, common `SHA256SUMS`,
  installer upgrade/rollback, and source installer conflicts must be checked
  before tagging/publishing.
- Only tested hosts receive the official host-native installer path. New
  families may be added later only with their own package and CI validation.

See `INSTALL.md`, `KNOWN_LIMITATIONS.md` and `TESTING.md`.
