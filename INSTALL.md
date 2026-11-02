# AppInstall Installation Guide

## System requirements

- Python 3
- bash, coreutils, xdg-utils
- PySide6 (graphical interface)
- kdialog (KDE) or zenity (GNOME/Xfce) (fallback dialogs)
- flatpak (Flatpak installation)
- podman + distrobox (DEB/RPM containers via rootless Distrobox)
- squashfs-tools (passive AppImage preview — recommended but optional)
- libarchive (package inspection)
- binutils (optional static ELF dependency checks)

## Install from package (Arch/CachyOS)

```sh
sudo pacman -U appinstall-1.0.0beta1-1-any.pkg.tar.zst
./install-user.sh
```

## Install from source

```sh
git clone https://github.com/aboodmohd/-AppInstall.git appinstall
cd appinstall
git checkout 1.0-beta
./install-user.sh
```

## What install-user.sh does

- Registers `appinstall.desktop` as the default handler for supported MIME types
- Copies AppInstall modules to `~/.local/share/appinstall/`
- Copies the `appinstall` executable to `~/.local/bin/`
- Creates `~/.local/bin/appinstall-uninstall`
- Migrates existing launchers via `launch_monitor.synchronize()`

## Uninstall

```sh
~/.local/bin/appinstall-uninstall
```

This restores previous MIME associations and removes AppInstall registration.
Installed applications are kept.

## Double-click usage

After registration, double-click any supported file:
- `.AppImage` — AppImage installation
- `.flatpak` / `.flatpakref` — Flatpak installation
- `.flatpakrepo` — Flatpak repository addition
- `.deb` / `.rpm` — DEB/RPM installation via Distrobox container

Or run from the command line:
```sh
appinstall FILE.AppImage
appinstall --manage          # Installed Applications Manager
appinstall --diagnostics     # Application Diagnostics
appinstall --list            # List managed applications
appinstall --remove NAME     # Remove a managed application
```
