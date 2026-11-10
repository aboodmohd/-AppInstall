# AppInstall Changelog

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
