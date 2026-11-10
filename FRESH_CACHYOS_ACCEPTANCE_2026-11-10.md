# AppInstall 1.0.0 — Fresh CachyOS KDE Wayland acceptance report

**Test date:** 2026-11-10  
**Reporter:** Repository owner (owner-reported terminal results and hands-on GUI tests)  
**Status:** **Local fresh-system acceptance evidence recorded; public Stable release remains HOLD / NO-GO.**  
**Evidence thread:** [GitHub issue #14](https://github.com/aboodmohd/-AppInstall/issues/14)

## Environment and exact candidate

- Freshly installed CachyOS (x86_64), KDE Plasma on **native Wayland**, Btrfs root on 113 GiB Apple internal SSD. This replaced the previous dual-boot installation. Initially `appinstall` was absent, as expected.
- Rootless Podman confirmed (`podman info --format '{{.Host.Security.Rootless}}'` => `true`).
- Test dependencies installed: Python 3.14.9, PySide6 6.12.0 (Qt 6.12.0), Flatpak 1.18.4, Podman 6.1.4, Distrobox 1.8.2.5, `squashfs-tools`, FUSE2, KDialog.
- Exact **tested Git source commit**: `9cf51696f574dd80f7adf9336c33adff79ed30f3`.
- Package **locally built on the fresh host** with `makepkg --noconfirm` from that detached source checkout: `appinstall-1.0.0-1-any.pkg.tar.zst`.
- SHA-256 of that **local package**: `14cab16fe1dc3cc63c11526184b948deca2755499272830dcde48fa993b2a5e3`. Independently rechecked before install, system-package lifecycle test, and package inspection.
- This local checksum is **not** a checksum for any future public download; a CI artifact and a locally rebuilt package may have different bytes.

## Results recorded from the fresh system

| Check | Outcome | Evidence or boundary |
| --- | --- | --- |
| Source regression before install | **PASS** | 190 tests run, `OK (skipped=2)`; no failures |
| `makepkg` package build | **PASS** | Local package created successfully; SHA-256 recorded |
| Clean Pacman installation | **PASS** | `sudo pacman -U` installed `1.0.0-1`; `/usr/bin/appinstall --version` => `appinstall 1.0.0` |
| Installed source regression | **PASS** | 190 tests run, `OK (skipped=1)`; one test skipped because no installed AppInstall state directory was initialized |
| Installed package integrity | **PASS** | `pacman -Qkk appinstall`: 42 files, 0 altered |
| Native KDE Wayland GUIs | **PASS (launch)** | Manager and Diagnostics windows opened successfully (owner report), not an exhaustive test of every button |
| Desktop integration | **PASS** | Installed desktop launcher and KIO service menu both call `/usr/bin/appinstall`; `xdg-mime query default` reported `appinstall.desktop` for checked AppImage, Flatpak ref, DEB, RPM MIME types |
| AppImage — Hayase | **PASS (owner report)** | All 11 checks below reported successful |
| Flatpak — Stremio | **PASS (owner report)** | All 11 checks below reported successful |
| DEB — Mousepad | **PASS (owner report)** | Owner reported all tests working, without individual test logs |
| RPM — OpenCode | **PASS (owner report)** | All 11 checks below reported successful |
| System package removal/reinstall | **PASS** | `sudo pacman -R appinstall` removed only that Pacman package; verified absence; reinstalled same checksum-verified package; integrity 42/42 |
| User settings and MIME preservation | **PASS for compared paths** | Pre-removal archive verified; `tar -dzf` compared archived user state unchanged; four MIME defaults unchanged |
| Container preservation | **PASS for names** | Rootless Podman container names `debian-apps` and `fedora-apps` persisted; container contents were not independently hashed |
| Invalid AppImage rejection | **PASS** | Invalid text masquerading as `.AppImage` rejected nonzero with error, no inventory changes |
| Missing file and unsupported format | **PASS** | Missing `.flatpakref` and unsupported `.txt` returned nonzero and explanatory errors; before/after inventory unchanged |
| License / launchers / package payload | **PASS** | Package-extracted MIT LICENSE byte-matched source; two absolute `Exec` values correct; repository evidence screenshot PNGs excluded from Arch package; integrity 42/42 |
| CI at tested source SHA | **PASS** | Six completed green GitHub workflow runs on `9cf5169` (unit tests, stable readiness compatibility, tmpfs recovery, X11 GUI, Dolphin/X11 MIME, Weston/Wayland smoke); headless CI must not be mistaken for on-device KDE acceptance |

For each of the four real application formats, the owner reported: opening from Dolphin with AppInstall; preview/confirmation; cancellation without installation; successful install; KDE launcher listing; AppInstall Manager listing; app launch; close/reopen; diagnostics and launch monitoring; reinstall/update; removal without deleting unrelated files. These are **44/44 owner-reported checks**, not independently captured per-format automated test logs, nor a claim of compatibility with every possible application.

## Exact final local package inspection (Step 107)

- Local package digest validated as above.
- `bsdtar -tf` checked archive members.
- `usr/share/licenses/appinstall/LICENSE` extracted with `bsdtar -xOf` and byte-compared with repo `LICENSE` using `cmp`.
- `usr/share/applications/appinstall.desktop` confirmed `Exec=/usr/bin/appinstall %F`.
- `usr/share/kio/servicemenus/appinstall-appimage-review.desktop` confirmed `Exec=/usr/bin/appinstall %f`.
- No `evidence/phase4/*.png` files in the package.
- `pacman -Qkk appinstall`: 42 files, 0 altered.
- Script printed `=== STEP 107 PASSED ===`.

## Remaining release conditions and limitations

1. **Third-party permissions/notices** — Owner already declared the project's source original and all eight repository screenshots their own and authorized (see `SCREENSHOT_PROVENANCE.md` and issue #14). These owner declarations are **recorded; do not request them again**. Independent inspection for externally sourced snippets/artwork and required license notices remains to be signed off; do not claim legal certification.
2. **Untested fault scenarios** — A real missing-runtime-dependency scenario and deliberate network failure were not separately recorded on the fresh host. CI validates tmpfs ENOSPC / SIGKILL recovery on disposable runners; no physical power-loss test was performed. A fresh source-user registration/upgrade path was not manually tested on this host.
3. **Environment and data limits** — Backups for the package lifecycle experiment were on the same SSD, and not a full host/container backup. Tests do not certify GNOME, Xfce, other Linux distributions, or arbitrary third-party packages. Distrobox shares the user's home and is **not** a security sandbox.
4. **Release metadata** — Refresh dated checklists, stable release notes, known limitations and final audit with accurately scoped claims. Do not present candidate files as a public stable release.
5. **Exact publication artifact** — After final reviewed source/docs commit, rebuild/check exact package and `SHA256SUMS` for that commit, inspect source/license/contents, confirm final CI and verify the actual asset to be uploaded. Do not use the local SHA above as a universal release checksum.
6. **Explicit owner authorization** — Do not create or push `v1.0.0`, publish a GitHub Release, or modify an already published prerelease without a separate explicit owner instruction.

**Release decision:** **HOLD / NO-GO pending the remaining checks and express approval.** This report only documents acceptance work already reported; it does not itself authorize publication.
