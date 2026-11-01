# Maintainer: Abood <abood@localhost>
pkgname=appinstall
pkgver=0.2.0
pkgrel=1
pkgdesc="Double-click installer for .flatpak/.flatpakref/.flatpakrepo/.AppImage files (Linux desktops)"
arch=('any')
url="https://github.com/aboodmohd/-AppInstall"
license=('MIT')
depends=('bash' 'coreutils' 'xdg-utils' 'python')
optdepends=('flatpak: Flatpak installation' 'kdialog: KDE dialogs' 'zenity: GNOME and Xfce dialogs' 'pyside6: graphical app preview' 'libnotify: notifications' 'fuse2: AppImage mounting' 'podman: rootless DEB/RPM containers' 'distrobox: DEB/RPM integration' 'libarchive: package inspection')
backup=()

source=('appinstall'
        'appinstall.desktop'
        'confirm.py'
        'appimage_backend.py'
        'native_backend.py'
        'container_backend.py'
        'container_ui.py')
b2sums=('d1bb0f9d62cedcce18d9d33288829e529365ef5789a57258d7607d01662a058e1bf3731acf07714ad2030f0c326649b4ae580c28e6cd395ceaee9c19969607f5'
'6088aedd79867e4a9df2a471177a33ff7070aab45fea8ede44dbade3e391de45d253b9f49e8c7336e757f9448ed4c4b1d7a2029637069a2c2c1f695a918d5229'
'90acaad6d0d6e653d1ef1b2efce6faedcd9e2aeb0618f5db7d39945a8e9b17c2bee12fdcd2275f8814039694e82d257afb203a03f05fcd3e56893de5f8423f36'
'38059b90ea7b7568a98cc95f3e4476a9570d80e86f6cb51be360751894f7e38343f1b04a5a0b9763402c4dda020482f38d1714aa774ffe2eb62e060ccdcbd9a1'
'8e9b705959fc0b9d21b76a8d7b4aaf2294d13cf7bb84afbc8af114ef072ed4f1d592936d64afc824da3c9ff7786ef2601c8130d375ec342942adcde59e5fc85f'
'17f98f2bc81c4aa6ac20b040290df836914a4673cc2612453f620cbb9e0774c7735ffba86b442cbe5147658b647e3c1d953ae85416b09c2bbbed7097c1b3be97'
'87ef05bf6c9b8e85461b3571a1f32b9bff4ba17c57ea018e11f88009f2d87fa7853694998caa62685ed38e61541cfbf65a6149feafff89f2be04651842d8e694')

package() {
    for helper in container_backend.py container_ui.py; do
        install -Dm0644 "$srcdir/$helper" "$pkgdir/usr/bin/$helper"
    done
    install -Dm0644 "$srcdir/native_backend.py" "$pkgdir/usr/bin/native_backend.py"
    install -Dm0644 "$srcdir/appimage_backend.py" "$pkgdir/usr/bin/appimage_backend.py"
    install -Dm0644 "$srcdir/confirm.py" "$pkgdir/usr/bin/confirm.py"
    install -Dm0755 "$srcdir/appinstall" \
        "$pkgdir/usr/bin/$pkgname"
    install -Dm0644 "$srcdir/appinstall.desktop" \
        "$pkgdir/usr/share/applications/$pkgname.desktop"
}
