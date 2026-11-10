# AppInstall dependency and license audit

## Targeted technical review — 2026-11-10

**Repository commit examined:** `8b99a0c06de473ec04d56495ef58d44ff93512f1`.

The primary Bash CLI, AppImage/Flatpak and container backends, user
interfaces, manager, diagnostics, monitor, source transaction, user installer,
desktop integration, screenshot tool and `PKGBUILD` were inspected for obvious
copied/vendored components and assets. No specific third-party executable,
vendored library, copied third-party source or proprietary bundled art was
identified in that limited technical inspection. **This is not independent
legal certification or proof of originality.**

- PySide6 imports use QtCore, QtGui and QtWidgets; Qt for Python is offered
  under LGPLv3/GPLv3 or commercial licensing. No Qt GPL-only add-on import was
  identified in the examined modules. Comply with the actual Qt/PySide6 terms.
- Flatpak (LGPL-2.1), Distrobox (GPL-3.0-only), Podman and other platform tools
  are separate host-installed dependencies, not source/binaries included in
  this Arch package. The project does not relicense those dependencies.
- The Arch package contains the project's MIT notice, code, desktop/KIO files
  and documents, without repository screenshots or bundled Qt dependencies.
- Screenshots are still in the public source repository. Owner declarations
  for original AppInstall source and all eight owner-authorized screenshots
  already exist in [issue #14](https://github.com/aboodmohd/-AppInstall/issues/14#issuecomment-6656840134).
  No repeated declaration is needed merely because older checkboxes exist.
- The screenshot tool's test icon is a generated dummy fixture, not a
  vendored external artwork file. Runtime icons may be supplied by installed
  apps or desktop themes and are not bundled by AppInstall here.

**Open human review:** Identify any externally copied snippets/artwork not
apparent in the inventory, document any required notice or permission,
and record reviewer/date/scope in issue #14. This is not an unlimited
copyright warranty. Future self-contained bundles require a new audit.

**Primary sources:** https://doc.qt.io/qtforpython-6/ ;
https://doc.qt.io/qt-6/licensing.html ;
https://github.com/flatpak/flatpak ;
https://github.com/89luca89/distrobox

---

## Historical review — 2026-11-04

**Status:** Repository/source packaging review in progress. **Not legal advice**
and not a certification that every third-party component or asset is clear
for redistribution. No v1.0.0 stable tag has been created.

## What the Arch package distributes

`PKGBUILD` installs AppInstall's Bash/Python source, desktop integration,
documentation and the project's own `LICENSE` file. It does not bundle the
Python/Qt runtime libraries, Flatpak, Podman, Distrobox, Debian or Fedora
container images, third-party DEB/RPM/AppImage apps, or the evidence PNGs
stored in `evidence/phase4/`. Those remain separately installed, downloaded,
or repository-only resources.

| Component | Where sourced | License observation | Release review |
| --- | --- | --- | --- |
| AppInstall's own code | This repository | `LICENSE` contains an MIT notice | Packaged in `/usr/share/licenses/appinstall/LICENSE`; verify contributor ownership and unreviewed copied code before final release |
| PySide6 / Qt for Python | Distribution-provided `pyside6` dependency | Qt documents LGPLv3/GPLv3 and commercial options; certain Qt modules have different terms | Only modules needed by AppInstall should be used; preserve library license notices/rights; review any future binary bundling separately |
| Flatpak | User-installed, optional external tool | Upstream repository lists LGPL-2.1 | No Flatpak code or runtime redistributed inside AppInstall |
| Distrobox | User-installed, optional external tool | Upstream scripts declare GPL-3.0-only | Invoked via subprocess; no Distrobox scripts vendored by AppInstall |
| Podman | User-installed, optional external container engine | License and dependencies belong to separately installed distribution packages | Confirm distribution-specific packaging and avoid calling Distrobox a security sandbox |
| squashfs-tools, libarchive, binutils, KDialog/Zenity, xdg-utils | Separately installed system tools/dependencies | Licensing varies by individual project and version | Their binaries are not included in AppInstall's package; check any later redistribution separately |
| Third-party applications/installers/images | Supplied by user or downloaded at install time | Each software source has its own terms | AppInstall does not grant redistribution rights for these packages |
| Evidence screenshots | Repository `evidence/phase4/` | Asset provenance/permissions not independently verified | Keep out of binary package; confirm creator rights or remove before tagging public stable source |

## Packaging obligations and checks

- MIT is a license family under Arch's `PKGBUILD` guidance, so an individual
  copy of this project's MIT license notice is installed into
  `/usr/share/licenses/appinstall/LICENSE`, in addition to the existing
  documentation copy.
- The new disposable Arch CI gate compares packaged LICENSE bytes to the
  repository's LICENSE and confirms its presence on install and absence on
  uninstall.
- The clean-package gate checks that installing/removing the system package
  does not silently take over MIME defaults or delete an unrelated test
  user's managed applications, data, or registry.
- This project is source-distributed. If distributing a bundled binary,
  AppImage, Flatpak, installer, or Docker image in the future, repeat the
  license review for *all included code and libraries* and required notices.

## Current dependency boundary

**Core Arch package requirements:** Bash, Python, PySide6, coreutils and
xdg-utils, as declared by the package. **Feature-specific optional tools:**
Flatpak; Podman and Distrobox for DEB/RPM; squashfs-tools for passive
AppImage metadata preview and extraction; KDialog or Zenity for dialogs;
other optional notification/probe tools. Internet access and dependencies
required by individual third-party applications are not under AppInstall's
control. Running DEB/RPM apps inside Distrobox is not a strong security
boundary.

## Checks still open

1. Validate the ownership/provenance of `evidence/phase4/` screenshots and
   any external code copied into AppInstall.
2. Confirm third-party notice requirements if changing the format of the
   distribution or bundling dependencies.
3. Verify runtime/feature dependency behavior on a spare CachyOS/KDE host
   without optional packages.
4. Confirm final v1.0.0 package contents, independent checksum, and
   publication approval.

## References (primary documentation)

- Arch `PKGBUILD` license guidance: https://wiki.archlinux.org/title/PKGBUILD
- Qt for Python licensing: https://doc.qt.io/qtforpython-6/
- Qt licensing and LGPL obligations: https://www.qt.io/development/open-source-lgpl-obligations
- Flatpak project: https://github.com/flatpak/flatpak
- Distrobox project and license headers: https://github.com/89luca89/distrobox
- AppInstall `LICENSE`: ./LICENSE
