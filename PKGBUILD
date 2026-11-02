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
        'manager.py'
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
b2sums=('3b2e821679c1eb4607152ea1db8a7ed6b3c5a293fe24caccf41be04c0197d7102fc6b7098bac1085897d10bff66ce785a9dbe4c04d5b6074fc75a5c963dc4a60'
        'b6359aa735dacaf21528fe450bd9fbd11ec07e8e2230e60c56e67336d79b0dc3b530c7dbf0b057279b51a7cab6c872229efe6e052ab250b333e262da697c2c18'
        '565f679e8e01d0f5d0e60fb49b3804c3c603461d6cbd1f7e9a01e2acd28a237b79d8386834dcd2a8a24e7080d811656d231be5772c074cc5e42a818c027f3ee2'
        '33b03523416e4329d0f8b1bebde24805bde1eb122f0cb6b21e0b3bf23f69f569a3d5175fc1cde7c4af20b5868e48ab5d99769a073ff8cdf9752666f02f4818d8'
        '9acc9b0cb15dd2082ba078cf1240995d443bdf974d0fc37719cb42e982379343e38a7d35a397fb87a17d82f76b29cc4bdaac0c9902c9387126f99e52d5ee47c9'
        'fb79957f8c55268b58cad39efe05173bd614f801c3af5b0fc21aab74eb4e07ba30630dcdcd56524cc1c69a8dc30808490e3e196136cb798457d734934afaae09'
        '7c06d68680c03fa030412fb585c6e2bf834e24634ddc8c2b97517f648cce9dcc5bd6c95e6d5cc226921f7a1ca9477092d0917d40f8cd926216ec0f3066a004cc'
        '8e9b705959fc0b9d21b76a8d7b4aaf2294d13cf7bb84afbc8af114ef072ed4f1d592936d64afc824da3c9ff7786ef2601c8130d375ec342942adcde59e5fc85f'
        'a70357db526a6c879c8e9edeaa2385df81ade78783c48a4f802b4d7322953b82472c3781b7a42ad266f3b81dcfff45cd412282a05d352fdf5d8a476f6ee627ce'
        '1807a6d5f96b34bd82b1abda46a21245a97ac2c1a9b7da2fa85a0bb4f1745d513aa1393a11a560a988ccdc0e72deded75ec1546207d6b4c9393220daa421466a'
        'bfe9ffd1557d5856bbcb33e5e271b9141f30aa0a029563b5d59a2f89d4de64330fe3a4c942007dc9b69727521664bcc3de015789995beeae7a4d5c18d322c54a'
        'f4b39e8d3c36c643ecac3286b3f1208ea6761cad29a3fa53940881dbab212b0627162ca76731b06c1a97935e0276be3e1bd9cc4c3b5dd01b7c550d6e45c4233c'
        '2e40e316cf3f2f4f37ddba5e4cfa56f19cff6dd4ce453331a7e8285a2253cdd9a0f46f0c70be029c85e043a11a1d5b68f4b41ff90c1dd7c39938811337e0ca9c'
        '7c5cbe8e9e51e99282743c168d4d03347793b5afa25e7eb19b4c2ad90126955d0c0b6e32e4adeb92cee8d3338d01fc53b44e78f96b3f96253d7f91fbd84ca050')

package() {
    for helper in container_backend.py container_ui.py launch_monitor.py manager.py runtime_probe.py diagnostics_core.py diagnostics_ui.py; do
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
