# AppInstall Testing Guide

## Automated tests

```sh
cd /home/abood/appinstall
python3 -m unittest discover -s tests
```

Expected result: 110 tests, 0 failures, 0 skipped (with `squashfs-tools`
installed). Without `squashfs-tools`, 2 tests skip (`PassiveExtractionWithTools`).

## Test files

| File | Coverage |
|------|----------|
| `tests/test_security.py` | Passive AppImage preview, exit codes, metadata guards |
| `tests/test_appimage.py` | AppImage install, replace, failure, rollback |
| `tests/test_containers.py` | DEB/RPM package inspection, container engine |
| `tests/test_monitor.py` | Launch monitoring, failure classification |
| `tests/test_diagnostics_ui.py` | Diagnostics UI |
| `tests/test_installer.py` | Bash installer |
| `tests/test_native.py` | Native package backend |
| `tests/test_manager.py` | Installed Applications Manager inventory and actions |

## Live GUI testing

The Installed Applications Manager can be tested on a live KDE Wayland
session:

```sh
QT_QPA_PLATFORM=wayland python3 manager.py
```

Manual verification checklist (see `KNOWN_LIMITATIONS.md`):
- Search filters installed applications
- Package-format filters work
- Open launches the correct application
- Details displays correct information
- Diagnostics displays correct records
- Repair Launcher works safely
- KDE application menu integration works
- Dolphin double-click opens AppInstall

## Offscreen screenshot evidence

```sh
python3 tools/ui_evidence.py
```

Captures light/dark screenshots of confirm.py, container_ui.py, and
manager.py into `evidence/phase4/`.

## Performance

Measured on a 2017 Intel MacBook Air:
- Manager inventory load: ~0.19s
- Full GUI window startup: ~0.057s
- Confirm module import: ~0.05s
