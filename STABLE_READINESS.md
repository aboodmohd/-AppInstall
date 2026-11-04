# Stable v1.0 readiness checklist

AppInstall `v1.0.0-beta.1` is published. This checklist tracks the **unpublished stable v1.0.0** preflight build; it is not a public release. It does not claim general Linux compatibility.

## Automated checks introduced

- Existing Ubuntu headless test suite and Bash syntax validation.
- Arch Linux container: full source tests, checksum-validated `makepkg` build,
  `pacman` install, same-version upgrade and removal.
- Fedora 44 container: full source tests with Fedora-provided PySide6.
- Source/user registration upgrade tests using a temporary HOME/XDG directory:
  preservation of managed records, original defaults and user-changed defaults.
- Isolated clean user registration and uninstall, including preservation of
  managed application records, plus refusal to update from incomplete source trees.
- Disk-full and abrupt-exit fault-injection tests for the source file update
  journal, preserving old installed modules and MIME settings after recovery.
  Recheck on real KDE hardware and an actual low-space filesystem before stable.

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

## Final audit findings (2026-11-04)

- **Merged in PR #8 (2026-11-04):** AppImage desktop metadata is sanitized
  against launcher field injection, escaping metadata symlinks are ignored,
  AppImageLauncher source payloads are retained, and unrelated user themed
  icons are protected during integration.
- **Validated on main:** source update journaling with simulated ENOSPC,
  abrupt-exit rollback, cross-distribution CI, and reported CachyOS KDE tests.
- **Not yet validated:** actual spare-system clean install, real low-space
  filesystem, power-loss recovery, unsupported desktop environments, and
  arbitrary application compatibility. Automated tests do not replace these.
- **Release artifacts pending:** v1.0.0 version/package metadata, stable
  notes, independently checked release package contents/checksums, and a
  separate release approval. The checksum for v1.0.0-beta.1 is not the
  checksum for any future stable binary.

## Disposable filesystem and package lifecycle CI

Source recovery now has a real tmpfs ENOSPC and real SIGKILL mid-publication
test in a disposable GitHub runner, followed by journal-based restart. This
is not a physical power-cut or a spare CachyOS host test.

A separate Arch container gate tests a clean install and uninstall while
preserving a non-root test user's MIME defaults, managed registry, and
AppImage data. The package must also ship its MIT notice in the standard
Arch license path. The third-party license review in
`DEPENDENCY_LICENSE_AUDIT.md` is preliminary: contributor ownership and
screenshot provenance still require independent verification.

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
