# AppInstall Changelog

## 1.9.3 — Compatibility and migration (candidate)

- Migrate legacy monitored Flatpak launchers to live native exports without overwriting user edits.
- Expand disposable compatibility and security testing. Details will be recorded in `docs/V1_9_3_COMPATIBILITY_AUDIT.md`.

## 1.9.2 — Reliability & Stability (published 2026-11-26)

- Repair local DEB repository handling, launcher lifecycle, AppImage staging and identity, and URL diagnostics. Harden APT source selection, uninstall record handling and URL log retention. See [the audit](docs/V1_9_2_RELIABILITY_AUDIT.md).

## 1.9.1 — Package identity maintenance

- Fix the collision where Yay offered unrelated AUR `appinstall` 2.0.8-1 as an upgrade to official AppInstall 1.9.0-1.
- Use `abood-appinstall` for native packages and the CLI, and `io.github.aboodmohd.AppInstall` for desktop integration. The product is still AppInstall.
- Check package ownership and origin before version checks or removal; leave unrelated legacy packages untouched.
- Migrate from v1.9.0 without renaming data or container registry paths. See [the migration guide](UPGRADE.md#migration-from-the-legacy-appinstall-package).

## 1.9.0 — Premium UI/UX redesign (published 2026-11-18)

- Redesign the Qt Quick/QML desktop shell with one horizontal navigation bar and a single Install app menu.
- Group My Applications into Installed and Needs attention, keep Open/Review actions safe, and move secondary maintenance actions into contextual menus.
- Streamline Discover with search, source tabs, responsive catalog cards, three-at-a-time Featured navigation, and source-aware categories, sorting, and View more.
- Add model-backed Updates summaries and compact update rows while preserving existing update review, cancellation and confirmation.
- Correct initial catalog scroll positions, preserve scroll during pagination/metadata refresh, and reserve scrollbar gutters for library and update cards.
- Provide light/dark themes, keyboard access and responsive Qt layouts tested on CachyOS KDE; preserve existing Python backends and native/portable package behavior.
- Published four native/portable artifacts with a verified SHA256SUMS manifest after 29/29 post-merge checks and upgrade/rollback acceptance from v1.8.0. The source is the accepted QML redesign merged via PR #89.

## 1.8.0 — Updates manager and richer Discover (published 2026-11-17)

- Add read-only source-aware update detection and an Updates tab with manual,
  available, unsupported, up-to-date and error states.
- Review and confirm individual Flatpak updates pinned to a verified target
  commit; reject changed source/version and disclose dependency uncertainty.
- Review exact DEB/RPM APT/DNF5 simulations for AppInstall-owned repository
  packages inside existing Distrobox containers; refuse foreign imports and
  changed transactions; preserve repair/recovery diagnostics.
- Support optional eligible AppImage zsync update staging and separately
  confirmed atomic replacement with recovery, when upstream metadata and the
  external helper are present.
- Improve AppStream metadata and safe cached PNG/WebP logos with fallback
  initials; preserve provider-qualified package identity.
- Add actual provider-backed category filters and a live Flathub Featured shelf.
- Add a redesigned, responsive Application Details page with a compact header,
  verified metadata, readable license labels, optional publisher website and
  existing reviewed install actions. Preserve My Applications and preferences.
- Publish v1.8.0 native packages for Arch/CachyOS, Debian/Ubuntu/Mint,
  Fedora 44 and a portable source archive with a matching checksum manifest.
- Support explicit, checksum-verified self-updates of portable user-source
  installations across Linux distributions with a working Python/Bash/XDG
  environment. Keep native self-updates on the host package manager path;
  refuse native/source conflicts and do not install missing dependencies.


## 1.7.0 — Discover Apps and a portable source route

- Discover Apps now browses and searches Flathub Flatpaks and AppImageHub
  AppImages, and the real Debian 13 APT and Fedora 44 DNF5 repository indexes.
- Use a multi-column card layout with **View more** pagination (24 at a time,
  up to 240 per query) and source-specific installation review.
- DEB/RPM repository setup is opt-in. Search is read-only; installing requires
  an explicit package and dependency transaction review/confirmation.
- Correct Fedora DNF5 record delimiting and regression-test actual Fedora
  repository browse results. Real application icons are best-effort metadata;
  dependency packages can keep letter placeholders.
- Retain the My Applications interface, managed-app records, favorites,
  menu, default associations, and explicit uninstall cleanup.
- Release builds retain native pacman/APT/DNF package paths on **verified
  distributions only**. Add a separate, non-root portable **source archive**
  for other Linux desktop environments with Python/Qt and freedesktop
  prerequisites; compatibility is not universal.
- Source installs now detect and ask before shadowing native pacman, dpkg,
  or RPM AppInstall installations. Add portable-archive and cross-distro CI.


## 1.6.0 — Fedora 44 native RPM and one-command installation

- Package AppInstall in three host-native formats: Arch/CachyOS `.pkg.tar.zst`,
  Debian/Ubuntu/Linux Mint `.deb`, and Fedora 44 `.noarch.rpm`.
  Each package derives its version and shared file inventory from PKGBUILD.
- Add a Fedora 44 native RPM built with `rpmbuild` by an unprivileged user,
  with Fedora distribution dependencies for PySide6 and Qt Quick. AppInstall's
  Python/QML modules remain co-located for reliable manager startup.
- The stable-release one-command installer identifies Fedora 44 (x86_64),
  selects only a release-matched native RPM, validates its SHA-256 checksum and
  RPM metadata, and invokes DNF for installation, update, or removal.
- Refuse unsupported Fedora versions, missing RPM assets, duplicate or
  untrusted download URLs, and incorrect package metadata instead of
  installing a package intended for another distribution.
- Add Fedora 44 CI for RPM build, DNF installation/removal, GUI smoke and
  preservation of unrelated user files/MIME defaults. The previous Arch
  and Debian-family CI paths remain covered.
- Compatibility is based on CI environments unless independently verified
  on a Fedora desktop; AppImage/Flatpak/DEB/RPM application behavior varies.

## 1.5.0 — QML manager becomes the default

- The redesigned Qt Quick/QML **My Applications** interface is now the default
  for `appinstall --manage` and launching AppInstall without file arguments.
  Use `appinstall --manage --widgets` for the legacy Widgets interface.
- Preserve the existing installer backends, managed applications, favorites,
  desktop integration and user settings when switching interfaces.
- Correct KDE Wayland QML runtime problems with delegate indices, hover state,
  unavailable icon paths and custom control content.
- Replace the unresponsive status and sort ComboBoxes with explicitly clickable
  popup menus supporting mouse and keyboard selection; filter and sorting
  changes update the inventory.
- Fix accidental bright-yellow hovered application cards by correcting Qt's
  `#AARRGGBB` color tokens, and use restrained neutral hover styling.
- Add QML/Wayland smoke and dropdown interaction regression tests, verify
  packaged QML resources and preserve the Widgets fallback.
- Release qualification is limited to tested samples; AppImage, Flatpak,
  DEB/RPM and desktop behavior depend on the user's system and packages.

## 1.4.0

- AppInstall checks for its own stable updates on startup (about every 12 hours) and on demand.
- Managed Flatpak apps can be updated individually from My Applications.
- Desktop notifications for available updates (notify-send, headless-safe).
- Settings module, theme toggle (auto/light/dark), favorites, package size.
- Drag-and-drop batch install with per-file results and cancel.
- Container health & repair for DEB/RPM container apps.
- Uninstall cleanup with explicit per-path checkboxes; nothing silently deleted.

## 1.3.0

- Check for stable updates from My Applications.
- Install the verified native package with desktop authentication.
- Show release notes after verifying the installed version.

## 1.2.2

- Repair a managed launcher directly from the launch failure dialog, then choose Retry Open.
- Retry failed URL downloads with the same URL and expected SHA-256.
- See which DEB/RPM backend tools are missing and how to install them on your distro.

## 1.2.1

- Add Install from File to My Applications and provide Qt fallback dialogs.
- Exercise GUI startup under Sway, i3 and Xfwm in CI.

## 1.2.0

- Add a native AppInstall Debian package for Debian 13, Ubuntu 24.04 and
  26.04, and Linux Mint 22.
- Select the host package automatically in the one-command installer. APT
  installs required dependencies only.

## 1.1.2 (published)

### KDE moved-launcher bug fix
- Verified managed desktop launchers relocated to the configured user Desktop
  using the recorded SHA-256 and AppInstall launch ID; reject mismatches and
  symlinked launchers.
- Recognized matching relocated AppImage and Distrobox DEB/RPM launchers in
  My Applications without modifying other application records.
- Regression tests added via PR #45 for valid, modified, unrelated and custom
  XDG desktop-location cases.

### Validation and known limits
- PR #46 release preparation merged as `5044b748` with 8/8 successful
  post-merge GitHub checks; source/package integrity and published-v1.1.1
  upgrade/rollback tested in disposable Arch CI.
- On a real CachyOS KDE device, the owner reported qBittorrent shortcut,
  Installed status, My Applications Open, Diagnostics and package-file
  integrity checks passing with the v1.1.2 candidate installed.
- Broader fresh desktop manual tests of all four package formats, Install
  from URL, and rollback on the active KDE system have not been repeated.
- The published v1.1.1 release and independently versioned `install.sh`
  v1.1.0 remain unchanged. Publication needs explicit owner authorization.
- Any documentation or packaging follow-up that changes `main` requires
  new final build/CI and checksum verification; previous artifact hashes
  do not identify that new build.

## 1.1.1 (published 2026-11-12 as [`v1.1.1`](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.1.1))

- Shipped the owner's official blue-folder/download/checkmark AppInstall icon
  in eight freedesktop hicolor PNG sizes for Arch and source installations.
- Connected AppInstall's KDE launcher, service menu and native Qt windows to
  the icon name `appinstall` without replacing third-party application icons.
- Enforced the packaged icon allowlist through release-evidence checks.
- Published the verified `appinstall-1.1.1-1-any.pkg.tar.zst`, SHA256SUMS and
  RELEASE_VERIFICATION.txt from source commit
  `311a7785f050c0a04b6d03bfee7ddb46692eced0`, after 8/8 post-merge CI
  and a reported real CachyOS KDE logo preview.
- `install.sh` remains independently versioned v1.1.0 and chooses the latest
  published stable application release.

## 1.1.0 (published 2026-11-12 as [`v1.1.0`](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.1.0))

- Added secure Install from URL with HTTPS progress, cancellation, package
  review, content-format detection and optional SHA-256 integrity comparison.
- Added CLI `appinstall --install-url URL`; existing AppImage, Flatpak and
  Distrobox DEB/RPM installation and management workflows were preserved.
- Added TLS/hostname validation, public-IP pinning, private-address and unsafe
  redirect blocking, size limits and temporary-download cleanup.
- Released from `f93ccd9c9f2cd9f4a473f92fe2323e248fd8ddda`; 8/8 post-merge CI.
  Full CachyOS KDE desktop end-to-end acceptance remained an explicitly
  documented owner-accepted exception.
- The separate `install.sh` is also numbered 1.1.0 but independently versioned
  and installs the latest *published stable* application package.

## 1.0.0 (published 2026-11-10 as [`v1.0.0`](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.0.0))

Release notes for the published Stable 1.0 source and package (`adf44eb`,
approval chain in [issue #14](https://github.com/aboodmohd/-AppInstall/issues/14)).

- Unified My Applications and Diagnostics interfaces, launch monitoring and
  repair flows for representative AppImage, Flatpak, DEB and RPM packages.
- Passive AppImage inspection, desktop-entry sanitation and source update
  recovery against isolated ENOSPC and SIGKILL faults.
- Retained original AppImageLauncher payloads, unrelated icons, application
  records and user MIME defaults during the tested operations.
- Real fresh CachyOS KDE Wayland acceptance on 2026-11-10: owner-reported
  44/44 representative four-format lifecycle checks, plus verified Pacman
  package removal/reinstallation and user settings preservation.
- Current Arch packaging includes the MIT notice and separate declared
  dependencies. Third-party technical findings and remaining human
  licensing scope are recorded in DEPENDENCY_LICENSE_AUDIT.md.
- Final rebuilt release artifacts and checksums, CI and owner approval are
  release-time gates; this changelog does not certify arbitrary compatibility.

## 1.0.0-rc.1 (release candidate — NOT PUBLISHED)

This is a test build for verifying the eventual stable 1.0.0 release. Do not
mistake this branch or its CI artifact for an approved stable release.

### Security and reliability
- Import AppImage metadata without executing application runtimes.
- Sanitize embedded launcher metadata and reject paths escaping AppDir.
- Preserve other applications' themed icons and the original
  AppImageLauncher AppImage files during shortcut migration.
- Protect user source upgrades with staged, fsynced writes, backups and a
  recovery journal; verify rollback through disk-full and abrupt-exit tests.
- Preserve existing source install data, MIME defaults and managed records.

### Testing
- Cross-distribution headless tests on Ubuntu, Arch and Fedora.
- Arch package build/reinstall/removal tested in disposable CI container.
- CachyOS isolated AppImage security and source-recovery tests passed.
- Real KDE, arbitrary DEB/RPM/Flatpak/AppImage compatibility and physical
  power-loss recovery remain release gates.

---

## 1.0.0-beta.1 (released 2026-11-02)

### Added
- Installed Applications Manager (`manager.py`, `appinstall --manage`)
  - Unified inventory across AppImage, Flatpak, DEB, and RPM backends
  - Search and package-format filtering (All / AppImage / Flatpak / DEB / RPM)
  - Per-application cards with icon, name, version, format, container, status
  - Application actions: Open, Details, Reinstall, Uninstall, Repair Launcher,
    Check for Updates (Flatpak only)
  - AppDetailsDialog with launch history, error details, compatibility notes
  - Light and dark theme support via `ui_style.maybe_dark()`
  - `--screenshot PATH` evidence-capture hook for offscreen rendering
- `result_ui.py`: shared SuccessDialog and FailureDialog windows
- Passive AppImage preview (`PreviewUnavailable`, `unsquashfs` offset scan)
  - AppImage is NEVER executed merely to display metadata
  - Degrades to generic identity (`package-x-generic` icon) with honest notice
- `result_ui.py` integrated into `container_ui.py` workflow
- Screenshot evidence runner (`tools/ui_evidence.py`)
- Phase 4 + Phase 5 GUI evidence screenshots (`evidence/phase4/`)

### Changed
- `confirm.py`: split window construction into `review_window()` function
- `ui_style.py`: added `maybe_dark(app)` and `ghost_button_stylesheet()`
- `container_ui.py`: restyled with info grid, indeterminate progress, stage
  labels, duplicate-click guard, result-dialog hooks
- `appinstall` bash: added `--manage` entry point; VERSION 0.2.0 → 1.0.0-beta.1
- `appinstall.desktop`: comment updated to include DEB/RPM
- PKGBUILD: pkgver 0.2.0 → 1.0.0beta1; added `result_ui.py` and documentation
  to source; added `pyside6` to depends; added `squashfs-tools` to optdepends

### Fixed
- Inventory status inference: container records resolve managed launchers via
  `exports[0].path` when the recorded desktop path is missing
- AppImage target path read from manifest when absent from launch registry
- Unknown status with no problems now reported as "installed"
- `manager.py` b2sum mismatch in PKGBUILD

### Removed
- AppImage runtime-execution fallback (Priority 1 security fix)

## 0.2.0 (previous release)

See git history for prior changes.
