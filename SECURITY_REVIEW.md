# AppInstall Security Review Summary

## AppImage Preview Security (Priority 1)

**Threat**: An untrusted AppImage could be executed merely to display its
metadata, icon, or contents when double-clicked.

**Fix**: Runtime-execution fallback removed from `appimage_backend.py`.
- `preview_contents()` uses passive `unsquashfs` offset scan only
- `PreviewUnavailable` raised when `unsquashfs` is unavailable or no
  squashfs payload found
- `install()` degrades to generic identity (`package-x-generic` icon,
  "Detailed preview unavailable" comment) without executing the image
- The image is copied to a temp directory and never made executable for
  preview purposes

**Verification**:
- `test_preview_refuses_and_never_spawns_the_image`: preview spawns
  nothing when `unsquashfs` unavailable; no `EXECUTED` marker written
- `test_passive_extraction_never_runs_the_image`: with `unsquashfs`,
  contents unpacked passively; image runtime never executed
- `test_archive_escape_names_are_rejected_by_unsquashfs`: extraction
  contained within scratch directory; no path escape

## Stable release audit: imported AppImage metadata (2026-11-04)

- Metadata from an AppImage is untrusted even when extracted passively.
  Desktop-entry values may contain indented continuation lines; these are
  flattened before writing a new launcher, preventing embedded values from
  injecting standalone `Exec=` or `Actions=` keys.
- Embedded `.desktop` symlinks that resolve outside the extracted AppDir
  are ignored during preview; the loader can still find legitimate nested
  desktop entries.
- When replacing an AppImageLauncher shortcut, AppInstall backs up the old
  shortcut but no longer deletes the pre-existing AppImage payload.
  AppInstall only cleans up its own previous generation.
- Tests use malicious desktop metadata and simulated legacy launchers.
  These controls are *not* a general guarantee that executing third-party
  applications is safe.

## Archive extraction security

- Extraction destination is a `tempfile.TemporaryDirectory` scratch
- Symlinks and path-traversal entries are contained within the scratch
  root (verified by `unsquashfs` itself)
- `.desktop` file parsing uses `configparser` with no interpolation
- No shell execution of archive contents

## Exit-code protocol

- 0 = install confirmed, 1 = user cancelled, 2 = failure, 3 = Qt unavailable
- `confirm.py` exit code 3 → bash falls back to kdialog/zenity instead of
  failing; a Qt crash is never silently mistaken for cancellation

## Launch monitoring

- Applications launch through monitored wrappers (`launch_monitor.py`)
- Startup failures classified: dependency, container, port, executable,
  permission, architecture, crash, launcher
- Launch errors and logs are preserved; success is never claimed without
  evidence
- "Running" status does not imply the application is usable

## Uninstall safety

- Only AppInstall-owned files, launchers, and metadata are removed
- Shared Distrobox containers are never deleted
- Unrelated applications and user data are preserved
- Confirmation dialog lists intended changes before removal

## Privileged operations

- `squashfs-tools` installation requires explicit user approval (done)
- No kernel, GRUB, EFI, or partition modifications
- No macOS or APFS modifications
