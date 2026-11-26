# AppInstall Installation Guide

The new package and launcher identity is `abood-appinstall`. For existing installations, see [migration and rollback](UPGRADE.md#migration-from-the-legacy-appinstall-package). Do not install the unrelated `appinstall` from the AUR.

## One-command installation

Run the installer as your regular desktop user:

```sh
curl -fsSL https://raw.githubusercontent.com/aboodmohd/-AppInstall/main/install.sh | bash
```

The installer selects the **native** package from the latest published
stable GitHub release and checks its SHA-256 before any package operation.
Arch Linux and CachyOS use pacman; Debian 13, Ubuntu 24.04/26.04 and Linux
Mint 22 use APT; and Fedora 44 x86_64 uses DNF when the release includes
the matching RPM. The installer rejects unsupported platforms or a missing
native asset, never substituting an Arch or Debian package. Ensure Python 3
and curl are available; Ubuntu needs the Universe repository enabled.

APT installs the selected `.deb` with `--no-install-recommends`. The package
declares alternative Qt bindings so APT can satisfy the dependency from the
distribution's repositories. Install optional backends separately as needed.
On Arch and CachyOS, the installer offers optional backends after setup.

Use `--dry-run` to inspect the package selection and `--uninstall` to remove
AppInstall. Use `--set-defaults` to opt into changing per-user file handlers
or `--no-defaults` to keep them. Previous defaults are backed up.

## Portable source route for other Linux distributions (v1.9.2)

**Use this route if the native one-command installer rejects your host.**
It is suitable for Linux desktop systems capable of running Python 3, Bash,
freedesktop xdg-utils and PySide6/Qt Quick. It does not need root for
AppInstall itself and does not attempt to run foreign package managers.
Not all distributions or desktop sessions are tested.

The **published** v1.9.2 release includes the portable archive and a matching
SHA256SUMS manifest. Download both from the
[v1.9.2 release page](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.9.2),
verify the archive's hash, then install as your regular desktop user:

```bash
sha256sum --ignore-missing -c SHA256SUMS
tar -xzf appinstall-1.9.2-portable.tar.gz
cd appinstall-1.9.2
bash ./install-user.sh
~/.local/bin/abood-appinstall --version
~/.local/bin/abood-appinstall --manage
```

On a distribution where `git` is available, an equivalent source workflow
can be used with the **published v1.9.2 tag**:

```bash
git clone --depth 1 --branch v1.9.2 https://github.com/aboodmohd/-AppInstall.git
cd -- -AppInstall
bash ./install-user.sh
```

The portable route is user-local. Uninstall it using
`~/.local/bin/abood-appinstall-uninstall`, not `sudo dnf/pacman/apt remove`.
It warns and requests interactive permission if a native AppInstall is
installed by pacman, dpkg or RPM. If the PySide6/Qt Quick dependency is
absent, Discover Apps cannot open; KDialog/Zenity CLI fallback may still
work for some operations. Install graphical dependencies through your
distribution's repository, not a guessed native AppInstall package.

The v1.9.2 native CI targets remain **Arch/CachyOS, Debian 13,
Ubuntu 24.04/26.04, Linux Mint 22 and Fedora 44**, on x86_64.
Other distributions require independent compatibility checks; this
portable option is not a guarantee that every application will work.
See `RELEASE_NOTES.md`.

## Native Fedora 44 RPM (introduced in v1.6.0)

Fedora 44 (x86_64) uses DNF and the native
`abood-appinstall-1.9.2-1.noarch.rpm` package. The one-command installer
fetches it only from a published stable release alongside `SHA256SUMS`,
validates the package checksum and RPM name/version/architecture and
obtains user consent before installing via DNF.

Advanced users can build from source **on Fedora 44 as a non-root user**
after installing `rpm-build` and dependencies:

```bash
bash tools/build_rpm.sh dist
```

Verify the generated RPM and install the locally built package explicitly with
`sudo dnf install ./dist/abood-appinstall-1.9.2-1.noarch.rpm`. The rpm
builder is not a substitute for a release checksum. Use the
release's verified downloadable RPM for normal installation; CI tests are
not live desktop acceptance.

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

Download from [the v1.9.2 release](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.9.2):

```sh
curl -fLO https://github.com/aboodmohd/-AppInstall/releases/download/v1.9.2/abood-appinstall-1.9.2-1-any.pkg.tar.zst
curl -fLO https://github.com/aboodmohd/-AppInstall/releases/download/v1.9.2/SHA256SUMS
sha256sum --ignore-missing -c SHA256SUMS
sudo pacman -U ./abood-appinstall-1.9.2-1-any.pkg.tar.zst
```

For the published release, check that the output includes
`abood-appinstall-1.9.2-1-any.pkg.tar.zst: OK` before installing.

The one-command installer performs download + verification +
installation automatically.

The new package installs `/usr/bin/abood-appinstall` and registers `/usr/share/applications/io.github.aboodmohd.AppInstall.desktop` as an *available* file handler. It does **not** change your existing default file associations. For a file that opens in another application, right-click it in Dolphin and select **Open With → AppInstall**, then choose AppInstall as the default only if you want to. Some file managers may prefer executable AppImage handling over a MIME default.

To open the Installed Applications Manager:

```sh
abood-appinstall --manage
```

## Install from source

```sh
git clone https://github.com/aboodmohd/-AppInstall.git appinstall
cd appinstall
./install-user.sh
```

## What install-user.sh does

- Registers `io.github.aboodmohd.AppInstall.desktop` as the default handler for supported MIME types
- Copies AppInstall modules to `~/.local/share/appinstall/`
- Copies the launcher to `~/.local/bin/abood-appinstall`
- Creates `~/.local/bin/abood-appinstall-uninstall`
- Migrates existing launchers via `launch_monitor.synchronize()`

## Uninstall

For a source/user installation:

```sh
~/.local/bin/abood-appinstall-uninstall
```

This restores previous MIME associations that AppInstall still owns and removes the user-level registration. For a pacman-managed system package, run `install.sh --uninstall` instead. Do not run the source uninstaller as a substitute for removing the system package. Managed applications and their data are kept.

## Avoid mixed installations

A previous source installation in `~/.local/bin/abood-appinstall` can take precedence over the packaged `/usr/bin/abood-appinstall` depending on your `PATH`. After installing or upgrading, check:

```sh
type -a abood-appinstall
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
abood-appinstall FILE.AppImage
abood-appinstall --manage          # Installed Applications Manager
abood-appinstall --diagnostics     # Application Diagnostics
abood-appinstall --list            # List managed applications
abood-appinstall --remove NAME     # Remove a managed application
abood-appinstall --install-url https://example.com/releases/application.AppImage
```
