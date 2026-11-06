# AppInstall screenshot provenance review — Stable 1.0

## Owner declaration and review boundary — 2026-11-06

**Owner attestation has already been received.** In the Stable 1.0 review, the owner declared **“AppInstall source code original by me”** and confirmed **all eight `evidence/phase4/` screenshots were theirs and authorized** for public redistribution. See the [recorded owner declaration in issue #14](https://github.com/aboodmohd/-AppInstall/issues/14#issuecomment-6656840134). **Do not ask the owner to repeat this statement solely because earlier checklists were left blank.**

**What this establishes:** a recorded declaration by the copyright claimant concerning their original contributions and the eight screenshots. It is **not** an independent ownership investigation, evidence about third-party snippets/icons, or an audit of all applicable software licenses. A subsequent technical inventory inspected source/packaging and found no obvious bundled third-party executables, but does **not** certify all code provenance or satisfy every notice obligation ([technical review](https://github.com/aboodmohd/-AppInstall/issues/14#issuecomment-6657199708)).

**For final sign-off:** identify any externally sourced snippets or artwork, check relevant licenses/notices and document attribution or removal if required. Review the existing [dependency license audit](DEPENDENCY_LICENSE_AUDIT.md). Record the reviewer, reviewed scope and date in [issue #14](https://github.com/aboodmohd/-AppInstall/issues/14) before closing the **independent third-party rights/notice** item. This is separate from the already recorded owner statement.

**Release status: HOLD / NO-GO.** Fresh **separately installed CachyOS** acceptance, verification of the exact asset to be published, and fresh explicit owner approval remain open. An unchanged binary payload check does not authorize a Stable release.

The earlier 2026-11-04 inventory and unchecked human-review list are retained below as historical context; where they request the **owner declaration**, that part is now documented above. Independent rights clearance remains pending.

---

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
