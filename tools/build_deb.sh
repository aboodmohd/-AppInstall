#!/usr/bin/env bash
set -euo pipefail

srcdir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="${1:-.}"
mkdir -p -- "$output_dir"
output_dir="$(realpath -- "$output_dir")"
pkgdir="$(mktemp -d)"
trap 'rm -rf -- "$pkgdir"' EXIT

# Reuse the system package payload and version from the Arch recipe.
source "$srcdir/PKGBUILD"
package

install -d "$pkgdir/usr/lib/appinstall"
mv "$pkgdir"/usr/bin/* "$pkgdir/usr/lib/appinstall/"
ln -s ../lib/appinstall/appinstall "$pkgdir/usr/bin/appinstall"
install -m0644 "$srcdir/LICENSE" "$pkgdir/usr/share/doc/appinstall/copyright"
rm -r -- "$pkgdir/usr/share/licenses"

install -d "$pkgdir/DEBIAN"
cat > "$pkgdir/DEBIAN/control" <<CONTROL
Package: appinstall
Version: $pkgver-$pkgrel
Architecture: all
Section: utils
Priority: optional
Maintainer: Abood <abood@localhost>
Depends: bash, coreutils, curl, python3, xdg-utils, python3-pyside6.qtwidgets | python3-pyqt6
Recommends: desktop-file-utils, shared-mime-info, libarchive-tools, zenity | kdialog
Suggests: pkexec, flatpak, podman, distrobox, squashfs-tools, binutils, libfuse2t64, libnotify-bin
Homepage: $url
Description: $pkgdesc
 Review and install Linux application packages from the desktop.
CONTROL

dpkg-deb --root-owner-group --build "$pkgdir" "$output_dir/${pkgname}_${pkgver}-${pkgrel}_all.deb"
