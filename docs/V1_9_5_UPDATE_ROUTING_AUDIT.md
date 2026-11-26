# AppInstall v1.9.5 update-routing hotfix audit

## Exact root cause

The live CachyOS desktop had a user-level desktop entry at
`~/.local/share/applications/io.github.aboodmohd.AppInstall.desktop` whose
`Exec=` pointed to a temporary portable launcher created during earlier
development testing:

```text
Exec=/tmp/opencode/appinstall-v193-flatpak2/home/.local/bin/abood-appinstall %F
```

KDE prefers that user entry over `/usr/share/applications/io.github.aboodmohd.AppInstall.desktop`. The stale launcher no longer had its sibling `manager_qml.py`, so it fell back to the old source modules in
`~/.local/share/appinstall`. `find_update_helper()` used only the module path: because the module lived in the XDG user-data tree, it selected `portable_update.py`. The native package was installed, but mode detection was wrong. The portable updater then correctly refused because its launcher was missing or a symlink:

```text
AppInstall portable update refused: Portable AppInstall user launcher is missing or is a symlink.
```

The portable security check was working; the updater was simply the wrong updater.

## Fix

- New `install_mode.py` verifies native installation by package ownership of `/usr/bin/appinstall` (`pacman`, `dpkg-query` or `rpm`) before considering module paths.
- Native installations always use the packaged `appinstall-installer`, even if stale portable modules or launchers remain.
- Portable installations still use `portable_update.py` with its existing launcher/symlink security checks.
- Stale AppInstall desktop entries whose `Exec` target is missing are repaired to the package-owned executable, preserving other fields. The repair runs from the native CLI, the one-command installer and native package install/upgrade scriptlets.
- Regression tests reproduce the exact error scenario: native package present, stale user-data portable module present, and a helper resolution that must not select the portable updater.

## Verification status

Pending live verification with the installed hotfix and existing CachyOS profile. This document will be updated with exact observed results before any merge or publication.
