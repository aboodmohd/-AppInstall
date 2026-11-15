# AppInstall Upgrade Guide

## Upgrading from v1.4.0 to v1.5.0

[v1.4.0](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.4.0)
was published before the QML-default interface, KDE dropdown fixes, and
hover-color corrections were merged. These changes belong to v1.5.0.
Do **not** treat the published v1.4.0 packages as containing them.

The independently versioned `install.sh` identifies itself as v1.2.0
at the time of this upgrade guide. It resolves the latest **published**
stable application release, not an unpublished candidate branch.

### Safe v1.4.0 → v1.5.0 upgrade checklist

1. Keep a verified copy of the published v1.4.0 package and its SHA256SUMS for
   rollback. Never reuse its checksum for a rebuilt v1.5.0 package.
2. Back up managed application records, launchers, settings, and user MIME
   defaults, and verify that the backup contains the expected files.
3. Once the final v1.5.0 package is built from the *approved* source commit,
   verify its SHA256SUMS and inspect `pacman -Qip` and `pacman -Qlp`
   (Arch/CachyOS) or `dpkg-deb -I` (Debian-family).
4. On Arch/CachyOS, install with
   `sudo pacman -U ./appinstall-1.5.0-1-any.pkg.tar.zst`; on supported
   Debian-family systems, use
   `sudo apt install ./appinstall_1.5.0-1_all.deb`.
   Installation changes system packages and requires the user's consent.
5. Confirm `appinstall --version` returns `appinstall 1.5.0`, package file
   integrity is clean, and `appinstall --manage` opens the QML manager.
   Verify Status, Sort, favorite/open/details actions, neutral hover colors,
   and `appinstall --manage --widgets` fallback.
6. Verify previously managed applications and user MIME defaults were
   preserved. If rollback is necessary, reinstall the **verified published**
   v1.4.0 package and recheck records and file associations.

The owner's earlier real CachyOS KDE acceptance verified the UI interactions
in a pre-release development build. It did not establish full end-to-end
AppImage/Flatpak/DEB/RPM lifecycle compatibility. Validate the exact v1.5.0
release artifacts and check the published source-to-package hashes separately.

### Avoid mixed source and system installations

A user-level `~/.local/bin/appinstall` executable may shadow the pacman
package at `/usr/bin/appinstall`. Check `type -a appinstall` and
`command -v appinstall` before testing. Avoid deleting managed apps,
registries, `~/Applications`, or user MIME defaults as an upgrade shortcut.

## Historical upgrade guidance (older releases)

> **Historical note (written before Stable v1.0.0):** the version in this branch is a
> not-yet-published test build. The published release remains
> v1.0.0-beta.1. Do not install over an existing source/user deployment
> before a backed-up spare-system acceptance run and explicit approval.


## Evaluating 1.0.0-rc.1 (testing only)

This release-candidate branch is not Stable 1.0. Avoid installing on a
working system until the clean-install and rollback gates are complete.
All recovery tests should use disposable HOME/XDG directories or a spare
Arch/CachyOS system, not the active user's managed application directories.

### Historical beta upgrade (0.2.0 to 1.0.0-beta.1)

### Package upgrade (Arch/CachyOS)

```sh
sudo pacman -U appinstall-1.0.0beta1-1-any.pkg.tar.zst
```

### Source upgrade

```sh
cd appinstall
git checkout main
git pull --ff-only
./install-user.sh
```

Source installs require running the user-level registration script again to copy the updated modules into your user installation. Registration verifies required source files, stages and fsyncs the replacement files, and retains adjacent recovery backups before publishing. If a write fails, the source installer attempts to restore the previous registration immediately. If the process stops abruptly, rerun the source installer (or installed uninstall helper) to recover the pending journal before reading or changing MIME defaults. The journal and backups are stored in user-controlled directories. Because individual file replacements are atomic but the entire multi-file installation is not, a killed process may temporarily leave a mixture of old and new files until the next registration recovers them. Keep your existing source checkout and application data until recovery completes. If the system package is also installed, the script warns and requires confirmation before creating a second user-level executable.

### What is preserved

- All AppInstall-managed application records (container registry and
  launch-monitor registry)
- User configuration and launchers
- Installed applications (Freebuff, OpenCode, Seanime, Stremio, etc.)
- Shared Distrobox containers (debian-apps, fedora-apps)

### Upgrade caveats

AppInstall is designed to preserve managed records and data, but backups are recommended before upgrades. Existing registry corruption, user changes or an interrupted operation can still require manual recovery.

**Important: mixed installation paths.** A user installation at `~/.local/bin/appinstall` may shadow the pacman package at `/usr/bin/appinstall`. Check `type -a appinstall` and `command -v appinstall` before assuming that the newly installed package is the one being launched. Use `~/.local/bin/appinstall-uninstall` only if you specifically choose to remove a previous source installation. Do not delete `~/.local/share/appinstall` or `~/Applications` to resolve this conflict.

## Rollback

If an upgrade causes problems, revert to the previous package:

```sh
# Package rollback
sudo pacman -U appinstall-0.2.0-1-any.pkg.tar.zst  # if you kept the old package

# Source rollback (from a local checkout with the previous version)
git checkout <previous-commit>
./install-user.sh
```

Managed application data is stored under:
- `~/.local/share/appinstall/` — registries, previews, container state
- `~/.local/state/appinstall/` — launch history, logs
- `~/Applications/` — AppImage installations

Do not delete these directories unless you intend to remove AppInstall
completely.
