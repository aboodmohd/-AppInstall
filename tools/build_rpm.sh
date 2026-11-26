#!/usr/bin/env bash
# Build a native noarch RPM from the same reviewed sources as PKGBUILD and DEB.
# Run as an ordinary user on Fedora with rpm-build, tar and gzip available.
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
out="${1:-$root/dist}"
mkdir -p -- "$out"
out="$(realpath -- "$out")"

if (( EUID == 0 )); then
    echo 'Do not build AppInstall RPMs as root.' >&2
    exit 2
fi
for command in rpmbuild tar gzip sed install mv ln cp; do
    command -v "$command" >/dev/null || {
        printf 'Required RPM build tool not found: %s\n' "$command" >&2
        exit 2
    }
done

work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/top"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

# PKGBUILD.package() provides the authoritative file inventory and copies
# trusted repository-local scripts/images. No network downloads or installs.
srcdir="$root"
pkgdir="$work/payload"
source "$root/PKGBUILD"
package

# Match the tested Debian layout: appinstall's helpers live beside it,
# /usr/bin/abood-appinstall is a relative link to the packaged executable.
test -x "$pkgdir/usr/lib/abood-appinstall/appinstall"
test -L "$pkgdir/usr/bin/abood-appinstall"
test -f "$pkgdir/usr/lib/abood-appinstall/manager_ui/main.qml"
test -f "$pkgdir/usr/share/licenses/abood-appinstall/LICENSE"
grep -Fxq 'Exec=/usr/bin/abood-appinstall %F' \
    "$pkgdir/usr/share/applications/io.github.aboodmohd.AppInstall.desktop"

sed -e "s/@VERSION@/$pkgver/g" -e "s/@RELEASE@/$pkgrel/g" \
    "$root/packaging/appinstall.spec.in" > "$work/top/SPECS/appinstall.spec"

# The RPM input tar is an installation payload staged from the canonical
# PKGBUILD; its contents are enumerated in the spec's %files section.
tar -czf "$work/top/SOURCES/appinstall-${pkgver}.tar.gz" -C "$pkgdir" usr
rpmbuild -bb --define "_topdir $work/top" \
    "$work/top/SPECS/appinstall.spec"

rpm_file="$work/top/RPMS/noarch/abood-appinstall-${pkgver}-${pkgrel}.noarch.rpm"
test -s "$rpm_file"
cp -- "$rpm_file" "$out/"

printf 'Created %s\n' "$out/$(basename "$rpm_file")"
sha256sum "$out/$(basename "$rpm_file")"
