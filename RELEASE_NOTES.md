# AppInstall v1.6.0

AppInstall v1.6.0 introduces a **native Fedora 44 RPM package** alongside the
existing Arch/CachyOS and Debian-family packages. The one-command installer
automatically selects the host-native package from the latest *published*
stable release, verifies its SHA-256 checksum, and uses the host package
manager. The updated QML My Applications manager from v1.5.0 remains the
default, with the Widgets interface still available.

## New in v1.6.0

- **Fedora 44 (x86_64):** Native `.noarch.rpm`, Fedora PySide6/Qt Quick
  dependencies, DNF installation, upgrade, and uninstall support.
- **One-command install:** Fedora 44 selection checks the stable release tag,
  RPM filename, canonical download URL, SHA256SUMS, and package metadata.
  It does not fall back to installing an Arch or Debian package on Fedora.
- **Compatibility:** Native RPM build and install/remove cycles, QML offscreen
  startup, verified install from a simulated stable GitHub release and
  preservation of unrelated user files/defaults are exercised in Fedora 44 CI.
- **Existing platforms:** Arch/CachyOS and Debian/Ubuntu/Mint installations
  retain their package formats, settings, previous associations and launcher
  behavior; cross-distro CI guards against regression.

## Supported installation targets

| Host distribution | Package | Package manager |
| --- | --- | --- |
| Arch Linux / CachyOS (x86_64) | `appinstall-1.6.0-1-any.pkg.tar.zst` | pacman |
| Debian 13, Ubuntu 24.04/26.04, Linux Mint 22 (x86_64) | `appinstall_1.6.0-1_all.deb` | APT |
| Fedora 44 (x86_64) | `appinstall-1.6.0-1.noarch.rpm` | DNF |

`noarch` and `all` describe the **package payload**; tested host
architectures remain x86_64. Fedora 43/45, RHEL, openSUSE, and other
distributions are not claimed to be supported by the one-command installer.
Source installation remains an alternative for advanced users.

## Install, verify, and roll back

As a regular (non-root) desktop user, run:

```bash
curl -fsSL https://raw.githubusercontent.com/aboodmohd/-AppInstall/main/install.sh | bash
```

For a no-changes preview, append `-s -- --dry-run` to the bash invocation.
For manual installation, download the **matching native package** and
`SHA256SUMS` from this release and verify the selected SHA-256 line first.
See `INSTALL.md` and `UPGRADE.md`.

After installing, check `appinstall --version`, `appinstall --manage`, and
`appinstall --manage --widgets`. Preserve user application records and
previously downloaded packages for recovery. Never delete `~/Applications`
or `~/.local/share/appinstall` as a shortcut to fix package conflicts.

## Testing boundaries

- The v1.5.0 QML interface was accepted on a real CachyOS KDE Wayland
  desktop; v1.6.0's *exact final package* still requires its own acceptance.
- Fedora 44 has package installation, Qt Quick offscreen GUI, and DNF lifecycle
  coverage in a disposable CI container. This **is not** equivalent to live
  Fedora GNOME/KDE desktop acceptance; interactions and desktop MIME handling
  can vary.
- Installing AppInstall itself with DNF is distinct from using AppInstall
  to install a third-party DEB/RPM in rootless Distrobox. Distrobox is
  not a security sandbox; package compatibility depends on the application.

See `KNOWN_LIMITATIONS.md` and `SECURITY_REVIEW.md` for additional
limitations and appropriate trust checks.
