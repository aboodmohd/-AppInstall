# AppInstall v1.10.0 — Native ARM64 Support (release candidate)

Unpublished development candidate. The latest published stable release is v1.9.5.

Adds native `aarch64` host support to the one-command installer alongside `x86_64`,
without enabling binfmt/QEMU or any other cross-architecture emulation. Native
amd64/arm64 DEB and x86_64/aarch64 RPM packages are matched to the host while
`all`/`noarch` packages keep working. AppImage, Flatpak, portable installs, the
Premium UI and PySide6/Qt QML are covered by native ARM64 runtime CI.

Candidate artifact prefix: `appinstall-1.10.0-portable.tar.gz`; native packages
use `abood-appinstall` version `1.10.0-1`.

## Previous release notes

# AppInstall v1.9.4 — Update check reliability (candidate)

Unpublished development candidate. The latest published stable release is v1.9.3.

Fixes the live CachyOS issue where the Premium UI reported "Could not check for updates" without an actionable explanation. Self-update failures are now categorized and explained; update checks have a timeout; application update backends are isolated so one failure cannot suppress partial results.

Candidate artifact prefix: `appinstall-1.9.4-portable.tar.gz`; native packages use `abood-appinstall` version `1.9.4-1`.

## Previous release notes

# AppInstall v1.9.3 — Compatibility and migration (candidate)

Unpublished development candidate. The latest published stable release is v1.9.2.

This candidate focuses on remaining reliability, migration and compatibility work before v2.0.0. See `docs/V1_9_3_COMPATIBILITY_AUDIT.md` for verified evidence and limitations.

Candidate artifact prefix: `appinstall-1.9.3-portable.tar.gz`; native packages use `abood-appinstall` with version `1.9.3-1`.

Live acceptance corrected Flatpak export handling: legitimate Flatpak export symlinks are followed only within the Flatpak installation root, while external symlink redirection and user-edited launchers are refused unchanged.

## Previous release notes

# AppInstall v1.9.2 — Reliability & Stability (published 2026-11-26)

This is the latest stable release. It keeps the AppInstall public name, Premium UI, and the unique `abood-appinstall` package identity from v1.9.1.

## Fixed issues

1. **DEB installation blockage (confirmed):** vendor-added APT fragments could block later local DEB installs. Local DEB transactions now stage only authenticated source stanzas inside the container.
2. **Uninstall could break managed apps (partially confirmed):** supported uninstallers now detach AppImage monitoring, preserve native Flatpak exports, and keep DEB/RPM launch commands. Records, payloads, containers and Flatpaks are retained.
3. **Frozen Flatpak launchers (confirmed):** new adoptions keep Flatpak's maintained export symlink live instead of copying it.
4. **Large AppImage failures (partially confirmed):** installation uses one streamed copy on the destination filesystem, checks free space, and treats preview timeouts as non-fatal.
5. **AppImage name collisions (confirmed):** each AppImage gets an independent launcher and payload identity; identical names coexist and can be updated or removed independently.
6. **URL installation errors (partially confirmed):** backend output is captured to a bounded, redacted diagnostic log; HTTP, network, format, checksum, size and storage failures produce actionable messages.

The previously reported Arch filesystem-layout issue was already resolved in v1.9.1: only `/usr/bin/abood-appinstall` is in `usr/bin`; modules live under `/usr/lib/abood-appinstall`. Additional hardening in this release covers APT prefix/keyring validation and malformed container-registry records during uninstall. See [the full audit](docs/V1_9_2_RELIABILITY_AUDIT.md).

## Upgrade and migration

Existing v1.9.1 users can upgrade normally through the one-command installer or a verified native package. No user data, records, launchers or container configuration paths are renamed. See [UPGRADE.md](UPGRADE.md#v191-to-v192-reliability-upgrade).

Live CachyOS acceptance verified the Premium UI, seven managed application records, settings, databases, nine MIME associations, launchers, Flatpaks, AppImages and Distrobox containers. Disposable acceptance covered official Chrome, VS Code, Edge and Brave DEBs, 512 MiB/1 GiB/2 GiB AppImages, and native/portable uninstall.

## Release assets

- Arch Linux / CachyOS: `abood-appinstall-1.9.2-1-any.pkg.tar.zst`
- Debian / Ubuntu: `abood-appinstall_1.9.2-1_all.deb`
- Fedora: `abood-appinstall-1.9.2-1.noarch.rpm`
- Portable: `appinstall-1.9.2-portable.tar.gz`
- `SHA256SUMS`

## Previous release notes

# AppInstall v1.9.1 — Package identity maintenance

On CachyOS, Yay offered unrelated AUR `appinstall` 2.0.8-1 as an upgrade to official AppInstall 1.9.0-1 because both used the same package name. v1.9.1 gives AppInstall its own package identity without replacing or removing unrelated packages.

AppInstall retains its public name and Premium UI. Native packages and the CLI now use `abood-appinstall`; the desktop ID is `io.github.aboodmohd.AppInstall`. This keeps the official package separate from unrelated software using the legacy `appinstall` name. The update helper checks local package ownership and origin before comparing versions.

Follow [the migration and rollback guide](https://github.com/aboodmohd/-AppInstall/blob/v1.9.1/UPGRADE.md#migration-from-the-legacy-appinstall-package) for the first upgrade. Settings, application records, and Distrobox registry paths do not change.

## Release assets

- Arch Linux / CachyOS: `abood-appinstall-1.9.1-1-any.pkg.tar.zst`
- Debian / Ubuntu: `abood-appinstall_1.9.1-1_all.deb`
- Fedora: `abood-appinstall-1.9.1-1.noarch.rpm`
- Portable: `appinstall-1.9.1-portable.tar.gz`
- `SHA256SUMS`: verify the downloaded asset before installation.

The v1.9.1 migration was verified on live CachyOS. The Premium UI, all nine MIME associations, and existing records, Flatpaks, AppImages and Distrobox containers were preserved.

## Previous stable release

### AppInstall v1.9.0 — Premium UI/UX (published 2026-11-18)

Published stable release:
[v1.9.0 — Premium UI/UX](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.9.0).
The notes below describe the published artifacts and their verification.
Upgrade and rollback from the published v1.8.0 packages were checked in CI.

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

## Release assets

- Arch Linux / CachyOS: `appinstall-1.9.0-1-any.pkg.tar.zst`
- Debian 13 / Ubuntu 24.04 and 26.04 / Linux Mint 22: `appinstall_1.9.0-1_all.deb`
- Fedora 44: `appinstall-1.9.0-1.noarch.rpm`
- Other environments with portable prerequisites: `appinstall-1.9.0-portable.tar.gz`
- A single `SHA256SUMS` manifest verifies all four files.

The portable source bundle is **not** a universal binary; it requires host
Python/Bash/XDG/Qt dependencies. DEB/RPM applications still use AppInstall-
managed rootless Distrobox containers, which are **not** security sandboxes.

## Verification

- Source: redesign PR #89, merged to main as `ad6e6ac3c625ced685bd283f05291143806f6452`;
  the stable release targets `850b01c1fbcef2fdaff447d617e3d9b0917002ab`.
- 29/29 post-merge GitHub checks passed on `850b01c1fbcef2fdaff447d617e3d9b0917002ab`,
  including 767 automated tests (2 skipped).
- Fresh pacman, APT, RPM and portable packages were built from that exact merged
  source; `SHA256SUMS` covers the four published assets.
- Upgrade and rollback from published v1.8.0 packages passed in disposable Arch,
  Debian 13 and Fedora 44 CI.
- Real Qt desktop acceptance: CachyOS KDE Wayland and XWayland for reviewed UI
  fixtures and read-only managed-app/catalog rendering. This does **not** prove
  all real package transactions or every desktop/distro.
- Tests in virtual desktops do not guarantee all physical setups. AppImage,
  Flatpak and container-managed DEB/RPM update compatibility varies by source.
  Distrobox is not a security sandbox.

Previous stable: [AppInstall v1.8.0 — Updates & Discover](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.8.0).

> Historical release notes for earlier versions follow. They are retained as
> written at the time each version was prepared; v1.7.0 and v1.8.0 are also
> published stable releases.

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
