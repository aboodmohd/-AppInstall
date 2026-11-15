# AppInstall v1.5.0 — release candidate

AppInstall v1.5.0 updates the **My Applications** interface. The Qt Quick/QML
manager is now the default when you run `appinstall --manage` or open AppInstall
without an installation request. The previous Qt Widgets manager remains
available through `appinstall --manage --widgets`.

## What's new

- A redesigned, keyboard-accessible application list with search, format chips,
  installed-state filtering, sorting, favorites, package sizes, and available
  actions for each managed application.
- Status and Sort menus now open reliably on tested KDE Wayland sessions and
  update the visible application list when an option is selected.
- Corrected KDE QML startup/runtime warnings for delegate indices, hover state,
  unsupported icon URLs, and ComboBox content compatibility.
- Corrected Qt alpha-color notation that made hovered cards bright yellow.
  Hover feedback is now neutral in light and dark modes.
- The application records, source-format install actions, Diagnostics,
  existing desktop file associations, and legacy Widgets manager are retained.

## Supported and tested environments

- On the owner's CachyOS KDE Wayland desktop, both menus and the neutral hover
  behavior were reported working after PR #69. This is real-device UI acceptance,
  not a new end-to-end test of every installer backend.
- GitHub CI tests isolated X11, Weston Wayland, virtual KWin Wayland, Arch,
  Fedora, and Debian-family packaging. These environments do not certify every
  real desktop or third-party AppImage, Flatpak, DEB, or RPM.
- DEB/RPM apps use rootless Distrobox containers, not a security sandbox.

## Upgrade and rollback

Before upgrading, back up your AppInstall settings, application/launcher
records, and MIME associations. Verify the release's `SHA256SUMS` manifest
against the downloaded package and inspect the package before installation.

Arch / CachyOS: `sudo pacman -U ./appinstall-1.5.0-1-any.pkg.tar.zst`

Debian-family: `sudo apt install ./appinstall_1.5.0-1_all.deb`

After installing, verify `appinstall --version`, `appinstall --manage`,
`appinstall --manage --widgets`, and existing managed applications. Retain a
verified v1.4.0 package as a rollback option; restoring older package code
does not undo unrelated application transactions.

**Publication status:** This text documents a candidate. A public v1.5.0
release, exact package hashes and downloadable assets must not be claimed
until the final source commit and artifacts are verified and publication is
separately approved.
