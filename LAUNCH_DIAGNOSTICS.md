# Application Diagnostics and monitored launches

AppInstall now routes its managed AppImage, Flatpak, DEB and RPM desktop entries
through `launch_monitor.py`. This improves error visibility for supported cases;
it does not guarantee compatibility with every application or package.

Open **AppInstall** from KDE's application launcher, run `appinstall`, or run
`appinstall --diagnostics`. The existing package confirmation windows also offer
an **Application Diagnostics** button. Double-click package installation still
requires confirmation.

## What is monitored

The wrapper keeps the application's name, icon, categories and desktop actions.
It saves the original desktop command, expands desktop field codes into argument
arrays, and invokes the correct backend without constructing a shell command.
Working-directory and environment assignments are preserved. Container launches
start the existing rootless Distrobox before checking the application command.
AppImages continue to disable AppImageLauncher interception.

Checks include missing desktop files, invalid commands, missing executables,
executable permissions, ELF architecture, required environment variables when
explicitly configured, and installed package status. When `readelf` is present,
ELF shared-library requirements are compared with known loader paths and the
loader cache without running the binary. This cannot discover every transitive
or dynamically loaded dependency. If static checks are unavailable, startup
output remains monitored. `binutils` is optional, not silently installed.

Only explicitly recorded service ports are observed before launch. An occupied
port is a note, not automatically a failure: an application's existing service
may legitimately reuse it. Explicit port-conflict messages in failed startup
output are categorized separately. **Port Owner** shows the listener via `ss`;
there is no action that kills it or changes application configuration.

The first 12 seconds after process start are the startup observation period.
Immediate nonzero exits, loader failures and explicit port-conflict output are
recorded as failures. Distrobox/container-start errors are distinguished from
application errors. Successful exit or detachment is **unverified**, not failure.
A process surviving startup is also **unverified**. Window detection is not used,
so a missing Wayland window alone does not trigger an error.

Interactive `Terminal=true` launchers preserve terminal stdin/stdout; their stderr
and exit status are monitored. Normal graphical applications have both startup
stdout and stderr captured. Monitoring may remain alive alongside a running app
for log collection; it does not create another application menu entry.

## Error windows, logs and repairs

Failures request a KDE notification and a Qt error window containing application
name, error category, explanation, technical details and suggested next step.
**View Logs**, **Copy Error Details** and **Application Diagnostics** are available.
If Qt is absent, notification/KDialog/Zenity fallbacks are attempted. A headless
session cannot display a desktop window; diagnostics remain in user state and a
terminal error is printed if no presentation channel is available.

Application Diagnostics lists managed applications, format, container, latest
launch and most recent detected error. View Logs can select earlier attempts.
Repair operations require confirmation:

- **Repair Launcher** recreates a missing managed launcher. Unexpected external
  edits are preserved, rather than overwritten.
- **Re-export** uses the existing container package record and Distrobox exporter.
  Existing ownership checks protect unrelated launchers.
- **Retry Container** only starts an existing container, without host sudo or
  creating a replacement.
- **Repair Dependency** is offered only for an evidenced missing library with an
  explicit package mapping. Currently `libasound.so.2` maps to Debian's
  `libasound2t64` or Fedora's `alsa-lib`. The official repository transaction is
  shown; installation happens only after approval. Unknown library names are not
  converted into package-manager commands. Changed diagnostic evidence invalidates
  an old repair plan.
- **Uninstall** asks for confirmation and uses the existing backend. Personal
  application data, other apps and diagnostic history remain untouched.

Launch metadata is stored in
`${XDG_DATA_HOME:-~/.local/share}/appinstall/launchers.json`.
Logs and attempt records are under
`${XDG_STATE_HOME:-~/.local/state}/appinstall/launches/`.
Files are mode 0600, with private state directories. Each app retains eight
attempts, each log bounded to 128 KiB. Environment dumps and full command lines
are not logged. Known secret environment/argument values, common credential
patterns, URL credentials and URL queries are redacted; overlong output lines
are omitted. Arbitrary unlabeled secrets printed by an application cannot be
reliably recognized. Review logs before sharing them; nothing is uploaded.

## Verification performed on CachyOS KDE Wayland

**70 automated tests pass**, including all original 33 tests. Added checks cover
Freebuff's missing-library error, OpenCode launcher and port errors, executable
and desktop-file failures, architecture/permissions/environment checks, container
startup errors, immediate exits, legitimate background processes, field codes,
quoting, working directories, desktop actions, duplicate registration, notification
requests, private bounded logs, history ordering, safe repair plans, external-edit
protection, rollback and Qt error/diagnostics controls. A time-dependent gzip test
fixture was fixed to compare the exact original package input rather than a second
newly generated gzip archive. Optional Qt tests skip if PySide6 is unavailable.

Real desktop tests used temporary, explicitly named launchers opened from KDE:

| Scenario | Observed result |
|---|---|
| Missing library | Compiled a small local ELF fixture and removed only its temporary test library. The preflight reported the missing library; error window and KDE notification visually inspected. |
| Occupied port | A test-owned socket held an ephemeral port. A launched client failed to bind; AppInstall reported the actual port and Port Owner identified the test process. No unrelated process was stopped. |
| Invalid executable | Visible error window categorized the missing executable. |
| Missing container | Visible container error, without creating any container. |
| Immediate exit | Test application exited with code 70; visible crash error with exit details. |
| Background process | Launcher spawned a background child and exited zero; recorded as detached/unverified, without a false failure. |
| Missing launcher and repair | Removed only a test launcher, opened it from Diagnostics, observed the missing-entry error, then recreated it through the confirmed Repair Launcher action. |
| Container repairs | Re-export and Retry Container passed through the actual Diagnostics confirmation UI. |
| Normal launches | OpenCode (DEB), Character Map (RPM), Seanime (AppImage) and Stremio (Flatpak) were launched through KDE and their populated windows visually inspected. |
| RPM lifecycle | Installed the official Fedora Character Map package through AppInstall, confirmed one monitored launcher, re-exported it, and uninstalled it through Diagnostics. |

Freebuff's monitored process produced no detected failure; its current focused
window was not independently verified during this phase. Its earlier ALSA repair
and sign-in-screen check remain documented in the previous integration work.
Copy Error Details and View Logs callbacks passed Qt tests, and View Logs was
also exercised in the real desktop. A cross-process clipboard read was inconclusive
under Wayland; physical copy/paste confirmation remains advisable.

Temporary test launchers, the test socket holder and the Fedora test app were
removed. Application data and diagnostic logs were retained. Evidence is private,
under `~/.local/share/appinstall/integration-results/` and
`~/.local/state/appinstall/monitor-integration/`. Screenshots are not added to Git.
The earlier integration report describes installation testing; this report covers
the new monitor.

## Remaining limits

A running process is not proof of usability. An error rendered only inside an
app's own window, an unsuccessful detached child that does not report through the
launcher, late failures after the startup period, GPU/network/account problems,
or an app that replaces its launcher outside AppInstall may require manual
investigation. No app-specific port configuration is changed automatically.
Distrobox remains integrated with the host and is not a security sandbox. These
tests cover this desktop and selected applications, not universal DEB/RPM support.

## Changed files and rollback

New production modules: `launch_monitor.py`, `runtime_probe.py`,
`diagnostics_core.py`, `diagnostics_ui.py`.
Integration changes: `appimage_backend.py`, `container_backend.py`, `appinstall`,
`integration.py`, `confirm.py`, `container_ui.py`, `appinstall.desktop`, `PKGBUILD`.
Tests and manual helpers are under `tests/` and `tools/`; existing assertions were
preserved with fixture isolation and the gzip fixture correction. No partitions,
GRUB, EFI, APFS or macOS configuration were modified.

Backup before this phase:
`~/appinstall-backups/launch-monitor-20261101-232709/`.
It contains source, installed helper/registry files, and the application-launcher
directory. It deliberately excludes container HOME/package caches and screenshots.

To roll back:

1. Close AppInstall package-operation and diagnostics windows.
2. Run `python3 ~/.local/share/appinstall/launch_monitor.py --restore-launchers`
   in a terminal and confirm. Only unchanged managed launchers are restored to
   their original commands; externally modified entries are skipped. Container
   export ownership hashes are updated without restoring an obsolete registry.
3. Restore the changed source and installed helper files from the backup. Copy
   the backup's source `appinstall` script to `~/.local/bin/appinstall`, preserving
   its executable permission. Restore only the AppInstall menu entry from
   `applications/appinstall.desktop` if you want its previous visibility.
4. Refresh KDE with `kbuildsycoca6 --noincremental`.

Do not replace the whole application-launcher directory or container registry over
later user changes. New monitor modules and logs can be kept; they are unused once
original commands are restored. No container, package or personal data is removed
by launcher rollback. This phase is published as commit `e7b68ec` on GitHub
(`main`); rollback procedures above remain valid.
