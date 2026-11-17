# AppInstall v1.8 — Cross-distro update support

**Scope: widest practical Linux coverage without forcing another
distribution's package format onto the host.**

| How AppInstall was installed | Update AppInstall itself | Update managed applications |
| --- | --- | --- |
| Arch/CachyOS native package | Verified release .pkg.tar.zst via pacman | Flatpak, eligible AppImage, and explicitly owned DEB/RPM Distrobox records |
| Debian/Ubuntu/Mint native package | Verified release .deb via APT | Same backend-specific rules; requires relevant local tools |
| Fedora 44 native package | Verified release .rpm via DNF | Same backend-specific rules; requires relevant local tools |
| Portable user-source, any suitable Linux distro | New verified stable portable .tar.gz via user-local recoverable installer | Flatpak where Flatpak is available, eligible AppImage where updater is installed, and owned container packages only where Podman/Distrobox/guest backend is supported |

**"All Linux distros" means a distribution-neutral fallback, not a guarantee**
that Qt Quick, FUSE, Flatpak, Podman/Distrobox, desktop integration or all
applications work on every distro/architecture. The portable CLI may work
where the GUI or a particular backend cannot.

## Portable update contract

- Source install is opted into through a **published stable portable archive**
  and \`install-user.sh\`. It must be a real user-local installation, not an
  unpacked checkout or a system package.
- \`portable_update.py --desktop-check\` is **read-only**. It queries only the
  latest official stable GitHub release and compares strict numeric versions.
  Drafts, prereleases, malformed tags, missing assets and suspicious URLs are
  rejected.
- In the QML manager, **Install update** asks for a second confirmation.
  The helper revalidates the exact published tag, downloads
  \`appinstall-V-portable.tar.gz\` plus \`SHA256SUMS\` over HTTPS, enforces
  size/redirect bounds and verifies the SHA-256 digest **before unpacking**.
- Extraction refuses traversal, symlinks, nonregular entries, excessive
  count/size and a different embedded version. Installation uses the
  existing per-user \`SourceTransaction\` with staging, journaling and
  recovery. It does **not** invoke pacman/APT/DNF or install dependencies.
- AppInstall data, settings, managed application records and MIME defaults
  are preserved. The source transaction protects replaced source files,
  **not** arbitrary third-party launcher migrations; interrupting updates
  or losing power can still need manual recovery.
- An existing native package blocks portable self-update, preventing the
  user-local executable from unexpectedly shadowing a package-managed copy.
- GitHub's checksums verify archive integrity, not an independent publisher
  signature. Only trust an official release from the project you intend to
  install. No automatic/silent updater is enabled.

## First installation on an unlisted distro

The existing \`install.sh\` intentionally refuses unknown native package
families. For a portable user-level installation instead:

1. Install a working Python 3, Bash, tar and gzip; add PySide6/Qt Quick for
   the full graphical manager and the other tools required by the particular
   source you want to install.
2. Download the **latest published stable** portable archive and the
   release's common \`SHA256SUMS\` from GitHub. Independently compare the
   exact expected filename/hash; unpack only after validation.
3. Run \`bash install-user.sh\` in the unpacked official archive as an ordinary
   user. The installer refuses to silently shadow a native installation.
4. On future stable releases the GUI can check and update this **portable**
   installation, or invoke
   \`python3 ~/.local/share/appinstall/portable_update.py --check\`
   for a read-only check.
5. To apply a specific offered stable version from a terminal, use
   \`python3 ~/.local/share/appinstall/portable_update.py --update vX.Y.Z\`.
   This explicitly performs the user-local update; never run with sudo.

**Not supported:** silently installing a DEB on Arch, pacman archives on
Fedora, or RPMs on Alpine; bypassing an operating system package manager's
ownership/upgrade rules; claiming all Flatpaks or AppImages can update; or
promising a full Qt desktop on every Linux family. Real desktop acceptance
remains a required release gate.
