# AppInstall v1.9.2 reliability audit

Status: candidate. The live v1.9.1 desktop installation was not changed during this audit.

## 1. DEB installation blockage — Confirmed

Source: `container_backend.py` (`Engine.ensure`, `Engine.transaction`, `Engine.install`).

`ensure()` read **all** APT `.list`/`.sources` fragments and `validate_apt_sources()` rejected the transaction if any fragment contained an unrecognized URL. A vendor-added fragment therefore blocked a subsequent local DEB install even though the package itself and the official Debian repositories were valid. DPKG locks were not cleared or removed, and no static lock path was found.

Fix: local DEB transactions build a private source tree **inside the container**, copying only authenticated stanzas: official Debian mirrors without `Signed-By`, or HTTPS vendor sources with a readable GPG/armored keyring. APT is scoped to that tree with `Dir::Etc::sourceparts=<container path>`, `Dir::Etc::sourcelist=-` and `DPkg::Lock::Timeout=30`. Unsigned, malformed, prefix-spoofed and commented `Signed-By` fragments are excluded. Repository-backed installs keep full validation. Failures set `needs-repair` and leave the container and repositories intact.

Evidence: new `tests/test_containers.py` trust tests. In a disposable Debian 13 container, signed Brave and Google repositories remained usable while unsigned/malformed fragments were excluded; Chrome, VS Code, Edge and Brave all installed, and a separate unrelated DEB installed successfully after each. `Acquire::AllowInsecureRepositories` remained `0`. A failed dependency, a failed maintainer script and `dpkg --configure -a` recovery were exercised; the next unrelated install succeeded.

## 2. Uninstall breaks managed applications — Partially Confirmed

Source: `appimage_backend.py`, `launch_monitor.py`, `integration.py`, `install.sh`, `url_install.py`.

The supported uninstall paths did not indiscriminately delete application payloads. However, the source portable uninstaller rewrote managed launchers back to a `python3 /path/to/integration.py` command pointing at files being removed; a Flatpak adoption could replace a live export symlink with a frozen copy; and the portable URL installer looked for `/usr/bin/appinstall` rather than the user-local launcher. These paths could break apps after AppInstall removal.

Fix: supported uninstallers call `restore_launchers(preserve_records=True)`, which removes monitoring from AppImage wrappers, adds their embedded working directory, and re-points adopted Flatpak launchers at the live Flatpak export. Registry records and payloads remain. Native Flatpak adoption keeps the export symlink. The portable URL installer resolves the user-local `abood-appinstall` launcher.

Evidence: new `tests/test_monitor.py` tests for standalone AppImage launch after uninstall and live Flatpak export replacement. A real 512 MiB AppImage test installed two images, ran the portable uninstaller, and launched both generated standalone commands. No live desktop data was changed.

## 3. Frozen Flatpak launchers — Confirmed

Source: `appinstall` (`refresh_flatpak_menu`), `launch_monitor.py` (`adopt_flatpak`), `integration.py`.

Adoption could replace Flatpak's maintained desktop-entry symlink with a copied file and then wrap its command. Upstream icon, command and metadata changes were frozen at adoption time. DBus activation was also disabled in the copied entry.

Fix: adoption preserves the symlink to Flatpak's export and records the native launch command without rewriting the file. Re-registration refreshes adoption from the live export. Uninstall restores the symlink. Invalid or unexpected application IDs are rejected.

Evidence: new `tests/test_monitor.py::test_flatpak_adoption_tracks_replacement_export` passed.

## 4. Large AppImage failures — Partially Confirmed

Source: `appimage_backend.py` (`install`, `preview_contents`).

Downloads were already streamed in `url_install.py`. Installation, however, copied the source once into a private temporary directory and again into the destination, and preview used a fixed 180-second timeout that propagated as a fatal error. There was no destination free-space check.

Fix: one streamed copy is staged on the destination filesystem; passive preview runs there; timeout and preview limitations degrade to a generic, launchable identity. A free-space check fails before creating a generation. Publication remains transactional.

Evidence: new tests for preview timeout and full destination. Three real appimagetool-generated AppImages of 529,728,704 bytes (512 MiB class), 1,059,259,584 bytes (1 GiB class) and 2,118,321,344 bytes (2 GiB class) installed with peak RSS of 20,776/21,072/20,844 KiB respectively. Staged disk usage matched the image size (529,735,680/1,059,266,560/2,118,328,320 bytes) and all three launched independently, printing `LARGE_APPIMAGE_OK`. No live desktop data was changed.

## 5. AppImage name collisions — Confirmed

Source: `appimage_backend.py`.

Identity was a 16-character hash of the visible `Name`. Two images with the same name shared a manifest and desktop entry; the later install retired the earlier launcher and removed its generation. The CLI removal path could also match by visible name.

Fix: each installation gets a UUID-based launcher and manifest identity. Same-name images coexist, and removal requires an exact launcher ID when several records match. Existing records retain their old manifests and remain launchable because `wrap_appimage` resolves from manifest data instead of the filename.

Evidence: regression tests for identical names and different payloads were written first and failed before the fix. Four real AppImages with the same embedded name produced four unique launchers. A simulated update added a fourth record, then removal of one record left the other three independently launchable (`SAME_APP_2`, `SAME_APP_3`, `SAME_APP_4`). The manager's reinstall docstring was corrected: each reinstall is a new independent record.

## 6. Arch filesystem layout — False Positive for v1.9.1

Source: `PKGBUILD` lines 149-187 and the published v1.9.1 artifact.

The reported layout places Python modules in `/usr/bin`. Source review and `bsdtar -tf` on the published artifact show only `/usr/bin/abood-appinstall` in `usr/bin`; the modules and QML resources are under `/usr/lib/abood-appinstall`. A fresh isolated `makepkg` install confirmed the CLI, QML load, ownership and removal. No layout change was needed. The `abood-appinstall` identity is preserved.

## 7. URL installation error reporting — Partially Confirmed

Source: `url_install.py`, `url_dialog.py`, `manager.py`.

Download errors were typed but the GUI showed a short message; backend `stdout`/`stderr` from the install command was captured and discarded. HTTP error reasons could include raw URLs, and checksum/format failures were not distinguished in the user-facing backend result.

Fix: bounded backend output is written to a mode-0600 diagnostic log under `XDG_STATE_HOME/appinstall/url-install`, with URLs, credentials, query parameters and secret-like values redacted. Only the five newest logs are retained. The user-facing message says which error occurred and where the log is. HTTP, truncated, interrupted, checksum, format, size, and disk-space paths have specific messages.

Evidence: real HTTPS checks produced `HTTP 404`, `Could not connect ... timed out`, and unsupported-format messages without exposing query secrets. A 64 KiB tmpfs produced `Not enough temporary storage`. A real backend script returning exit 42 produced the log location; the log contained no `TOPSECRET`, `secret@` or `opaque=` values. The live state directory written by the first test pass was removed after testing.

## Broader audit

- Local DEB source validation was made transaction-scoped rather than globally disabled.
- AppImage identity changed without renaming user data or container registries.
- Uninstall no longer consumes launch registry records when preserving applications.
- Flatpak application IDs are validated before filesystem use.
- Native package identity and Premium UI are unchanged.
- Portable, Arch/CachyOS, Debian 13, Ubuntu 24.04 and Fedora 44 disposable installs and removals were checked.

Remaining limitations: full interactive Qt workflows and a real browser/URL flow were not driven on the live desktop; a full system upgrade was not performed with Yay. DEB/RPM application compatibility remains application-dependent.

## 8. Additional defects found during acceptance — Confirmed

- `launch_monitor.restore_launchers()` assumed every container registry value was a dictionary. A malformed record aborted uninstall before package removal. It now skips malformed records. Evidence: the native uninstall test first failed with `AttributeError`; after the fix, `install.sh --uninstall --yes` removed only `abood-appinstall` and preserved the record.
- Independent review identified APT prefix matching, weak `Signed-By` checks and a host path passed into a container. All three were fixed as described in section 1 and covered by new tests.
- URL diagnostics now cap retained logs and avoid rejecting downloads with chunked transfer encoding.

## Final acceptance evidence (disposable environments)

- Native v1.9.1 → v1.9.2 migration in an Arch container preserved settings, launcher records, container registry, an independent desktop entry and an AppImage; CLI and QML smoke passed.
- Native uninstall in an Arch container removed only `abood-appinstall`. An AppImage launcher became a standalone executable command and launched; an adopted Flatpak launcher remained a symlink and reflected an updated export; DEB/RPM launchers kept native commands; the container registry hash was unchanged.
- Portable uninstall in a disposable HOME produced the same preservation results, including the standalone AppImage launch and live Flatpak export.
- Real browser DEBs: Chrome 158.0.8127.88-1, VS Code 1.148.0-1795526052, Edge 142.0.3595.94-1 and Brave 1.100.59 installed from official URLs; Brave's SHA-256 matched the signed release checksum file. After each install a different unrelated DEB installed successfully.
- Filesystem layout was verified in Arch, Debian 13, Ubuntu 24.04 and Fedora 44 disposable installs: `/usr/bin/abood-appinstall` is the only executable entry point; modules live under `/usr/lib/abood-appinstall`.

Limitations: VS Code's `--version` refused to run as container root, so package installation was verified through `dpkg-query` rather than a graphical launch. Flatpak behavior was verified with real export files and symlinks, not an installed Flatpak application. A full Yay system upgrade was not run.
