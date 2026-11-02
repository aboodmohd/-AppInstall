# AppInstall Changelog

## 1.0.0-beta.1 (unreleased)

### Added
- Installed Applications Manager (`manager.py`, `appinstall --manage`)
  - Unified inventory across AppImage, Flatpak, DEB, and RPM backends
  - Search and package-format filtering (All / AppImage / Flatpak / DEB / RPM)
  - Per-application cards with icon, name, version, format, container, status
  - Application actions: Open, Details, Reinstall, Uninstall, Repair Launcher,
    Check for Updates (Flatpak only)
  - AppDetailsDialog with launch history, error details, compatibility notes
  - Light and dark theme support via `ui_style.maybe_dart()`
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
