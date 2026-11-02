# Maintainer: Abood <abood@localhost>
pkgname=appinstall
pkgver=1.0.0beta1
pkgrel=1
pkgdesc="Double-click installer for AppImage, Flatpak, DEB, and RPM files on Linux desktops"
arch=('any')
url="https://github.com/aboodmohd/-AppInstall"
license=('MIT')
depends=('bash' 'coreutils' 'xdg-utils' 'python' 'pyside6')
optdepends=('flatpak: Flatpak installation' 'kdialog: KDE dialogs' 'zenity: GNOME and Xfce dialogs' 'libnotify: notifications' 'fuse2: AppImage mounting' 'squashfs-tools: passive AppImage preview' 'podman: rootless DEB/RPM containers' 'distrobox: DEB/RPM integration' 'libarchive: package inspection' 'binutils: optional static ELF dependency checks')
backup=()

source=('appinstall'
        'appinstall.desktop'
        'confirm.py'
        'manager.py'
        'result_ui.py'
        'package_meta.py'
        'ui_style.py'
        'appimage_backend.py'
        'native_backend.py'
        'container_backend.py'
        'container_ui.py'
        'launch_monitor.py'
        'runtime_probe.py'
        'diagnostics_core.py'
        'diagnostics_ui.py'
        'README.md'
        'LICENSE'
        'LAUNCH_DIAGNOSTICS.md'
        'INTEGRATION_TESTING.md'
        'CHANGELOG.md'
        'RELEASE_NOTES.md'
        'INSTALL.md'
        'UPGRADE.md'
        'TESTING.md'
        'KNOWN_LIMITATIONS.md'
        'SECURITY_REVIEW.md')
b2sums=('b067d9ee2990c09bb9e1c668443490bb4a7cc389c25d347e4a70f1dcc1142c107afdd5c8d02c7b9a1fe9b216b00e0e867509e14081bfbd548e6b6397576d489a'
        'b7231cd28d06ee2de0e2f7b4cb2cda8a11274b5836f31a615a170cd1c6cfde9e45ad3f1868d1a849bd3953e0de74cc35a2d8def7d3c67bb739bbeeea4cff55b0'
        '565f679e8e01d0f5d0e60fb49b3804c3c603461d6cbd1f7e9a01e2acd28a237b79d8386834dcd2a8a24e7080d811656d231be5772c074cc5e42a818c027f3ee2'
        '23640dd63460b60d7804e9f00b063f55d22e0ba6188860dfa7617f631d8db19b1393b993f6e24a1236a550a736fcfece503fd3a17a46e2191dffa0655ef72859'
        'd06b9051e8daa08a2fe2540c7a26be57e56e5b528cf09edeca10c68c488c0b8cb0a565ee8d5279699e8baedc9b2ef00541fabf820bb4df08178e1c8bc93e42be'
        '9acc9b0cb15dd2082ba078cf1240995d443bdf974d0fc37719cb42e982379343e38a7d35a397fb87a17d82f76b29cc4bdaac0c9902c9387126f99e52d5ee47c9'
        'fb79957f8c55268b58cad39efe05173bd614f801c3af5b0fc21aab74eb4e07ba30630dcdcd56524cc1c69a8dc30808490e3e196136cb798457d734934afaae09'
        '7c06d68680c03fa030412fb585c6e2bf834e24634ddc8c2b97517f648cce9dcc5bd6c95e6d5cc226921f7a1ca9477092d0917d40f8cd926216ec0f3066a004cc'
        '8e9b705959fc0b9d21b76a8d7b4aaf2294d13cf7bb84afbc8af114ef072ed4f1d592936d64afc824da3c9ff7786ef2601c8130d375ec342942adcde59e5fc85f'
        'a70357db526a6c879c8e9edeaa2385df81ade78783c48a4f802b4d7322953b82472c3781b7a42ad266f3b81dcfff45cd412282a05d352fdf5d8a476f6ee627ce'
        '1807a6d5f96b34bd82b1abda46a21245a97ac2c1a9b7da2fa85a0bb4f1745d513aa1393a11a560a988ccdc0e72deded75ec1546207d6b4c9393220daa421466a'
        'bfe9ffd1557d5856bbcb33e5e271b9141f30aa0a029563b5d59a2f89d4de64330fe3a4c942007dc9b69727521664bcc3de015789995beeae7a4d5c18d322c54a'
        'f4b39e8d3c36c643ecac3286b3f1208ea6761cad29a3fa53940881dbab212b0627162ca76731b06c1a97935e0276be3e1bd9cc4c3b5dd01b7c550d6e45c4233c'
        '2e40e316cf3f2f4f37ddba5e4cfa56f19cff6dd4ce453331a7e8285a2253cdd9a0f46f0c70be029c85e043a11a1d5b68f4b41ff90c1dd7c39938811337e0ca9c'
        '7c5cbe8e9e51e99282743c168d4d03347793b5afa25e7eb19b4c2ad90126955d0c0b6e32e4adeb92cee8d3338d01fc53b44e78f96b3f96253d7f91fbd84ca050'
        '3dcf80d5739c6c7181299ffe960717fbcc35de5e475ae9471602a3466cb9be800312bb566ac160184a7fd604d7d8aa9c94ca582b8cba95e9ce64d0656c2c0d7d'
        'fb989f8ee11448944229f9268b47ac9c645191f1cf58943837b3215dd596decf989bd023d8bf7b1444f5d3be36aa58059e86e8693d192c606d6c3fe43ec47c77'
        'aa57bc6a30118876bba2d2360383e2bb13b43738dc8d87296f7cfa53df1c19c3b2348dd1a4ffb00199a8a06a0f0dbf285edd7e33edffad02e98a9f07c29fb72d'
        'eb7caf4bc1e66f0db898e56dd98926b96b7afbf5b1a561aff75f06e93bbe0ad45f169230f0938c76d9770ce82b4895295a7c47e94b1fbd1b7a70c455dbd0ad4a'
        'c6c2daabb99268993322d93c39012f16345334c6eadd3e86f51943cecefea9d4550736a24339890c3b341181a83490d2b547c09fcf9ee2c66ef9b7c026bea22c'
        'ee2fc962ba3b30d3d356cbdeb44939d3fd2c399d7693abad00dca774b9775a78315fbf1645b62215a71cacf33c24f0aa034245520c6ab23b99722d8ede252bbd'
        'd7a0d0ca410449442f6348bf9329142555662e7aadbfb1c2abc0f76868dda2234cdd781cff63b82660f5a0f5468de987580f9e9a90e3922aa5582ab91d66c041'
        'caae490bc3a4aead63de15fa31c3b2694e189605b5576e411aafc9eaa7fd588a9877470a080790d44908a4a9d6979ca26332b342c4254997be3533c4fe92c64d'
        '4891a544d48be058c9dcef0e32fe7429f60a327addaefdc58482c145f473d617e2a7b969506688f747d60ce4e7ea2be5133ad98a95b62c651ef9ba63890baa6f'
        'c4f23c2cffc1ee91985059cff9d29d27f5629ade85d8819565f1fdec0a871b345b63f517cc9521241a3006a77410dae3c9dac887a765db0b6f3a3f97ccdaadc9'
        'b3a8152e57e4945baaaad58db67aafb8c741a0fd25eaae96d0f0055a74dec859d8cf5cb6713da8e76a9767778f8d787baaf2b03ca5ac22857a607c8ee81ffb32')

package() {
    for helper in container_backend.py container_ui.py launch_monitor.py manager.py result_ui.py runtime_probe.py diagnostics_core.py diagnostics_ui.py; do
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
    install -Dm0644 "$srcdir/README.md" \
        "$pkgdir/usr/share/doc/$pkgname/README.md"
    install -Dm0644 "$srcdir/LICENSE" \
        "$pkgdir/usr/share/doc/$pkgname/LICENSE"
    install -Dm0644 "$srcdir/LAUNCH_DIAGNOSTICS.md" \
        "$pkgdir/usr/share/doc/$pkgname/LAUNCH_DIAGNOSTICS.md"
    install -Dm0644 "$srcdir/INTEGRATION_TESTING.md" \
        "$pkgdir/usr/share/doc/$pkgname/INTEGRATION_TESTING.md"
    install -Dm0644 "$srcdir/CHANGELOG.md" \
        "$pkgdir/usr/share/doc/$pkgname/CHANGELOG.md"
    install -Dm0644 "$srcdir/RELEASE_NOTES.md" \
        "$pkgdir/usr/share/doc/$pkgname/RELEASE_NOTES.md"
    install -Dm0644 "$srcdir/INSTALL.md" \
        "$pkgdir/usr/share/doc/$pkgname/INSTALL.md"
    install -Dm0644 "$srcdir/UPGRADE.md" \
        "$pkgdir/usr/share/doc/$pkgname/UPGRADE.md"
    install -Dm0644 "$srcdir/TESTING.md" \
        "$pkgdir/usr/share/doc/$pkgname/TESTING.md"
    install -Dm0644 "$srcdir/KNOWN_LIMITATIONS.md" \
        "$pkgdir/usr/share/doc/$pkgname/KNOWN_LIMITATIONS.md"
    install -Dm0644 "$srcdir/SECURITY_REVIEW.md" \
        "$pkgdir/usr/share/doc/$pkgname/SECURITY_REVIEW.md"
}
