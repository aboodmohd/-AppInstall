# AppInstall 1.0.0-beta.1 Package Checksum Manifest

Package: `appinstall-1.0.0beta1-1-any.pkg.tar.zst`
SHA-256: `06e72385e6af6931f15c59c88513ea6e77bf8c4edb235f252344be42cbe359b3`
Source commit: `7f8d110` + deployment workflow fix on branch `1.0-beta`
Build date: 02 Nov 2026

## Package contents (21 files)

| Path | Size | Permissions |
|------|------|-------------|
| /usr/bin/appinstall | 22,914 bytes | 0755 |
| /usr/bin/appimage_backend.py | 13,150 bytes | 0644 |
| /usr/bin/confirm.py | 9,595 bytes | 0644 |
| /usr/bin/container_backend.py | 19,948 bytes | 0644 |
| /usr/bin/container_ui.py | 12,919 bytes | 0644 |
| /usr/bin/diagnostics_core.py | 6,069 bytes | 0644 |
| /usr/bin/diagnostics_ui.py | 11,273 bytes | 0644 |
| /usr/bin/launch_monitor.py | 28,565 bytes | 0644 |
| /usr/bin/manager.py | 37,261 bytes | 0644 |
| /usr/bin/native_backend.py | 3,735 bytes | 0644 |
| /usr/bin/package_meta.py | 2,065 bytes | 0644 |
| /usr/bin/result_ui.py | 5,397 bytes | 0644 |
| /usr/bin/runtime_probe.py | 5,265 bytes | 0644 |
| /usr/bin/ui_style.py | 3,449 bytes | 0644 |
| /usr/share/applications/appinstall.desktop | 494 bytes | 0644 |
| /usr/share/doc/appinstall/README.md | 9,836 bytes | 0644 |
| /usr/share/doc/appinstall/LICENSE | 1,080 bytes | 0644 |
| /usr/share/doc/appinstall/LAUNCH_DIAGNOSTICS.md | 10,753 bytes | 0644 |
| /usr/share/doc/appinstall/INTEGRATION_TESTING.md | 8,368 bytes | 0644 |

## Installed size

207.16 KiB

## Compressed size

69.04 KiB

## Verification

```sh
pacman -Qip appinstall-1.0.0beta1-1-any.pkg.tar.zst
sha256sum appinstall-1.0.0beta1-1-any.pkg.tar.zst
# Expected: 069970228a8e85df06c7848bc58dce3c5acfa4eef9f7d1203c8b5f9c82b0a252
```
