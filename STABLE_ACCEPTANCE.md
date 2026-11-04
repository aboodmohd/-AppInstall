# AppInstall 1.0.0-rc.1 — Acceptance Checklist

**Status: test candidate, NOT an approved Stable 1.0 release.**

The automated tests cannot demonstrate a clean real desktop installation,
safe system package removal, or arbitrary application compatibility.
Do not run destructive upgrade/uninstall tests on the working CachyOS
installation or remove any managed AppImages or Distrobox data.

## A. Read-only host checks (CachyOS)

Run without sudo to collect installation and desktop information:

~~~fish
printf '\n== Installation paths ==\n'
type -a appinstall
printf '\n== Installed version ==\n'
appinstall --version
printf '\n== Session ==\n'
printf '%s\n' "$XDG_CURRENT_DESKTOP" "$XDG_SESSION_TYPE"
printf '\n== Optional backends ==\n'
for command in python3 flatpak podman distrobox unsquashfs kdialog zenity
    if type -q $command
        echo "$command: present"
    else
        echo "$command: absent"
    end
end
printf '\n== Default file associations ==\n'
for mime in application/vnd.flatpak application/x-rpm application/vnd.debian.binary-package application/vnd.appimage
    echo "$mime: "(xdg-mime query default "$mime")
end
~~~

None of these checks changes installed applications or source files.
Record actual GUI launches and any errors separately.

## B. Isolated regression suite (does NOT change installed AppInstall)

~~~fish
set -gx APPINSTALL_RC_TEST (mktemp -d "$HOME/.appinstall-rc.XXXXXXXX")
git clone --depth 1 --branch release/v1.0.0-rc1-preparation https://github.com/aboodmohd/-AppInstall.git "$APPINSTALL_RC_TEST/repo"
and env TMPDIR="$APPINSTALL_RC_TEST" QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s "$APPINSTALL_RC_TEST/repo/tests" -v
and echo "PASS: Isolated candidate source regression suite"
~~~

The tests use disposable HOME/XDG directories and fixtures. A passing suite
does not confirm a physical disk-full event or a live source upgrade.

## C. Spare VM or non-production Arch/CachyOS system ONLY

Use a snapshot/backup. Avoid running real upgrade/removal trials on a daily-use
desktop. This section intentionally supplies no copy-paste live removal command.

- [ ] Clean snapshot: confirm absence of AppInstall and original MIME defaults
- [ ] Obtain the candidate package from its *specific* green CI workflow run
- [ ] Compare SHA-256 against the hash printed by that run; inspect package files
- [ ] Install in the spare environment and confirm version 1.0.0-rc.1
- [ ] Verify manager and diagnostics windows open under KDE Wayland
- [ ] Test Dolphin review, cancel, install and monitored launch for a
      representative AppImage, Flatpak, DEB and RPM
- [ ] Check missing-dependency, network failure and launch-error messaging
- [ ] Verify manager refresh, no duplicate launchers and uninstall confirmation
- [ ] Reinstall/upgrade with existing managed records and confirm data retention
- [ ] Remove the *system package* in the spare environment: confirm user
      application data and unchanged MIME defaults remain intact
- [ ] On another disposable filesystem, simulate low space and abrupt
      termination during *source* registration; rerun to recover, check
      permissions, MIME defaults, backup journal and managed app records
- [ ] Review third-party licenses and dependency versions
- [ ] Restore the snapshot; preserve test evidence without private identifiers

## D. Release gates

A public Stable 1.0 requires verified manual gates, final stable version and
notes, an independent checksum of the exact final built artifact, and explicit
merge/tag/publication approval. Passing candidate CI is not that approval.

See STABLE_RELEASE_AUDIT.md and STABLE_READINESS.md.
