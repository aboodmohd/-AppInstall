# AppInstall Upgrade Guide

## Upgrading from v1.5.0 to v1.6.0

Version 1.6.0 adds an independently packaged Fedora 44 RPM while retaining
the Arch and Debian package formats and the default QML manager. It does
not change the user's managed application records or install third-party
applications during a host package upgrade. The one-command installer
(`install.sh`) is independently versioned at 1.3.0.

**Before upgrading:** Keep the already published v1.5.0 package and its
checksum manifest, and back up AppInstall records, launchers, settings,
user MIME defaults and active applications. Read `KNOWN_LIMITATIONS.md`.

Once v1.6.0 is **published**, obtain the correct package for the host and
verify its `SHA256SUMS`:

- Arch/CachyOS: `sudo pacman -U ./appinstall-1.6.0-1-any.pkg.tar.zst`
- Debian/Ubuntu/Mint: `sudo apt install ./appinstall_1.6.0-1_all.deb`
- Fedora 44 (x86_64): `sudo dnf install ./appinstall-1.6.0-1.noarch.rpm`

Fedora 43/45, RHEL, openSUSE and other unverified distributions remain
unsupported by the one-command installation path. Do not force a native
package from another distro.

After installation, verify `appinstall --version` reports 1.6.0, then run
`appinstall --manage`, `appinstall --manage --widgets`, and check the
installed applications, favorites, Open/Details actions, Status and Sort menus,
and preserved file associations. On Fedora, verify the installed package
with `rpm -V appinstall`; on Arch, use `pacman -Qkk appinstall`.

For rollback, reinstall a separately verified prior native package for the
same distribution and recheck all records and file associations. The public
v1.5.0 release has no Fedora RPM, so Fedora has **no same-project prior
native RPM rollback artifact** from v1.5.0. Keep your local Fedora
candidate only for development rollback; consult system package history
and backups. A package rollback does not undo unrelated application
transactions.

## Historical: Upgrading from v1.4.0 to v1.5.0

[v1.4.0](https://github.com/aboodmohd/-AppInstall/releases/tag/v1.4.0)
was published before the QML-default interface, KDE dropdown fixes, and
hover-color corrections were merged. These changes belong to v1.5.0.
Do **not** treat the published v1.4.0 packages as containing them.

The one-command installer is independently versioned from AppInstall.
It resolves the latest **published** stable application release, not
an unpublished candidate branch.

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
# Migration from the legacy `appinstall` package

AppInstall now uses the native package and command `abood-appinstall` on
Arch/CachyOS, Debian/Ubuntu and Fedora. Its desktop ID is
`io.github.aboodmohd.AppInstall.desktop`; the application menu still says
**AppInstall**. The new package deliberately does not provide, conflict with,
replace, or obsolete `appinstall`: that name also belongs to an unrelated AUR
project. No installer or uninstaller should remove it by name alone.

On CachyOS, an AUR update through Yay offered an unrelated `appinstall`
2.0.8-1 as an upgrade to the official v1.9.0 package because both used the
same package name. The v1.9.1 identity separates those packages. If the
collision already happened, leave the unrelated package alone and install
`abood-appinstall` alongside it.

1. Close AppInstall, and back up `$XDG_DATA_HOME/appinstall`,
   `$XDG_STATE_HOME/appinstall` (defaulting to `~/.local/share` and
   `~/.local/state` respectively), and `mimeapps.list`. Leave managed apps,
   Flatpak installations and Distrobox storage in place.
2. For a **legacy native** install, use the [published one-command installer](INSTALL.md#one-command-installation)
   or install the checksum-verified native package alongside the legacy
   package (`pacman -U` for Arch/CachyOS, `apt install` for Debian/Ubuntu,
   `dnf install` for Fedora). Run `abood-appinstall --version` and open
   `abood-appinstall --manage` to verify that your records are present.

   To switch all nine defaults with the published installer, pass
   `--set-defaults` to it. That option queries the published release feed;
   for an unpublished CI build or a local package install, set and verify
   the defaults directly as your desktop user:

   ```bash
   (
     set -euo pipefail
     id=io.github.aboodmohd.AppInstall.desktop
     entry=/usr/share/applications/$id
     test -r "$entry"
     mapfile -t mimes < <(sed -n 's/^MimeType=//p' "$entry" | tr ';' '\n' | grep .)
     test "${#mimes[@]}" -eq 9
     for mime in "${mimes[@]}"; do
       xdg-mime default "$id" "$mime"
       test "$(xdg-mime query default "$mime")" = "$id"
     done
   )
   ```

   Retire the legacy package only after checking that it owns the old
   launcher and that its upstream is `https://github.com/aboodmohd/-AppInstall`.
   On Arch/CachyOS, use `pacman -Qo /usr/bin/appinstall` and `pacman -Qi appinstall`
   to verify both before running `sudo pacman -R -- appinstall`. On other
   systems, use the corresponding native ownership and metadata queries.
   If any check is inconclusive, or identifies the unrelated AppInstaller,
   leave it untouched. Do not use recursive removal or purge.
3. For a **legacy portable** install, verify the existing source uninstaller
   belongs to this project, then run it **before** running `install-user.sh`
   from the new verified portable bundle. The uninstaller removes legacy
   launcher/registration files, not managed apps or records. If it cannot
   be verified, stop and inspect the install rather than running it. The new
   user commands are `~/.local/bin/abood-appinstall` and
   `~/.local/bin/abood-appinstall-uninstall`.
4. To roll back, remove only `abood-appinstall` using its installer or portable
   uninstaller, then reinstall a checksum-verified official artifact and
   restore your saved associations. Only roll back to the legacy native name
   if the unrelated package does not occupy that name and you explicitly
   exclude `appinstall` from AUR upgrades while using it.

The application data directories and container registry are not renamed.
The pre-migration desktop updater cannot perform this identity change;
use the verified package or bundle directly for the first migration.

## v1.9.1 to v1.9.2 reliability upgrade

No data migration is required. Install the verified native package or portable bundle over v1.9.1; application data, container registries, settings, launchers and MIME defaults remain in the same locations. The Premium UI and `abood-appinstall` command are unchanged.

Existing Flatpak launchers adopted before v1.9.2 remain monitored wrappers; new adoptions preserve Flatpak's live export symlink. If you want an existing launcher converted, remove its local copy only after confirming a native export exists at `~/.local/share/flatpak/exports/share/applications/<appid>.desktop` (or the system equivalent), then re-run the Flatpak registration. Do not delete managed applications or containers.
