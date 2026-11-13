# AppInstall Installation Guide

## One-command installation

Run the installer as your regular desktop user:

```sh
curl -fsSL https://raw.githubusercontent.com/aboodmohd/-AppInstall/main/install.sh | bash
```

The installer selects a package from the latest stable GitHub release and
checks its SHA-256. Arch Linux and CachyOS use pacman. Debian 13, Ubuntu 24.04
and 26.04, and Linux Mint 22 use APT when the stable release includes a
`.deb`. On APT systems, have Python 3 and curl available before running the
command. Ubuntu needs the Universe repository enabled.

APT installs the selected `.deb` with `--no-install-recommends`. The package
declares alternative Qt bindings so APT can satisfy the dependency from the
distribution's repositories. Install optional backends separately as needed.
On Arch and CachyOS, the installer offers optional backends after setup.

Use `--dry-run` to inspect the package selection and `--uninstall` to remove
AppInstall. Use `--set-defaults` to opt into changing per-user file handlers
or `--no-defaults` to keep them. Previous defaults are backed up.

## System requirements

- Python 3
- bash, coreutils, xdg-utils
- PySide6 or PyQt6 (graphical interface)
- kdialog (KDE) or zenity (GNOME/Xfce) (fallback dialogs)
- flatpak (Flatpak installation)
- podman + distrobox (DEB/RPM containers via rootless Distrobox)
- squashfs-tools (passive AppImage preview — recommended but optional)
- libarchive (package inspection)
- binutils (optional static ELF dependency checks)

## Install from package (Arch/CachyOS)

Download from the [`v1.1.2` release](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.1.2):

```sh
curl -LO https://github.com/aboodmohd/-AppInstall/releases/download/v1.1.2/appinstall-1.1.2-1-any.pkg.tar.zst
curl -LO https://github.com/aboodmohd/-AppInstall/releases/download/v1.1.2/SHA256SUMS
sha256sum -c SHA256SUMS   # must print: appinstall-1.1.2-1-any.pkg.tar.zst: OK
sudo pacman -U appinstall-1.1.2-1-any.pkg.tar.zst
```

The one-command installer performs download + verification +
installation automatically.

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
appinstall --install-url https://example.com/releases/application.AppImage
```
