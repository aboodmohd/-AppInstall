# AppInstall

A graphical double-click installer for AppImage, Flatpak, DEB, and RPM files on Linux desktops. DEB/RPM applications run in rootless Debian/Fedora Distrobox containers.

**Development status:** tested on CachyOS KDE with selected applications. DEB/RPM compatibility remains application-dependent; some packages omit runtime dependencies or require additional configuration. This project does not guarantee that every Linux package will run.

Install PySide6 for the graphical app preview (for example, `pyside6` on Arch). Without it, KDialog or Zenity provides the confirmation dialog. Flathub previews fetch and cache app names, summaries and icons when online; offline previews use available local information. AppImage details are extracted only after trust confirmation.

Double-click a supported file, review its source and destination, confirm installation, then choose whether to open the application. AppImage downloads are copied into `~/Applications`; the originals remain untouched. Flatpak applications and repositories are installed for the current user.

Managed applications now use monitored launchers. Startup failures show useful errors and logs; open **AppInstall → Application Diagnostics** or run `appinstall --diagnostics` for launch history and safe repair actions. See [Launch Diagnostics](LAUNCH_DIAGNOSTICS.md) for tested behavior and limits.

## Install AppInstall (Arch Linux / CachyOS)

**One-command installation** is available for tested **Arch Linux and CachyOS (x86_64)** desktops. Run this as your normal desktop user (not with `sudo`):

```bash
curl -fsSL https://raw.githubusercontent.com/aboodmohd/-AppInstall/main/install.sh | bash
```

The installer script is **v1.1.0**, but it installs the latest *published Stable AppInstall package* (currently **v1.0.0-1**), not an unreleased application version. It selects stable releases only, downloads the release package and its `SHA256SUMS`, verifies the checksum, and installs through pacman. It prompts before installing; when AppInstall is already up to date, it does not reinstall it.

The installer also checks required dependencies and offers missing optional backends such as Flatpak, rootless Podman, Distrobox, squashfs-tools, fuse2, KDialog/Zenity and libnotify. It will **ask before changing your default file handlers** for AppImage, Flatpak, DEB and RPM (nine MIME types). That choice is optional, per-user only, and the previous defaults are backed up with a restoration script. It does not create Distrobox containers during setup.

Verify the installation or open the application manager:

```bash
appinstall --version
appinstall --manage
```

To **uninstall the AppInstall package** and optionally restore previous file associations (your managed applications, containers and user data are preserved), run:

```bash
curl -fsSL https://raw.githubusercontent.com/aboodmohd/-AppInstall/main/install.sh | bash -s -- --uninstall
```

For a no-changes plan, run `curl -fsSL https://raw.githubusercontent.com/aboodmohd/-AppInstall/main/install.sh | bash -s -- --dry-run`. The `--yes` flag allows unattended installation, but does **not** automatically change file defaults; use `--set-defaults` to opt in, or `--no-defaults` to leave them unchanged. See [INSTALL.md](INSTALL.md) for all flags and installation details.

Only Arch Linux and CachyOS are supported by this one-command package installer today. Other distributions (Debian/Ubuntu, Fedora, openSUSE and others) should use the [source installation instructions](INSTALL.md) instead; never install an Arch `.pkg.tar.zst` on another distribution. DEB/RPM support within the AppInstall application uses Distrobox and is separate from the installer’s supported host distributions.

## Install from source (alternative)


```sh
git clone https://github.com/aboodmohd/-AppInstall.git appinstall
cd appinstall
```

Install Python 3 and either **KDialog** (KDE) or **Zenity** (GNOME/Xfce), then run:

```sh
./install-user.sh
```

The My Applications manager watches for external changes to its managed registries and updates its list automatically, generally within a couple of seconds. The installer registers file associations for the current user and saves their previous values. It does not require root. If Flatpak is missing when installing an application, AppInstall offers setup through apt-get, dnf, pacman or zypper with a PolicyKit administrator prompt. Other systems receive manual instructions. Immutable systems need their distribution's own Flatpak setup procedure.

The Arch package can be built with `makepkg`. Package installation registers AppInstall as an available file handler, **but does not automatically make it the default**. In Dolphin, use **Open With → AppInstall** and select it as the default for each desired format. `./install-user.sh` is for **source installs from a checked-out repository**; do not run it from an extracted pacman package. To inspect possible conflicts between source and package installs, run `type -a appinstall` and see [UPGRADE.md](UPGRADE.md).

## Supported files

- `.AppImage`: ELF type 2 images matching x86-64 or ARM64. Creates an application menu entry and attempts icon extraction after approval. If FUSE 2 is not detected, offers an extracted launch copy when extraction succeeds. Passive preview uses `unsquashfs` without running the AppImage; extracted AppImage application code is run only when you choose to launch it. Only install and launch packages from trusted sources.
- `.flatpak`: local bundle. Required runtimes may still need downloading.
- `.flatpakref`: application reference; downloads the application and runtime as needed. Confirmation displays its repository and runtime source.
- `.flatpakrepo`: adds a repository, rather than installing an application.

Local integration is usually quick. Download speed, runtime size, extraction and dependency setup determine total installation time. Application compatibility still depends on the app and host system.

## CLI

```sh
appinstall FILE.AppImage
appinstall --diagnostics
appinstall --yes --nolaunch FILE.flatpakref
appinstall --dir ~/Games FILE.AppImage
appinstall --list
appinstall --remove NAME
appinstall --detect FILE
```

`--yes` bypasses confirmation and disables the Open prompt. `--nolaunch` suppresses the Open prompt. `APPINSTALL_APPIMAGES` sets the default AppImage directory. Application menu and icon directories respect `XDG_DATA_HOME`; association settings respect `XDG_CONFIG_HOME`.

AppImages with the same embedded application name replace the previous AppInstall-managed version. Extraction and staging must finish before replacement. Launchers preserve embedded application arguments and disable AppImageLauncher interception. Matching old AppImageLauncher shortcuts are backed up before retirement; their payloads are retained.

## Uninstall and recovery

For installs using the **one-command pacman installer**, use the `curl ... | bash -s -- --uninstall` command in [Install AppInstall](#install-appinstall-arch-linux--cachyos). It removes the system package and offers to restore your previous MIME defaults without deleting managed applications, containers or user data.

For **source installs** using `./install-user.sh`, run `~/.local/bin/appinstall-uninstall` to remove user registration and restore prior associations if AppInstall still owns them. Installed applications are kept. `appinstall --remove NAME` removes an AppInstall-managed AppImage; use Flatpak or your software center to remove Flatpak apps.

If your file manager opens AppImages directly, use **Open With → AppInstall**, then choose it as the default. Executable handling varies by file manager. After installing Flatpak for the first time, logging out and back in may be needed for its applications to appear in menus.

## Validation

```sh
python3 -m unittest discover -s tests -v
bash -n appinstall install-user.sh
```

Automated tests cover invalid input, cancellation, Flatpak failure reporting, existing applications, association restoration, AppImage replacement/failure, icon installation, argument preservation and interception bypass. Seanime Denshi was also installed from a real AppImage and launched through its generated desktop entry on KDE. Desktop VM testing on Ubuntu/Mint, Fedora, Arch/CachyOS and openSUSE remains required before claiming verified cross-distribution support. GNOME, KDE and Xfce are the intended desktop targets.

## DEB and RPM on CachyOS (container backend)

AppInstall now routes DEB/RPM files to its container workflow on every host;
it never passes these files to CachyOS's package manager. The older
`native_backend.py` is retained for compatibility tests but is not the active
installation path.

Install these **host dependencies** using your software manager:
`podman`, `distrobox`, `libarchive`, `python`, `pyside6`, and `glib2` (GIO).
Rootless Podman must be configured for your user (including subordinate UID/GID
ranges). AppInstall reports missing dependencies rather than installing them
silently. Do not run AppInstall as root.

Double-click a `.deb` or `.rpm`, or run `appinstall /path/to/package.deb`.
Preview shows metadata, available icon, dependencies and the container method.
After approval, AppInstall prepares/reuses `debian-apps` (Debian 13) or
`fedora-apps` (Fedora 44), using official container images. Distrobox
bootstrap installs integration dependencies. Review the resulting APT/DNF
transaction and click Install. Package maintainer scripts run only during the
approved installation. The original download is preserved; the staged input is
hashed before installation.

Only official Debian/Fedora repositories are accepted by the repository guard.
Additional vendor repositories require manual review and are not enabled by
AppInstall. Unknown repositories cause the operation to stop.

Distrobox shares your home and integrates with your desktop. **It is not a
security sandbox.** Only install trusted packages. Drivers, kernel modules,
system services and packages requiring host integration are unsupported. Package
metadata cannot prove a package is safe or compatible.

Package-provided desktop entries are exported with `distrobox-export --app`.
For multiple launchers, choose the primary application. Exported labels omit
the container suffix; unrelated or modified launcher collisions stop export.
CLI-only packages are recorded without a graphical launcher.

Lifecycle commands use a registry key such as `deb:example` or `rpm:example`:

```sh
appinstall --container-info deb:example
appinstall --container-launch deb:example
appinstall --container-remove deb:example
```

Select the same package file again to reinstall; select a newer file to update.
Registry: `${XDG_DATA_HOME:-~/.local/share}/appinstall/containers/registry.json`.
It records source, hash, version, container, desktop entry, exported launcher and
icon ownership, operation status and user-confirmed GUI launch verification.
Persistent containers are retained after package removal. Uninstall preserves
application data and user-modified or unrelated launchers/icons. Dependency
autoremove is not requested.

Failures and interrupted operations are marked `needs-repair`; retry the same
package or use the removal command. Container package transactions are **not
atomic**: dependency or maintainer-script changes may remain after failure.
AppInstall does not claim to roll those changes back automatically. Container
snapshots and arbitrary cross-format app deduplication are not implemented.
Host desktop export conflict recovery restores overwritten launcher content.

### Validation status

Real integration testing on CachyOS KDE now passes for Debian Galculator and
Fedora Character Map: Dolphin double-click, confirmation, dependency resolution,
export, visible GUI launch, reinstall without duplicate launchers, and uninstall.
The published beta release was qualified with 121 passing automated tests and 10 live acceptance tests on CachyOS KDE. Existing Seanime AppImage and Stremio
Flatpak windows were also visually verified. See [INTEGRATION_TESTING.md](INTEGRATION_TESTING.md)
for exact evidence, tested scope, storage and limitations.

Containers have separate application HOME directories and read-only package
staging. Distrobox still shares host resources, including access to the host
home; it is not a security sandbox. Container initialization and images need
roughly 2.7 GiB for these two environments. First-time setup is substantially
slower than subsequent app installation.

### Rollback of this development change

The source and affected user files were backed up to:
`~/appinstall-backups/20261101-215534/`.
Restore `source/` to `~/appinstall/`, `binary` to `~/.local/bin/appinstall`, and
`installed/` to `~/.local/share/appinstall/` to return to the previous code.
The backup also contains the application-launcher directory and MIME config;
restore individual affected files rather than replacing unrelated later changes.
Real integration testing subsequently created `debian-apps` and `fedora-apps`; see the integration report before removing either. If you later create
containers, uninstall their recorded apps first; remove containers only after
checking their contents. Reverting source code does not undo package transactions.
