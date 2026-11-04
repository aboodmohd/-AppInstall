# AppInstall screenshot provenance review — Stable 1.0

**Review date:** 2026-11-04  
**Status:** Automated evidence verification added; human copyright/redistribution sign-off **still required**. This document is evidence, not certification or permission to publish.

## Repository screenshots

| Filename | Recorded capture method | Supporting Git history |
| --- | --- | --- |
| `confirm-review-light.png` | Qt offscreen, scripted review dialog | [Phase 4 UI evidence](https://github.com/aboodmohd/-AppInstall/commit/49e4050ec4d3bf4c3d643d3445d8214c7ae5e095) |
| `confirm-review-dark.png` | Qt offscreen, scripted review dialog | Phase 4 UI evidence |
| `container-preview-light.png` | Qt offscreen, scripted container preview | Phase 4 UI evidence |
| `container-preview-dark.png` | Qt offscreen, scripted container preview | Phase 4 UI evidence |
| `manager-list-light.png` | Qt offscreen, scripted manager view | [Phase 5 manager](https://github.com/aboodmohd/-AppInstall/commit/21ac829aff2aa4493961522eb987789a950c19f5) |
| `manager-list-dark.png` | Qt offscreen, scripted manager view | Phase 5 manager |
| `manager-details.png` | Qt offscreen, scripted manager details | Phase 5 manager |
| `manager-live-wayland.png` | User-reported live KDE Wayland session; **not captured by the offscreen script** | [Wayland screenshot update](https://github.com/aboodmohd/-AppInstall/commit/d24ce5930ef55b5e5b82033689bc586a17eff421) |

The script `tools/ui_evidence.py` provides the path for the seven offscreen captures. The live capture is supported by repository commit history and `evidence/phase4/RESULTS.md`, but its rights have not been independently confirmed. A byte-size discrepancy in the live screenshot report was corrected from 55,176 to **54,500 bytes** to match the current GitHub file. Individual file SHA-256 values, PNG headers, dimensions, inventory, and report sizes are checked by `tools/ci_release_evidence_gate.py`.

## Distribution boundaries

- The screenshot PNGs live in the public GitHub repository, and ordinary source archives include them.
- `PKGBUILD` does **not** list those screenshots as source entries. The Arch package test independently checks the built archive does not contain them.
- `PKGBUILD` installs the project's checked-in MIT notice into `/usr/share/licenses/appinstall/LICENSE`, which CI byte-compares to the repository license.
- No upstream application binaries or Qt/PySide6/Flatpak/Distrobox/Podman libraries are intentionally bundled in this Arch package.
- None of these technical observations proves ownership, originality, or redistribution permission.

## Owner sign-off — required before a public Stable 1.0 release

- [ ] Confirm each of the eight screenshots is an authorized capture and does not include third-party material that may not be redistributed.
- [ ] Confirm that AppInstall's application source, copied snippets, icons, and other contributed code/assets are original or used under compatible permissions. Record required attributions, or remove material that lacks permission.
- [ ] Review the project MIT notice and `DEPENDENCY_LICENSE_AUDIT.md`.
- [ ] Record the reviewer and date in issue [#14](https://github.com/aboodmohd/-AppInstall/issues/14). Do not check a box until verified.

**No-GO remains in effect.** Also still required: disposable-system CachyOS/KDE desktop acceptance, final uploaded-asset checksum verification, and explicit separate publication authorization.
