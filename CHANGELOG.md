# AppInstall Changelog

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
