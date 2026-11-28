# Native ARM64 (aarch64) support

## Support matrix

| Surface | x86_64 / amd64 | aarch64 / arm64 |
|---|---|---|
| One-command installer (`install.sh`) | native | native |
| Portable source install | native | native |
| Arch `any` package | native | native |
| DEB `all`, native `amd64`, native `arm64` | matching arch only | matching arch only |
| RPM `noarch`, native `x86_64`, native `aarch64` | matching arch only | matching arch only |
| Container DEB/RPM inspection | `amd64`, `x86_64`, `all`, `noarch` | `arm64`, `aarch64`, `all`, `noarch` |
| AppImage ELF machine type 62/183 | 62 | 183 |
| Flatpak refs from installed apps | host ref | host ref |
| Premium UI / PySide6 / Qt QML | supported | supported |

## Product changes

- `install.sh` now accepts `x86_64` and `aarch64` from `uname -m` via
  `supported_arch()`. Every other machine type is refused before any package
  manager runs. No binfmt/QEMU registration, `--platform` override or other
  cross-architecture emulation is enabled by the product.
- Native package backends were already host-derived (`dpkg --print-architecture`,
  `rpm --eval %{_arch}`, `platform.machine()`); no behavior change was needed.
  Regression tests now prove amd64/arm64 DEB and x86_64/aarch64 RPM acceptance,
  matching `all`/`noarch` preservation and foreign-architecture refusal.

## Runtime acceptance

`.github/workflows/arm64-native.yml` runs entirely on native `ubuntu-24.04-arm`
hosts and native arm64 container images:

- architecture unit gates and shell syntax on an aarch64 host;
- portable install, PySide6/Qt QML smoke, MIME record, real upgrade/rollback and
  uninstall through `tools/ci_portable_upgrade.py`;
- DEB and RPM legacy migration, upgrade, rollback, data and MIME preservation
  through `tools/ci_native_upgrade_rollback.sh` in Debian 13 and Fedora 44 arm64
  containers;
- real Podman and Distrobox arm64 container execution, plus a genuine arm64 DEB
  accepted by `container_backend.inspect_package`;
- a genuine aarch64 Flatpak ref and a genuine aarch64 AppImage validated by the
  production `validate_appimage` path.

Additional native-runtime acceptance (v1.10.0 release candidate):

- a genuine third-party **arm64 DEB** (`hello`) is inspected by the production
  native backend, installed with APT, launched and removed in Debian 13 arm64;
  a genuine **amd64** build is refused and application records are unchanged;
- a genuine third-party **aarch64 RPM** is inspected, installed with DNF,
  launched and removed in Fedora 44 arm64; a genuine **x86_64** build is
  refused and records are unchanged;
- a genuine **aarch64 AppImage** is validated by the production validator and
  launched; a real **aarch64 Flatpak** is installed, launched, updated and
  removed;
- the **one-command installer** is exercised on an aarch64 host both as a dry
  run against live release metadata and as a real install from locally built,
  checksum-verified candidate artifacts, followed by uninstall with records
  preserved;
- **Discover Apps** repository filtering uses real `apt-cache` output and the
  production catalog on aarch64; update detection uses the real installer.

Foreign-architecture packages are rejected before any package manager runs.
No binfmt/QEMU registration or `--platform` override is used anywhere.

x86_64 compatibility and the Premium UI remain covered by the existing x64 jobs.
Arch Linux ARM is not covered by an official native CI image; its architecture
neutral `any` package is unchanged and x64 Arch coverage is intact. No release
is published from this branch.
