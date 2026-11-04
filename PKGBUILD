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
        'SECURITY_REVIEW.md'
        'integration.py'
        'source_transaction.py')
b2sums=(
        'bc71921018aa77cf4086411457ee14fb606fd3078955bf0b8971a5f1502f3a9e13d86aa48b5f824c5598d769a855e90c1e8efd07dd8b41a2efc7e0396ef000f0'
        '16c4910c07dcc10eb6953329144c8be9db021f9ddf9785e7b1f832e280cc1dc1297a4935e005c44ba9614a50ce371a9c13c45fffadcb34dca95a2d6f7a20e154'
        '565f679e8e01d0f5d0e60fb49b3804c3c603461d6cbd1f7e9a01e2acd28a237b79d8386834dcd2a8a24e7080d811656d231be5772c074cc5e42a818c027f3ee2'
        '53047e37e4510e466a620f6d2ff08f7d6460b734f1e938ea7d952deed6ff25f056d09a94bba5f7a2dd978d7f55f072c3d0983345fe70fe33c617f6b4f7de92d0'
        'd06b9051e8daa08a2fe2540c7a26be57e56e5b528cf09edeca10c68c488c0b8cb0a565ee8d5279699e8baedc9b2ef00541fabf820bb4df08178e1c8bc93e42be'
        '9acc9b0cb15dd2082ba078cf1240995d443bdf974d0fc37719cb42e982379343e38a7d35a397fb87a17d82f76b29cc4bdaac0c9902c9387126f99e52d5ee47c9'
        'fb79957f8c55268b58cad39efe05173bd614f801c3af5b0fc21aab74eb4e07ba30630dcdcd56524cc1c69a8dc30808490e3e196136cb798457d734934afaae09'
        '0968a84458830c8888a2e7a5059bf74a01e80e5c85a78ede7e492ce88ec246a4b77a5e05264faa818383dd8831ea0a81da7bd1551f641110b8e0e6f099a15dca'
        '8e9b705959fc0b9d21b76a8d7b4aaf2294d13cf7bb84afbc8af114ef072ed4f1d592936d64afc824da3c9ff7786ef2601c8130d375ec342942adcde59e5fc85f'
        'a70357db526a6c879c8e9edeaa2385df81ade78783c48a4f802b4d7322953b82472c3781b7a42ad266f3b81dcfff45cd412282a05d352fdf5d8a476f6ee627ce'
        '1807a6d5f96b34bd82b1abda46a21245a97ac2c1a9b7da2fa85a0bb4f1745d513aa1393a11a560a988ccdc0e72deded75ec1546207d6b4c9393220daa421466a'
        '1b3abdb09c9804b55e0fa3e4964e9017685aa55c6e6138922e4b43439b53eb41d7b7e5e3bb6adc3afec1e192611be8226da2c82d30c068e532b20f0041e7a048'
        'f4b39e8d3c36c643ecac3286b3f1208ea6761cad29a3fa53940881dbab212b0627162ca76731b06c1a97935e0276be3e1bd9cc4c3b5dd01b7c550d6e45c4233c'
        '2e40e316cf3f2f4f37ddba5e4cfa56f19cff6dd4ce453331a7e8285a2253cdd9a0f46f0c70be029c85e043a11a1d5b68f4b41ff90c1dd7c39938811337e0ca9c'
        '7c5cbe8e9e51e99282743c168d4d03347793b5afa25e7eb19b4c2ad90126955d0c0b6e32e4adeb92cee8d3338d01fc53b44e78f96b3f96253d7f91fbd84ca050'
        '47f6c40b40db8c3ef0fc926f191a0ebc457672c1a1744f1105672c8acbd313bcbe9451f87960390f21c5c553741bffd01e8ceaf5dafeffbd3c1548a14c018e1f'
        'fb989f8ee11448944229f9268b47ac9c645191f1cf58943837b3215dd596decf989bd023d8bf7b1444f5d3be36aa58059e86e8693d192c606d6c3fe43ec47c77'
        'aa57bc6a30118876bba2d2360383e2bb13b43738dc8d87296f7cfa53df1c19c3b2348dd1a4ffb00199a8a06a0f0dbf285edd7e33edffad02e98a9f07c29fb72d'
        'eb7caf4bc1e66f0db898e56dd98926b96b7afbf5b1a561aff75f06e93bbe0ad45f169230f0938c76d9770ce82b4895295a7c47e94b1fbd1b7a70c455dbd0ad4a'
        '520889f14ed3fb648f8b24336ced260e6636052267d56a39be2e6f06f3ee19ad8cef62d0ea4b5dd665bc28cddbc15e5807bd21bf28d051ff7b0c3eae87ca58da'
        '4ae88c7cee2605330507c48298d9cb4af5bbc30c7df5cb0f7a6065247f4ea8c80b82e6f607691b0552f10c2d9dbf88536a112fea27140533265155a34120a013'
        '9afafeb092f90a9495072d37e94da817772512180dc913819fa70ad483d789f33a60e318d81370b2121e01767c53517503c8fb08fb439aafce2dccf4a806b234'
        'a777340a4861bff7030996f6083d7c40c12f592da9c9ad48f4e257c1f18750d32368e782afb3f2ff4c5bb0fa4de6aa3a5023950417b5ab8e1b249151f9d967dc'
        'ce04bc2194dd2ca59bedc16047090e361d9c06a1fafc6ce47814966a6d16a70046a547505221f0507e744a669e69cef356cdf6117920a15b4821332b2a792844'
        'c4f23c2cffc1ee91985059cff9d29d27f5629ade85d8819565f1fdec0a871b345b63f517cc9521241a3006a77410dae3c9dac887a765db0b6f3a3f97ccdaadc9'
        '0226a6e54ff3f6fb8ef15a36b2b6ce6ddcfac6cf63d641e923884e2110ab69184af63d0743f8d858eddfb40fe075239e8cd53df136c97cc053fecc7246a0c2d3'
        '00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
)

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
