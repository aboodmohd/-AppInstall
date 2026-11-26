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

- New `install_mode.py` verifies native installation by package ownership of `/usr/bin/abood-appinstall` (`pacman`, `dpkg-query` or `rpm`) before considering module paths.
- Native installations always use the packaged `appinstall-installer`, even if stale portable modules or launchers remain.
- Portable installations still use `portable_update.py` with its existing launcher/symlink security checks.
- Stale AppInstall desktop entries whose `Exec` target is missing are repaired to the package-owned executable, preserving other fields. The repair runs from the native CLI, the one-command installer and native package install/upgrade scriptlets.
- Regression tests reproduce the exact error scenario: native package present, stale user-data portable module present, and a helper resolution that must not select the portable updater.

## Packaging verification

Initial CI exposed that `install_mode.py` was added to `source=` but not installed into `/usr/lib/abood-appinstall`, causing `ModuleNotFoundError` in native packages. The packaging rule was corrected and a local `makepkg` build now includes the module and the install scriptlet.

## Repair safety

The repair rewrites only the `Exec=` line of the fixed filename
`~/.local/share/applications/io.github.aboodmohd.AppInstall.desktop`, and only
when all of these hold: native package ownership is verified, the entry is a
regular file (not a symlink), the entry is positively identified as AppInstall,
the launcher path is absolute or `~/`, and that launcher no longer exists.
Existing portable launchers, PATH-based commands, unrelated entries and all
other desktop-entry fields are left untouched. Package scriptlets run the
packaged module with `runuser -u <user>`, so root never executes user-owned
code; only the invoking user's own AppInstall entry is considered.

## Verification status (final candidate)

- Local suite: 804 tests, 803 passed, 1 skipped.
- CI: 29/29 checks green at the final PR head. Earlier failures were a missing
  packaged module and a test-side repair side effect; both were fixed. A Fedora
  repoquery timeout was transient and passed on rerun.
- Live CachyOS (installed 1.9.5-1 candidate, snapper snapshots 171/172/173):
  the stale user entry was repaired to `Exec=/usr/bin/abood-appinstall %F`,
  `find_update_helper()` selected `/usr/lib/abood-appinstall/appinstall-installer`,
  and the real Premium UI Check for Updates reached the native updater with no
  portable error. Forced proxy failure produced actionable network diagnostics
  with no credential leakage; retry, repeated checks and close-during-check
  (including child cleanup) passed.
- Launched through the desktop entry via `gio launch`; process tree was
  `bash /usr/bin/abood-appinstall` → `python3 /usr/lib/abood-appinstall/manager_qml.py`,
  with no portable updater. The same path was used again after closing the app.
- Newer-version detection: with a stubbed release service, installed 1.9.5-1
  emitted `APPINSTALL_UPDATE=v1.9.6` for a fake v1.9.6 release and no marker
  for v1.9.4/v1.9.5, both from the installed helper and the final source.
- All nine MIME defaults, records, AppImages, Flatpaks, containers and managed
  list are intact; no temporary test paths remain in any AppInstall desktop
  entry. The only settings change from UI checks was `last_update_check`,
  restored from the verified pre-change backup.

Limitation: literal mouse injection into the desktop-entry-launched window was
not possible because Xwayland ignored XTest synthetic input in this session;
the actual Premium UI button was driven in-process with QtTest in the same real
user profile instead.
