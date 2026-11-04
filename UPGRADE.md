# AppInstall Upgrade Guide

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
