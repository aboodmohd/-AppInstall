# Maintainer: Abood <abood@localhost>
pkgname=appinstall
pkgver=0.2.0
pkgrel=1
pkgdesc="Double-click installer for .flatpak/.flatpakref/.flatpakrepo/.AppImage files (Linux desktops)"
arch=('any')
url="https://github.com/aboodmohd/-AppInstall"
license=('MIT')
depends=('bash' 'coreutils' 'xdg-utils' 'python')
optdepends=('flatpak: Flatpak installation' 'kdialog: KDE dialogs' 'zenity: GNOME and Xfce dialogs' 'pyside6: graphical app preview' 'libnotify: notifications' 'fuse2: AppImage mounting' 'podman: rootless DEB/RPM containers' 'distrobox: DEB/RPM integration' 'libarchive: package inspection' 'binutils: optional static ELF dependency checks')
backup=()

source=('appinstall'
        'appinstall.desktop'
        'confirm.py'
        'package_meta.py'
        'ui_style.py'
        'appimage_backend.py'
        'native_backend.py'
        'container_backend.py'
        'container_ui.py'
        'launch_monitor.py'
        'runtime_probe.py'
        'diagnostics_core.py'
        'diagnostics_ui.py')
b2sums=('32a61ce28c73e07483d50baaf6be243dc271e1ef9fe603f396de0ae2ee4162dbb517a922053976dbb2b5437ed3de528c3d6434be69169a2730f47207815721d5'
'b6359aa735dacaf21528fe450bd9fbd11ec07e8e2230e60c56e67336d79b0dc3b530c7dbf0b057279b51a7cab6c872229efe6e052ab250b333e262da697c2c18'
'11182e6fbbaafd30e59dc1d4b7b0d2fab229f5f17bf2bfb21267051832c2655595cdd3e8625e66237df38ee16f43f98b6a6ef465dbcadd73cab21858edc7623c'
'5724b273b622e53188801d8db1b3acfac3a5d90c53b9d2f49625e9e05d6c4c3e5cd6aaf062ed6dd54bca09e4977e147e65419085fff93b460804fae2b581c4db'
'8e9b705959fc0b9d21b76a8d7b4aaf2294d13cf7bb84afbc8af114ef072ed4f1d592936d64afc824da3c9ff7786ef2601c8130d375ec342942adcde59e5fc85f'
'a70357db526a6c879c8e9edeaa2385df81ade78783c48a4f802b4d7322953b82472c3781b7a42ad266f3b81dcfff45cd412282a05d352fdf5d8a476f6ee627ce'
'31e05d750115073d1d397f3a834ba93c15232ba95bed6bf7cbdfd35d0f0730b95d01f8ab56b2ead560b68bfa7eed4fbf42f81a0a3077604c4cc96fabb4135071'
'9ef31bb9bbe7241f9126ac337262d4394ebd493eab515bc87ee292be0eda060050aa2584dadcf95f7efa29e24bc99e20d69df442bfccca74b3139644bd2e9e23'
'f4b39e8d3c36c643ecac3286b3f1208ea6761cad29a3fa53940881dbab212b0627162ca76731b06c1a97935e0276be3e1bd9cc4c3b5dd01b7c550d6e45c4233c'
'2e40e316cf3f2f4f37ddba5e4cfa56f19cff6dd4ce453331a7e8285a2253cdd9a0f46f0c70be029c85e043a11a1d5b68f4b41ff90c1dd7c39938811337e0ca9c'
'39acbda3e5b450123b365bd0d8a356da7d22f7156ca5a3ffa7597cb5a58fb5f2048ed2c6fce5ed7688dcfe0b0bd85b0f0d49c5feed0eb8300215d40a8c6c7565')

package() {
    for helper in container_backend.py container_ui.py launch_monitor.py runtime_probe.py diagnostics_core.py diagnostics_ui.py; do
        install -Dm0644 "$srcdir/$helper" "$pkgdir/usr/bin/$helper"
    done
    install -Dm0644 "$srcdir/native_backend.py" "$pkgdir/usr/bin/native_backend.py"
    install -Dm0644 "$srcdir/appimage_backend.py" "$pkgdir/usr/bin/appimage_backend.py"
    install -Dm0644 "$srcdir/confirm.py" "$pkgdir/usr/bin/confirm.py"
    install -Dm0644 "$srcdir/package_meta.py" "$pkgdir/usr/bin/package_meta.py"
    install -Dm0644 "$srcdir/ui_style.py" "$pkgdir/usr/bin/ui_style.py"
    install -Dm0755 "$srcdir/appinstall" \
        "$pkgdir/usr/bin/$pkgname"
    install -Dm0644 "$srcdir/appinstall.desktop" \
        "$pkgdir/usr/share/applications/$pkgname.desktop"
}
