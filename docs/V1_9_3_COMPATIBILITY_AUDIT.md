# AppInstall v1.9.3 compatibility, migration and security audit

Status: development candidate. The live CachyOS installation was not modified for this audit.

## Independent audit findings and fixes

Two independent audits reviewed the v1.9.2 base while this branch was being developed. Findings below were re-verified against the final tree before being marked fixed.

### Confirmed and fixed

1. **Legacy Flatpak wrappers were not migrated on native installs** (medium-high). `migrate_flatpak_launchers()` was reachable only from `integration.py`, which native packages do not run. Added a `--migrate-flatpak` CLI flag to `launch_monitor.py` and an opt-in call from `appinstall --manage`, preserving the byte-identical ownership check. Tests cover migration, user-edit preservation, and the CLI flag.
2. **`integration.py` syntax error** (critical, transient). A mid-development edit placed the migration block between `try` and `except`, breaking all source installs/uninstalls. Fixed and protected by `tests/test_source_syntax.py`, which compiles all executable Python entry points.
3. **APT signature-bypass gate on repository installs** (medium). `validate_apt_sources()` accepted `Trusted: yes` / `[trusted=yes]` and other apt-secure bypass options. It now rejects those options in both deb822 and one-line formats, validates every URI (including continuations), and restricts official Debian paths. New tests cover lowercase and uppercase bypass attempts.
4. **Native Flatpak launch integrity** (low). Native launchers re-read `Exec` from the live export without checking that it still describes the same application. `monitor()` now validates native Flatpak argv through `flatpak_exec_argv()`; migration and adoption use the same helper. Tests reject unrelated commands and application IDs.
5. **Flatpak export symlink and TOCTOU handling** (low). Native export discovery now rejects symlinked export files, and recorded hashes are computed from the exact validated bytes. Tests cover symlinked-export rejection.
6. **Malformed registry records during uninstall** (medium). `restore_launchers()` and container `uninstall()` now skip incomplete or non-dictionary records instead of aborting removal. Tests cover both paths.
7. **Uninstall with an older helper** (medium). `install.sh --uninstall` now feature-detects `--detach-launchers`; older helpers are left unchanged rather than blocking package removal.
8. **AppImage publication rollback** (low). A failure while registering the monitored launcher now restores the previous manifest and launcher bytes before removing the staged generation. A new regression test forces `wrap_appimage()` to fail and verifies no published state remains.
9. **Unbounded `cat` of APT source paths / special files** (low). APT sources are checked as regular files before reading, and `subprocess.run` has a default timeout.
10. **Portable bundle on Python 3.6 (confirmed, Leap 15.6).** `source_transaction.py` used `Path.unlink(missing_ok=True)` (Python 3.8+) and the code base also uses other 3.7/3.8 APIs. The portable installer now checks for Python 3.8+ and exits with an actionable message before touching user state. Documentation states the minimum. With `python311` exposed as `python3`, the portable lifecycle is tested separately.
11. **Diagnostic redaction for non-HTTP secrets** (low, carried from v1.9.2 final review). HTTP Basic credentials and schemeless URLs with query secrets are redacted in addition to bearer/token patterns; tests verify no `TOPSECRET`-style values survive.

### Not reproduced / false positive

- The reported background-process leak was not reproduced. A disposable-profile sampling run showed no persistent manager/monitor/backend process increase after repeated smoke runs (before=1, after=1, the sampling command itself). Manager update scans remain TTL-gated at 12 hours and can be disabled with `APPINSTALL_DISABLE_UPDATE_TIMER`.

## Real Flatpak lifecycle

In a disposable HOME/user Flatpak installation, a real Flathub application (`net.ffkkinos.Wildcard`) was installed, its native export adopted by AppInstall while preserving the live symlink, updated from the remote, launched with a no-op command, and uninstalled. The AppInstall CLI remained functional afterwards. No live Flatpak installation was touched.

## Package collision during a complete system upgrade

A disposable Arch container held the official legacy `appinstall 1.9.0-1` and `abood-appinstall 1.9.3-1` together with a local repository offering unrelated `appinstall 2.0.8-1`. A complete `pacman -Syu` upgraded the legacy package to the unrelated AUR package. Ownership remained split (`/usr/bin/appinstall` → `appinstall`, `/usr/bin/abood-appinstall` → `abood-appinstall`), and the AppInstall ownership/origin check still reported the genuine `abood-appinstall 1.9.3-1` version. No uninstall or overwrite occurred.

## Performance profile

Measured from a disposable profile with the current branch (three runs each):

| Operation | Average seconds | Notes |
|---|---:|---|
| Manager QML smoke | 1.1996 | offscreen, update timer disabled |
| CLI version | 0.0051 | shell entry point |
| Flatpak migration CLI | 0.1223 | no legacy wrappers in profile |
| Python module import | 0.4374 | manager + backends |

Memory: child-process high-water mark was approximately 150,788 KiB during the QML smoke run; pure CLI/import work stayed below that. These are cold-ish averages in a container-desktop-less profile, not physical desktop benchmarks.

## Platform compatibility

Executed portable-cli install → version/list/detect → uninstall lifecycle, in disposable containers:

| Platform | Image / basis | Result | Scope |
| --- | --- | --- | --- |
| Debian 13 | `debian:13` native image | PASS | CLI lifecycle; GUI skipped where PySide6 unavailable |
| Ubuntu 24.04 | `ubuntu:24.04` native image | PASS | CLI lifecycle |
| Linux Mint 22 | Ubuntu 24.04 image with Mint `/etc/os-release` | PASS | **Emulated**, not a physical Mint installation |
| Fedora 44 | `fedora:44` native image | PASS | CLI lifecycle |
| Bazzite stable | `ghcr.io/ublue-os/bazzite:stable` native image | PASS | CLI lifecycle; immutable host, native package path not attempted |
| Manjaro | `archlinux:base` with Manjaro `/etc/os-release` | PASS | **Emulated**, not a physical Manjaro installation |
| EndeavourOS | `archlinux:base` with EndeavourOS `/etc/os-release` | PASS | **Emulated**, not a physical EndeavourOS installation |
| openSUSE Leap 15.6 (default Python 3.6) | `opensuse/leap:15.6` native image | rejected as expected | Portable installer exits with Python 3.8+ guidance before writing state |
| openSUSE Leap 15.6 with Python 3.11 | same image with `python311` as `python3` | PASS | CLI lifecycle; GUI skipped (PySide6 not installed) |

A genuine Manjaro image was not available (`manjarolinux/base` could not be pulled), and EndeavourOS does not publish a container image. The os-release cases verify only that the support gate and portable path behave as intended on Arch-like hosts; they are not claims of physical-distro compatibility. Native `.deb`/`.rpm`/`.pkg.tar.zst` lifecycles for v1.9.3 are covered by the GitHub CI matrix rather than these local portable runs.

## Test results

- Full local suite: 791 tests, 790 passed, 1 skipped.
- New syntax gate compiles all executable Python entry points.
- Real DEB lifecycle in Debian 13: a signed-source scoped APT install, verification and removal through the current `container_backend` code passed.
- Real Flatpak lifecycle and package-collision upgrade results are recorded above.
- GitHub CI results are recorded on the pull request after the final commit.

## Remaining limitations

Interactive Qt workflows, full graphical application launches, a real Yay system upgrade on a physical desktop, immutable-OS package layering, and long-running background behavior were not executed. DEB/RPM application compatibility remains application-dependent.
