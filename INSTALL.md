# AppInstall Installation Guide

> **v1.0.0 final preflight branch:** source and package version have been
> staged as 1.0.0 for isolated release validation only. The public release
> is still v1.0.0-beta.1. No stable tag, public release, or authorized
> update to an existing installation has happened. Install the candidate
> only on a backed-up/disposable system, after independently verifying
> the package and its SHA256SUMS file.


> **Release candidate branch:** Version 1.0.0-rc.1 is for testing on a
> disposable system. The published 1.0.0-beta.1 package shown below is
> historical; it is not the candidate package. Stable 1.0.0 is not released.

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
```

The package installs `appinstall` to `/usr/bin/appinstall` and registers `/usr/share/applications/appinstall.desktop` as an *available* file handler. It does **not** change your existing default file associations. For a file that opens in another application, right-click it in Dolphin and select **Open With → AppInstall**, then choose AppInstall as the default only if you want to. Some file managers may prefer executable AppImage handling over a MIME default.

To open the Installed Applications Manager:

```sh
appinstall --manage
```

## Install from source

```sh
git clone https://github.com/aboodmohd/-AppInstall.git appinstall
cd appinstall
./install-user.sh
```

## What install-user.sh does

- Registers `appinstall.desktop` as the default handler for supported MIME types
- Copies AppInstall modules to `~/.local/share/appinstall/`
- Copies the `appinstall` executable to `~/.local/bin/`
- Creates `~/.local/bin/appinstall-uninstall`
- Migrates existing launchers via `launch_monitor.synchronize()`

## Uninstall

For a source/user installation:

```sh
~/.local/bin/appinstall-uninstall
```

This restores previous MIME associations that AppInstall still owns and removes the user-level registration. For a pacman-managed system package, run `sudo pacman -R appinstall` instead. Do not run the source uninstaller as a substitute for removing the system package. Managed applications and their data are kept.

## Avoid mixed installations

A previous source installation in `~/.local/bin/appinstall` can take precedence over the packaged `/usr/bin/appinstall` depending on your `PATH`. After installing or upgrading, check:

```sh
type -a appinstall
command -v appinstall
```

If both are listed, decide which installation to keep. Use the source uninstaller only when you intend to remove that user copy; it restores only associations that it still owns. `install-user.sh` warns and asks permission before creating a user copy when a pacman-managed package exists. Nothing is removed automatically.

## Double-click usage

After explicitly selecting AppInstall as the default handler, double-click a supported file (file-manager behavior can vary):
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
