# Stable v1.0 readiness checklist

AppInstall `v1.0.0-beta.1` is published. This checklist is for a possible
future **stable v1.0.0** release. It does not claim general Linux compatibility.

## Automated checks introduced

- Existing Ubuntu headless test suite and Bash syntax validation.
- Arch Linux container: full source tests, checksum-validated `makepkg` build,
  `pacman` install, same-version upgrade and removal.
- Fedora 44 container: full source tests with Fedora-provided PySide6.
- Source/user registration upgrade tests using a temporary HOME/XDG directory:
  preservation of managed records, original defaults and user-changed defaults.

These checks run in disposable CI environments. In particular, they cannot
verify that GUI windows work under KDE, GNOME or Xfce, or that every
third-party AppImage/Flatpak/DEB/RPM is compatible.

## Real-device testing reported on CachyOS (2026-11-03)

A tester exercised Dolphin double-click installation and KDE/AppInstall launch
for a sample of all four formats, plus an uninstall/reinstall cycle without a
duplicate launcher. On that device, a missing WebKitGTK host dependency was
needed for an AnymeX AppImage. The Mizuki AppImage's upstream AppRun script
searched for legacy executable names while packaging a binary called Mizuki;
a user-local extracted-launch workaround was required. This evidence is
encouraging but does not establish arbitrary application compatibility.

The live My Applications inventory refresh and the safe handling of missing
old AppImage manifests have automated regression tests. Repeat these workflows
in a real KDE session before publishing the stable release. A stale launcher
must not be deleted automatically when its ownership data is missing.

## Manual work required before stable release

- Test an actual clean install and rollback on a spare Arch/CachyOS system.
- Test upgrade and uninstall with existing real managed apps and user data.
- Exercise double-click, default MIME selection, dialogs and error displays on
  real KDE Wayland/X11 (and GNOME/Xfce if claiming those desktops).
- Exercise real signed/test packages for every format, including missing
  runtime dependencies and network interruptions.
- Review open bugs, security boundaries and third-party licensing.
- Independently verify final source, release binary checksums and packaging.

Do not retag or overwrite the already published beta. Cut a new version/tag
only after these conditions are supported by test evidence and release approval.
