# AppInstall v1.9.2 reliability audit

Status: candidate. The live v1.9.1 desktop installation was not changed during this audit.

## 1. DEB installation blockage — Confirmed

Source: `container_backend.py` (`Engine.ensure`, `Engine.transaction`, `Engine.install`).

`ensure()` read **all** APT `.list`/`.sources` fragments and `validate_apt_sources()` rejected the transaction if any fragment contained an unrecognized URL. A vendor-added fragment therefore blocked a subsequent local DEB install even though the package itself and the official Debian repositories were valid. DPKG locks were not cleared or removed, and no static lock path was found.

Fix: local DEB transactions now read only the known Debian source file and scope `apt-get` with `Dir::Etc::sourceparts=-`, `Dir::Etc::sourcelist=<known file>` and `DPkg::Lock::Timeout=30`. Repository-backed installs keep the full repository validation. Failures set `needs-repair` and leave the container, repositories, and other packages intact. The interrupted-dpkg error now points to the container for manual configuration.

Evidence: new `tests/test_containers.py::test_apt_transaction_ignores_vendor_source_fragments`. In a disposable Debian 13 container, a broken vendor fragment blocked unscoped APT; two local DEBs were then installed in succession through the scoped path after one dependency failure, with the vendor file unchanged. Regression tests passed.

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

Evidence: new tests for preview timeout and full destination. A real 512 MiB synthetic AppImage installed twice with a maximum process RSS of approximately 21 MiB, then launched independently. No live desktop data was changed.

## 5. AppImage name collisions — Confirmed

Source: `appimage_backend.py`.

Identity was a 16-character hash of the visible `Name`. Two images with the same name shared a manifest and desktop entry; the later install retired the earlier launcher and removed its generation. The CLI removal path could also match by visible name.

Fix: each installation gets a UUID-based launcher and manifest identity. Same-name images coexist, and removal requires an exact launcher ID when several records match. Existing records retain their old manifests and remain launchable because `wrap_appimage` resolves from manifest data instead of the filename.

Evidence: regression tests for identical names and different payloads were written first and failed before the fix. The real 512 MiB test produced two unique entries, both launchable after uninstall.

## 6. Arch filesystem layout — False Positive for v1.9.1

Source: `PKGBUILD` lines 149-187 and the published v1.9.1 artifact.

The reported layout places Python modules in `/usr/bin`. Source review and `bsdtar -tf` on the published artifact show only `/usr/bin/abood-appinstall` in `usr/bin`; the modules and QML resources are under `/usr/lib/abood-appinstall`. A fresh isolated `makepkg` install confirmed the CLI, QML load, ownership and removal. No layout change was needed. The `abood-appinstall` identity is preserved.

## 7. URL installation error reporting — Partially Confirmed

Source: `url_install.py`, `url_dialog.py`, `manager.py`.

Download errors were typed but the GUI showed a short message; backend `stdout`/`stderr` from the install command was captured and discarded. HTTP error reasons could include raw URLs, and checksum/format failures were not distinguished in the user-facing backend result.

Fix: bounded backend output is written to a mode-0600 diagnostic log under `XDG_STATE_HOME/appinstall/url-install`, with URLs, credentials, query parameters and secret-like values redacted. The user-facing message says which error occurred and where the log is. HTTP, truncated, interrupted, checksum, format, size, and disk-space paths have specific messages.

Evidence: new `tests/test_url_install.py::test_backend_log_redacts_sensitive_urls` passed and verified the user message plus redaction.

## Broader audit

- Local DEB source validation was made transaction-scoped rather than globally disabled.
- AppImage identity changed without renaming user data or container registries.
- Uninstall no longer consumes launch registry records when preserving applications.
- Flatpak application IDs are validated before filesystem use.
- Native package identity and Premium UI are unchanged.
- Portable, Arch/CachyOS, Debian 13, Ubuntu 24.04 and Fedora 44 disposable installs and removals were checked.

Remaining limitations: full interactive Qt workflows and a real browser/URL flow were not driven on the live desktop; a full system upgrade was not performed with Yay. DEB/RPM application compatibility remains application-dependent.
