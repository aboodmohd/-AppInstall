# AppInstall 1.0.0-beta.1 Release Notes

AppInstall is a graphical double-click installer for AppImage, Flatpak, DEB,
and RPM files on Linux desktops. DEB/RPM applications run in rootless
Distrobox containers. This is the first public beta release candidate.

## What's new in 1.0.0-beta.1

- **Installed Applications Manager**: Open AppInstall-managed applications,
  view details, launch, repair launchers, reinstall, and safely uninstall
  through one graphical interface (`appinstall --manage`).
- **Secure AppImage preview**: AppImages are never executed to display
  metadata. Contents are inspected passively via `unsquashfs` only.
- **Modern PySide6 UI**: Light/dark theme support, consistent styling across
  installer and manager, progress indicators, success/failure dialogs.
- **Launch monitoring**: Application startup is monitored; failures show
  useful errors and logs through Application Diagnostics.

## Supported package formats

| Format | Backend | Installation | Notes |
|--------|---------|--------------|-------|
| AppImage | AppImage | Copied to `~/Applications` | Passive preview via `unsquashfs` |
| Flatpak | Flatpak | User installation via `flatpak --user` | Update supported |
| DEB | Distrobox (Debian) | Rootless container | DEB/RPM compatibility varies |
| RPM | Distrobox (Fedora) | Rootless container | DEB/RPM compatibility varies |

## Installation

### From Arch/CachyOS package

```sh
# Install the package (requires pacman)
sudo pacman -U appinstall-1.0.0beta1-1-any.pkg.tar.zst
```

The package installs `appinstall` to `/usr/bin/appinstall` and registers `/usr/share/applications/appinstall.desktop` as an available handler for supported formats. It does **not** override the user's default file associations. If double-click opens another application, choose **Open With → AppInstall** in your file manager and set the default if desired. Executable AppImage handling may vary by file manager.

To open the Installed Applications Manager:

```sh
appinstall --manage
```

### From source

```sh
git clone https://github.com/aboodmohd/-AppInstall.git appinstall
cd appinstall
./install-user.sh
```

## Requirements

- Python 3
- bash, coreutils, xdg-utils
- PySide6 (for graphical interface)
- kdialog or zenity (for fallback dialogs)
- flatpak (for Flatpak installation)
- podman + distrobox (for DEB/RPM containers)
- squashfs-tools (for passive AppImage preview — recommended)

## Installation method conflicts

If AppInstall was previously installed from source, `~/.local/bin/appinstall` may shadow a newer pacman-managed `/usr/bin/appinstall`. Run `type -a appinstall` to identify duplicates and consult [UPGRADE.md](UPGRADE.md) before removing the old user-level installation. Do not remove managed applications or data folders to fix a PATH conflict.

## Known limitations

- DEB/RPM compatibility is not universal; some packages omit runtime
  dependencies or require additional configuration.
- Containers do not guarantee security isolation.
- Certain system services, kernel modules, and drivers are unsupported.
- Some runtime dependencies may be discovered only during launch.
- GUI launch monitoring cannot always prove that an application is usable.
- Flatpak update support only; DEB/RPM updates require reinstalling with a
  newer package file.

See `KNOWN_LIMITATIONS.md` for details.

## Security

AppImage previews never execute the image. Detailed preview information is
unavailable without `squashfs-tools`; the installer degrades gracefully to a
generic icon and honest notice.
