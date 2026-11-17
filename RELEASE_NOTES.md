# AppInstall v1.8.0 — Release candidate (NOT PUBLISHED)

**Development-branch draft.** v1.7.0 is the latest published stable release
until the exact v1.8.0 packages, source archive, checksum manifest, per-host
acceptance and owner authorization are verified.

## Proposed v1.8 changes

- **Application Updates:** source-aware read-only discovery and a dedicated
  Updates tab. Reviewed, one-at-a-time Flatpak updates use verified ref, origin
  and target commit. Owned DEB/RPM container packages use exact simulated
  transactions before opt-in upgrade; imported/foreign packages remain manual.
- **AppImage updates:** eligible type-2 AppImages with supported zsync metadata
  and a separately installed updater may be downloaded, reviewed, validated,
  atomically replaced, and recovered. Other AppImages require manual action.
- **Discover enhancements:** local verified PNG/WebP icons, source-qualified
  developer/version/license metadata where available, filters from real
  categories, and an actual live Flathub popular Featured collection.
- **Application Details:** compact, responsive display for exact source/package
  identity, optional homepage, description, version/license/developer and the
  normal reviewed install flow. Missing metadata is not guessed.
- **Cross-distro portable self-update:** user-source installs can check the
  latest published stable GitHub release and, after explicit confirmation,
  validate the portable archive against its SHA256SUMS and update the user
  files with the existing recoverable transaction. No foreign native package
  is installed. Native installs continue using their package-manager paths.
  This feature requires Python 3 and other portable runtime prerequisites;
  it cannot guarantee support for every Linux desktop or CPU architecture.

## Candidate installation formats — pending final acceptance

- Arch Linux / CachyOS: `appinstall-1.8.0-1-any.pkg.tar.zst`
- Debian 13 / Ubuntu 24.04, 26.04 / Mint 22: `appinstall_1.8.0-1_all.deb`
- Fedora 44: `appinstall-1.8.0-1.noarch.rpm`
- Other equipped Linux desktops: `appinstall-1.8.0-portable.tar.gz`

These are **expected candidate filenames only**, not links to verified or
published downloads. The final release must also include matching
`SHA256SUMS`, provenance/upgrade/rollback records and real desktop tests.
Some package metadata and icons may be unavailable. zsync is not a
developer signature; Distrobox is not a security sandbox; portable support
is conditional, not universal. No package installation occurs without
the application's explicit confirmation controls.

Do not install PR build artifacts on a primary system merely because CI
passed. Final owner merge, tag and publish approvals remain mandatory.

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
