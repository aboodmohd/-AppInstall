# Maintainer: Abood <abood@localhost>
pkgname=appinstall
pkgver=1.0.0
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
        'appinstall-appimage-review.desktop'
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
        'url_install.py'
        'url_dialog.py'
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
        'STABLE_RELEASE_AUDIT.md'
        'DEPENDENCY_LICENSE_AUDIT.md'
)
b2sums=(
        'e32657d29e165fdb47b1f8b85c5393f08b5c83cf4e4db81465040f738f5aabc34ff030a9f8d282f7fde3f49e78096f84903964cbaad76c8dfddd878035c14d62'
        '16c4910c07dcc10eb6953329144c8be9db021f9ddf9785e7b1f832e280cc1dc1297a4935e005c44ba9614a50ce371a9c13c45fffadcb34dca95a2d6f7a20e154'
        '729a95b76242bdb55441601fe4386f0a1ba4b0d58bd578d815e2393876ba4e9d5e9d06f7904d6563a4b0772018cc9df90a65cf7e77271d9e24ccbff4f469dd2f'
        '1cd9cc74d62156f23242213c0c93d2adb9b265a119794af8c519f1f50f1e99d6df68a6e0a4db9cae5aaf1a5372255b913b67086b54d7073b26c08d45bdd825dd'
        '7acc6a3942b45a6b44ecab633c7d73172cccffd9d0bed1c670acade7da3dc30139ad9ce0f350747963bafadd0c3a1c55dfae8668d3994b8812b112aabe3f1288'
        '4b02713639278f171e7726e6b1c53d8d798df1219a81b1e306e9aa70dbb5b7865e16216c41fee35a5da7ba4ab3075dc74d9d340d8fc440e3381690d4fc17b14a'
        '9acc9b0cb15dd2082ba078cf1240995d443bdf974d0fc37719cb42e982379343e38a7d35a397fb87a17d82f76b29cc4bdaac0c9902c9387126f99e52d5ee47c9'
        'fb79957f8c55268b58cad39efe05173bd614f801c3af5b0fc21aab74eb4e07ba30630dcdcd56524cc1c69a8dc30808490e3e196136cb798457d734934afaae09'
        '523924a6aa9549689445302ed19c330e388c7ca2b6c69fbbab52a9d5d4149e52f2e068d62aabe9a6149df73eb13f99649a4986deae4a08ccb1e7cf283db7f809'
        '8e9b705959fc0b9d21b76a8d7b4aaf2294d13cf7bb84afbc8af114ef072ed4f1d592936d64afc824da3c9ff7786ef2601c8130d375ec342942adcde59e5fc85f'
        'a70357db526a6c879c8e9edeaa2385df81ade78783c48a4f802b4d7322953b82472c3781b7a42ad266f3b81dcfff45cd412282a05d352fdf5d8a476f6ee627ce'
        '621016128275bbec4b76685c6192d75379e2542cb834614cbcf06f9829772be8f8d3299c4e63f55bb458a0f5fb61e1bb77be4d48e5803005434b5bdb75e9d06d'
        '1b3abdb09c9804b55e0fa3e4964e9017685aa55c6e6138922e4b43439b53eb41d7b7e5e3bb6adc3afec1e192611be8226da2c82d30c068e532b20f0041e7a048'
        'f4b39e8d3c36c643ecac3286b3f1208ea6761cad29a3fa53940881dbab212b0627162ca76731b06c1a97935e0276be3e1bd9cc4c3b5dd01b7c550d6e45c4233c'
        'e59b0098ba2649a51335eb89784c69bacb64089a6932cbb692d5c6f74d8f38a590cf3682e858c60c724bcaf7802f83ade8f758f922cbd3a80fcb2615190f6348'
        '54852a95a10b748ec1478c41a4baa9ad50d9cf571dd234c4bb41d67372fc837de9cd606da52e8375607e2e4d38ef1eb3a3b46c11e77ffa0fa93dc6d435244183'
        '768830d640495c2a0404037e6ce70de5a2d13a5b7a117ee8e05ad20453a02278eae74be615acbf34b395898b6edcee3bf0933912ce7f2d3114cfb32a0be734a4'
        '6cb1f35c13abff0d7f27be11b05dcb927e030fa03548ebdf69302dbdda1ec92990ee77658ac5ae43a9e012fcfee97e5c86c264910cf52498629ed4a2ea4e3bac'
        '8e94cac2c228b48a02e86ef3a05ac2d9da6f554b0ce7295439008de84d3ce632188c97f4b9a85a8132c5f207bc02f85c2db59fbb152fc0dde31f4d04ef078b8a'
        'fb989f8ee11448944229f9268b47ac9c645191f1cf58943837b3215dd596decf989bd023d8bf7b1444f5d3be36aa58059e86e8693d192c606d6c3fe43ec47c77'
        'aa57bc6a30118876bba2d2360383e2bb13b43738dc8d87296f7cfa53df1c19c3b2348dd1a4ffb00199a8a06a0f0dbf285edd7e33edffad02e98a9f07c29fb72d'
        'eb7caf4bc1e66f0db898e56dd98926b96b7afbf5b1a561aff75f06e93bbe0ad45f169230f0938c76d9770ce82b4895295a7c47e94b1fbd1b7a70c455dbd0ad4a'
        '56a9e3de66b2b446b82f692a05826d3e892ffb4da66ee6bf1e51f6d5375af2d67bb0cf87f1f15c18cfcd0026e56972bb7912c3453659ddf2107547131c32311f'
        'b9bbe6e1c56f71d98aed5c4f8ea39fcc342fd337b89a91dea5104a74cc2bfaa651ab4d85ab8bfa377c98d8506def52db0fe7991c3f2be68f838c86da4964d7c1'
        'eabc737038f5606cbc2f1134425ee6ae8fb9ecd8498392dd0f8f850a493100729cc5dbc8457489b1ca4bce513d23dcb13bdbd2af23bbf2020ea1f8a5ac21e71a'
        '98251e5ecb1cf861c371d396af1a044727e282a7334e77b733bbc603cff722072f2bca061da2ef16317aeb00372b45812f803af28d50cc9ea840a06e076814b8'
        'ce04bc2194dd2ca59bedc16047090e361d9c06a1fafc6ce47814966a6d16a70046a547505221f0507e744a669e69cef356cdf6117920a15b4821332b2a792844'
        'c4f23c2cffc1ee91985059cff9d29d27f5629ade85d8819565f1fdec0a871b345b63f517cc9521241a3006a77410dae3c9dac887a765db0b6f3a3f97ccdaadc9'
        'c8e7bf349ffb0716c5e05b52f1c5b691b41fa2dced18655f181a08e40208fe556d722d2bf9dcfefcaf70bd5ae27bcfe738af6306d86db931e2ecc2658022d1d7'
        '79c2dc89139ff6c5492f96729d141b98c928ceb8711c81b35818fca3ee93e5680f326408f672ec156acdb5b9fa4dfa9b873882ed09f78c07f7e0b64de9dbc9cb'
        '7685cb1496c71d074dccff047286242c2a28b9e1fe52a8ea33758414a8f2ab49c6591318f5983207f9bc3f5a3f7333e2e07c66974fa0bd4c35e3a52d1ad2eb66'
        'ad9c11820ca12ef1062f4a995edc015ce8ab902fee1f0c04a3c8666caca8770f4d8bb7352df10c4768b958d0ccdf50d8167c08e0aa8a560857c09c9e8bca10e5'
        '2f17356411c62bfe54df87a45e3c98a54a29dc5707fb587876d7f3df241c6d601dd013e090fd9960db19d113ef7b433f95843592221bde58c9027afbd99ed07f'
        'b7fd9be519714fa463423e16a51059e1e40d3dda14fc0c6df3f7154b9864ab37f8981117f9af4ad5a82c37c92fef943c89641f11bef905ef6fc6f315d6cb287a'
        '1464312d4f2b59164b8a72a2fc606117558faf1a37b3006440ba2ff0da3e037082ed7e79746819b5847dc063b323f80e7106be9a268a2359fc8e57b7d2d371b7'
)
package() {
    for helper in container_backend.py container_ui.py launch_monitor.py manager.py result_ui.py runtime_probe.py diagnostics_core.py diagnostics_ui.py url_install.py url_dialog.py; do
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
    # Pin the system launcher to the pacman-owned executable. A separate
    # source/user install may place an older appinstall first in PATH.
    # integration.py still rewrites its user-level launcher independently.
    sed -i 's|^Exec=appinstall %F$|Exec=/usr/bin/appinstall %F|' \
        "$pkgdir/usr/share/applications/$pkgname.desktop"
    install -Dm0755 "$srcdir/appinstall-appimage-review.desktop" \
        "$pkgdir/usr/share/kio/servicemenus/appinstall-appimage-review.desktop"
    # Use the pacman-owned executable even when ~/.local/bin/appinstall
    # from a source/beta installation appears first in PATH.
    # The source installer rewrites its own menu to the user-local path.
    sed -i 's|^Exec=appinstall %f$|Exec=/usr/bin/appinstall %f|' \
        "$pkgdir/usr/share/kio/servicemenus/appinstall-appimage-review.desktop"
    install -Dm0644 "$srcdir/README.md" \
        "$pkgdir/usr/share/doc/$pkgname/README.md"
    install -Dm0644 "$srcdir/LICENSE" \
        "$pkgdir/usr/share/doc/$pkgname/LICENSE"
    # MIT is a license family, so ship this project's exact notice under
    # /usr/share/licenses as required by Arch packaging guidance.
    install -Dm0644 "$srcdir/LICENSE" \
        "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
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
    for guide in STABLE_ACCEPTANCE.md STABLE_READINESS.md STABLE_RELEASE_AUDIT.md DEPENDENCY_LICENSE_AUDIT.md; do
        install -Dm0644 "$srcdir/$guide" "$pkgdir/usr/share/doc/$pkgname/$guide"
    done
}
