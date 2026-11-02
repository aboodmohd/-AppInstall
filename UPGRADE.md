# AppInstall Upgrade Guide

## Upgrading from 0.2.0 to 1.0.0-beta.1

### Package upgrade (Arch/CachyOS)

```sh
sudo pacman -U appinstall-1.0.0beta1-1-any.pkg.tar.zst
```

### Source upgrade

```sh
cd appinstall
git checkout 1.0-beta
git pull
# or: git fetch && git merge origin/1.0-beta
```

### What is preserved

- All AppInstall-managed application records (container registry and
  launch-monitor registry)
- User configuration and launchers
- Installed applications (Freebuff, OpenCode, Seanime, Stremio, etc.)
- Shared Distrobox containers (debian-apps, fedora-apps)

### What is not preserved

- Nothing — this is an in-place upgrade. All managed data is preserved.

## Rollback

If an upgrade causes problems, revert to the previous package:

```sh
# Package rollback
sudo pacman -U appinstall-0.2.0-1-any.pkg.tar.zst  # if you kept the old package

# Source rollback
git checkout <previous-commit>
```

Managed application data is stored under:
- `~/.local/share/appinstall/` — registries, previews, container state
- `~/.local/state/appinstall/` — launch history, logs
- `~/Applications/` — AppImage installations

Do not delete these directories unless you intend to remove AppInstall
completely.
