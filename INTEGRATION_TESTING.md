# Real integration testing — 2026-11-01

Environment: CachyOS, KDE Plasma, Wayland, x86-64. Testing was explicitly authorized.

## Results

| Check | Evidence and outcome |
|---|---|
| Host dependencies | Installed Podman 6.1.4 and Distrobox 1.8.2.5 from configured official CachyOS/Arch repositories. 12 packages, 32.12 MiB download, 107.23 MiB installed. |
| Boot safety | Inspected transaction archives and applicable hooks before installation. No kernel, GRUB, EFI, or initramfs package changes. Actual hooks performed tmpfiles, manager reloads, icon updates, and Snapper snapshots 35/36. No macOS changes. |
| Rootless operation | `podman info` reports rootless=true; UID/GID maps contain user 1000 and subordinate range 100000–165535. Existing mappings were sufficient; no edits required. |
| Persistent containers | `debian-apps`: official Debian 13 image; `fedora-apps`: official Fedora 44 image. Both start and execute APT/DNF without host root privileges. |
| DEB metadata | Galculator 2.1.4-2, amd64, from Debian trixie/main. Name, description, dependencies, maintainer and bundled icon displayed in the actual GUI. |
| RPM metadata | Character Map (`gucharmap`) 18.0.0-2.fc44, x86_64, downloaded from Fedora's official repository using DNF. Parsed application name, metadata and desktop icon name. |
| Dolphin DEB | A real virtual-pointer double-click on the downloaded file in Dolphin opened AppInstall. No silent installation. Preparation confirmation, transaction review and Install were activated through the actual accessible Qt controls. |
| Dolphin RPM | The same Dolphin double-click and real Qt-confirmation workflow succeeded for the RPM. |
| Dependency resolution | AppInstall ran APT/DNF transaction previews and installed local package files plus official-repository dependencies inside their respective containers. No host DEB/RPM installation. |
| DEB export and launch | Distrobox exported `debian-apps-galculator.desktop`, with Name=Galculator, Icon=galculator, Categories=Utility. One KDE application result. Launch through the exported entry and through KDE search succeeded; calculator window visually inspected. |
| RPM export and launch | Distrobox exported `fedora-apps-gucharmap.desktop`, with Name=Character Map, Icon=accessories-character-map, Categories=GNOME;GTK;Utility. One KDE application result. Actual Character Map window visually inspected, including a launch from KDE search. |
| Reinstallation | Both packages reinstalled through the actual AppInstall UI. Registry and host launcher checks showed one package record and one exported launcher per application. |
| Cancellation | Declined Galculator removal first; operation stayed available and the application was not removed. Then explicitly confirmed removal. |
| Uninstall | Removed both test packages through AppInstall's confirmation UI. Container package databases report them absent, registry is empty, managed launchers are gone, and KDE search has zero application results for both. Test windows were closed. Application data and dependency packages were preserved. |
| AppImage regression | Existing Seanime Denshi AppInstall launcher/backend started successfully. Visually inspected its rendered application window. AppImage install/replace regression tests also pass; no fresh AppImage installation was performed in this phase. |
| Flatpak regression | Existing Stremio launched and its populated interface was visually inspected. Its `.flatpakref` was also processed with `--yes --nolaunch` to exercise the existing-install path. Runtime emitted application warnings, but the window rendered. No new Flatpak application was installed in this phase. |
| Automated tests | 31 tests pass, including all original 11, container fixtures, interruption recovery, export rollback, repository-comment handling, themed icons, private HOME and read-only staging. Bash syntax, Python compilation and desktop validation pass. |

Screenshots and package hashes/metadata are stored locally under:
`~/.local/share/appinstall/integration-results/`.
The desktop tests used AT-SPI and a temporary uinput pointer device with the
user's existing device ACL. The original runtime accessibility setting was
restored afterward. These manual helpers are under `tools/`; they are not used
by the product and do not run as part of unit tests.

## Fixes made during testing

- Use the requested persistent names `debian-apps` and `fedora-apps`.
- Give containers separate application HOME directories and explicitly mount
  package staging read-only.
- Ignore commented URLs in APT source files; continue rejecting unknown active
  HTTP(S) repository hosts. Official Debian image comments had blocked startup.
- Stream backend command output into the Qt progress view.
- Resolve preview themed icons from the package's desktop entry when no image
  is bundled directly.
- Preview reinstall transactions using the same reinstall operation performed
  after confirmation.
- Add regression tests for the newly observed behaviors.

## Storage and cleanup

After removing the two test applications:

- Official images: approximately **630 MB** (Podman logical image accounting).
- Container writable layers: approximately **2.09 GB** combined.
- Actual storage directory excluding merged overlay mounts: **2.7 GiB** by
  `podman unshare du -sxh ~/.local/share/containers/storage`.
- AppInstall container state, package inputs and preview cache: about **4.7 MiB**.
- Host dependency download inspection cache: **33 MiB**.
- Original DEB/RPM downloads: **1.5 MiB**, retained in
  `~/Downloads/AppInstall-Integration/`.
- Filesystem: about **42 GiB free** after testing. Btrfs compression/shared
  extents mean logical usage does not equal the change in physical free space.

Both containers remain running and reusable. AppInstall deliberately does not
remove application data, shared dependency packages or containers automatically.
Containers may be stopped when idle using `distrobox stop debian-apps` and
`distrobox stop fedora-apps`; starting an exported application starts its box.
Do not use global Podman prune operations to clean unrelated containers.

## Limits of this verification

This verifies two trusted graphical packages on this CachyOS desktop, not all
DEB/RPM packages, distributions, drivers or hardware. Distrobox's standard
rootless integration uses host mounts and its default privileged settings
inside the user namespace. It is not a security sandbox; separate application
HOME directories do not revoke access to the host home. No rootful containers
were created. Packages needing system services, drivers or kernel modules
remain unsupported. GUI installation cannot roll back arbitrary package scripts
or dependency changes atomically; failed operations remain marked for repair.

## Changed files and rollback

Production changes in this phase: `container_backend.py`, `container_ui.py`,
`PKGBUILD`, and README. Updated `tests/test_containers.py`; added the explicit
manual test helpers in `tools/` and this report. The installed helper copies
were refreshed through the existing user installer.

Pre-test source backup: `~/appinstall-backups/20261101-220324/source/`.
The earlier complete user-file backup remains at
`~/appinstall-backups/20261101-215534/`.
Restore source files from the newer backup and run `./install-user.sh` to revert
code. This does not remove dependencies or containers. Review container data
before separately removing only the named test containers. Do not restore an
entire applications/config directory over later unrelated user changes.


## OpenCode follow-up — 23:13

OpenCode 2.2.5 supplied a hidden compatibility launcher and a visible launcher.
AppInstall had offered both. The backend now filters NoDisplay/Hidden entries,
records export ownership immediately, and marks export failures for repair.
There are now 33 passing tests. The visible OpenCode launcher was exported;
the pre-existing hidden entry was preserved. Exactly one entry is visible.

A separate startup failure was caused by the existing host OpenCode service
occupying port 49374. Backed up the container settings and used its bundled CLI
to set only the container service to 49475. The host process remained running
on 49374. Visually verified the populated OpenCode projects/sessions screen.
Backup: `~/appinstall-backups/opencode-20261101-231000/`.
