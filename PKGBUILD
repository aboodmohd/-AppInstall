# Maintainer: Abood <abood@localhost>
pkgname=appinstall
pkgver=1.0.0rc1
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
        'source_transaction.py'
        'STABLE_ACCEPTANCE.md'
        'STABLE_READINESS.md'
        'STABLE_RELEASE_AUDIT.md')
b2sums=(
        'f7be76a5b506ba951aaf9034e9e616df00f5b052fd902f1445b7b921201e00b5ebcefa134bce77b411cd4e310b43cc91391f35bb1e561616a5a2abe12cf7365d'
        '16c4910c07dcc10eb6953329144c8be9db021f9ddf9785e7b1f832e280cc1dc1297a4935e005c44ba9614a50ce371a9c13c45fffadcb34dca95a2d6f7a20e154'
        '565f679e8e01d0f5d0e60fb49b3804c3c603461d6cbd1f7e9a01e2acd28a237b79d8386834dcd2a8a24e7080d811656d231be5772c074cc5e42a818c027f3ee2'
        '53047e37e4510e466a620f6d2ff08f7d6460b734f1e938ea7d952deed6ff25f056d09a94bba5f7a2dd978d7f55f072c3d0983345fe70fe33c617f6b4f7de92d0'
        'd06b9051e8daa08a2fe2540c7a26be57e56e5b528cf09edeca10c68c488c0b8cb0a565ee8d5279699e8baedc9b2ef00541fabf820bb4df08178e1c8bc93e42be'
        '9acc9b0cb15dd2082ba078cf1240995d443bdf974d0fc37719cb42e982379343e38a7d35a397fb87a17d82f76b29cc4bdaac0c9902c9387126f99e52d5ee47c9'
        'fb79957f8c55268b58cad39efe05173bd614f801c3af5b0fc21aab74eb4e07ba30630dcdcd56524cc1c69a8dc30808490e3e196136cb798457d734934afaae09'
        '97a4148d8ce805f160e0af13cff2d93eb1ae47c075de877fc4be2524d4e3671758edb0b2eb3a1a1faba471ae8bec0198fc0ecbf6893305782feb0cbb29407bc7'
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
        '55f989206dfb56f7751137b619b6291d550478aaa3167fc25ec581302cacb22c43ac0df89bf0ccf1552953d515f0dd53743f34f8ce8b5d5f51a077e9d9b45a85'
        'f4f3428217374d73b60479801b8e692c15d3fd9923df0c2ef7412edae2e81666c796c9849369d24da242be854dcc4995420fdb88585b2e6769dca3148578be95'
        '627f49de71d9d34e6d728ef3877b59441402c237afdee81836640f2c640d9453e285cae694def116eba0808a58202fb8ecaa3dc37cf1ea72924545bee4986223'
        'caa637e7f0de749cf988d101a5d9c0e9921c9a79a007ddcbe40ae94c189e62d1a4d89937af77b563e8612b7e8e4988b2e0289f88c8ba98baf328643f0abed03c'
        'ce04bc2194dd2ca59bedc16047090e361d9c06a1fafc6ce47814966a6d16a70046a547505221f0507e744a669e69cef356cdf6117920a15b4821332b2a792844'
        'c4f23c2cffc1ee91985059cff9d29d27f5629ade85d8819565f1fdec0a871b345b63f517cc9521241a3006a77410dae3c9dac887a765db0b6f3a3f97ccdaadc9'
        'c8e7bf349ffb0716c5e05b52f1c5b691b41fa2dced18655f181a08e40208fe556d722d2bf9dcfefcaf70bd5ae27bcfe738af6306d86db931e2ecc2658022d1d7'
        '025abf5f04af04a4848313baab6fa9fc8ed97362cec9f97ded33ad2dd5148a4e7aa60c1d6097ae598844ca04314bdddaef0189141b648b6de5e5a8dd3eb82375'
        '7685cb1496c71d074dccff047286242c2a28b9e1fe52a8ea33758414a8f2ab49c6591318f5983207f9bc3f5a3f7333e2e07c66974fa0bd4c35e3a52d1ad2eb66'
        '46eb5952451e8a50c560b0cce52b04d5d42dd51bf58dc8a56626507941a66e1b8a2caad1d58e16198377ea538f8f30b9c11517dfa266eba059d34ba4de7b7934'
        'eea0358f0a2529e7c685173ea1d21ca984f4be010034b770e470a874712ab6531c983c8e012ad9e35a9289ff67f37c2201c1658ee7925e80e147b77d6764d724'
        'b920de30bb683ade8c8cbefe5ae9e4367594976f76c1f65491f12b095c1a4d31c77edcc8345b39721f7f8ab6e35b2256b4d8f183c4361a3389771caf24d8e9f6'
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
    for guide in STABLE_ACCEPTANCE.md STABLE_READINESS.md STABLE_RELEASE_AUDIT.md; do
        install -Dm0644 "$srcdir/$guide" "$pkgdir/usr/share/doc/$pkgname/$guide"
    done
}
