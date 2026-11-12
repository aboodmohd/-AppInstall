# AppInstall Installation Guide

AppInstall 1.0.0 remains the latest **published stable** application release:
[`v1.0.0`](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.0.0).
Version 1.1.0 is being prepared but is not published. The manual package
download URLs below still refer to the published v1.0.0.

## One-command installation (Arch/CachyOS)

The separately versioned installer script `install.sh` (v1.1.0) is available
on `main`. It installs only the latest **published stable** AppInstall
package on tested Arch/CachyOS x86_64 desktops. Run as a regular user:

```sh
curl -fsSL https://raw.githubusercontent.com/aboodmohd/-AppInstall/main/install.sh | bash
```

To review this checkout without installing anything:

```sh
bash install.sh --dry-run
```

Run as your regular desktop user with Bash, curl, coreutils, pacman and sudo.
If Python is missing, setup asks to install it from your configured pacman
repositories. Pacman installs required application dependencies, including
PySide6. Optional backends are offered separately. Keep the system fully
updated before installing packages; setup does not refresh databases alone.

When run without `--dry-run`, the installer downloads and verifies
the package plus `SHA256SUMS`, installs through
`sudo pacman -U` (package installation and optional backend installation use root; the
app itself never runs as root), offers missing optional backends, and asks for
one clear confirmation before making AppInstall the default handler for
supported package formats. Your previous per-user associations are backed up
and restorable (`~/.local/share/appinstall/installer/restore-mime-defaults.sh`).

Installer flags: `--yes` (answer install prompts), `--set-defaults` (opt into
default handler changes noninteractively), `--no-defaults`, `--dry-run` (plan
without changes), `--uninstall`. Re-running is safe and idempotent.

Other distributions are not covered by this one-command installer yet — see
"Install from source" below. Do not install the Arch `.pkg.tar.zst` package with
another distribution's package manager.

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

Download from the [`v1.0.0` release](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.0.0):

```sh
curl -LO https://github.com/aboodmohd/-AppInstall/releases/download/v1.0.0/appinstall-1.0.0-1-any.pkg.tar.zst
curl -LO https://github.com/aboodmohd/-AppInstall/releases/download/v1.0.0/SHA256SUMS
sha256sum -c SHA256SUMS   # must print: appinstall-1.0.0-1-any.pkg.tar.zst: OK
sudo pacman -U appinstall-1.0.0-1-any.pkg.tar.zst
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
