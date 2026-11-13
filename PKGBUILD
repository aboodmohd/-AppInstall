# Maintainer: Abood <abood@localhost>
pkgname=appinstall
pkgver=1.2.0
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
        'qt_compat.py'
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
        # Application icon (official AppInstall logo: blue folder, white download
        # arrow, green checkmark). Distinct source basenames are required because
        # makepkg resolves local sources by basename at $startdir/; the exact
        # approved artwork is preserved at every size (16x16 and 24x24 are
        # downscaled from the smallest supplied 32px render; never upscaled from
        # the largest image). Installed destinations keep the hicolor names.
        'appinstall-16.png'
        'appinstall-24.png'
        'appinstall-32.png'
        'appinstall-48.png'
        'appinstall-64.png'
        'appinstall-128.png'
        'appinstall-256.png'
        'appinstall-512.png'
)
b2sums=(
        'c8ff166827f1ca2afae04e386c2a6d2411a34b2f848ea5d223bf045c12ec5eb56b1bf2098d31394084e082bc34a68206fc43df4acdec5adbff324d8fdea60868'
        'f8da2822ad2a5638b9f7932728727fc624fae695db8cc30470783e1f7e26e719d1fa8624e0533ebcfd1713f99935d7752d0b8b3c46d90c06f2ff034f8b307d59'
        '5a0a824810d4c4d7a8f7f2603f3c4623874eef4de55ee4b360ab0321ecfae8edf42a9443c134e10272fba0b96f89f74cd45473e6ac09c6493595c9ad0cf9c0e5'
        'aa2943ff6d844443cb68654103a1aadadea9c3b000dffe66ef0601999f12e9a6e5cd3b8ab0b7aa7f5c60bebb1fe872ff51aebec12722cce31f98b04194b39cc8'
        '7ffd722a584490349dcefa9c60a51836089b12ec95109945af371a74ae4e154e64932c4d2c254e36447a20b9f35f6a91231c0d7a3bbf77572e9a3b08fadc5f1e'
        '2e05cd589ad5fe269caf53e4f15585792cf0be6fdd18068609e903164d5b976eb4a9bccd789e2fbd13efa9a23fa8ddce50cde9c73bfe1a109620102379d7a7a4'
        '9acc9b0cb15dd2082ba078cf1240995d443bdf974d0fc37719cb42e982379343e38a7d35a397fb87a17d82f76b29cc4bdaac0c9902c9387126f99e52d5ee47c9'
        'ecb167e735b2eb0756fa05ff729caa8494ca1a1d886fe15402f0d2da31087a2e42ec54c1a6b18baca25c66322e5d9ee09fc65e662152604f857f3a0eea58bd83'
        '5063760c7f560672e58512d29229c123b7f6bc4de5af9da5b39c6d6146d744940ddb5ee305d68f4cd820d45908570a6f5e30d8ce94d91d0edb8ee70d2bfe9cc5'
        '523924a6aa9549689445302ed19c330e388c7ca2b6c69fbbab52a9d5d4149e52f2e068d62aabe9a6149df73eb13f99649a4986deae4a08ccb1e7cf283db7f809'
        '8e9b705959fc0b9d21b76a8d7b4aaf2294d13cf7bb84afbc8af114ef072ed4f1d592936d64afc824da3c9ff7786ef2601c8130d375ec342942adcde59e5fc85f'
        'a70357db526a6c879c8e9edeaa2385df81ade78783c48a4f802b4d7322953b82472c3781b7a42ad266f3b81dcfff45cd412282a05d352fdf5d8a476f6ee627ce'
        'c99d5e70a378abfc7429dfa51db7b56549f169d4058835e77a9eb63a18e923a898cca30b191be0ded7a99b03a2903f28b62faf75dcbc358de75b0e235a342bbd'
        '2c9da87d45ed113294d2cecc100900691060c2b0797f23cf21b475119021aa8fcbd9084a51400a0e2e3857fed74e967fd21ae8b2eb52f098d041dc5869b1ddf0'
        'f4b39e8d3c36c643ecac3286b3f1208ea6761cad29a3fa53940881dbab212b0627162ca76731b06c1a97935e0276be3e1bd9cc4c3b5dd01b7c550d6e45c4233c'
        'e59b0098ba2649a51335eb89784c69bacb64089a6932cbb692d5c6f74d8f38a590cf3682e858c60c724bcaf7802f83ade8f758f922cbd3a80fcb2615190f6348'
        '3e53402ffb124710c051e76f63db58fcc6e689356fb9253d8933aa354273e85a6811de06acf3f36cedb33badd3a18c84e51f5ab15198dcdf4334e0f72ba01d67'
        '40312bd4605b692791c1910d2126108ea84f34400131c4e03f00ae257c8d773523da493f687046d3c38a85d7231133bbb789a6f88d8f484e26d17bd5a8226307'
        'e0a21eaab4d618b22566e4ce0a2eeadfe851128b2be1542afed9c4f5e156c810a96cc86c356fd47b65bb5d100e545936819d5b25ad0f6e779059e7e18776c52a'
        '22da7a5816548dd9f33baf9edace3d9d99ee0ef7a556fb07de875dc741ffd14897280032fc7b9a605fe7683b1c06783f69bdb5e00c6f0ffc4c657e0bc9d254e7'
        'fb989f8ee11448944229f9268b47ac9c645191f1cf58943837b3215dd596decf989bd023d8bf7b1444f5d3be36aa58059e86e8693d192c606d6c3fe43ec47c77'
        'aa57bc6a30118876bba2d2360383e2bb13b43738dc8d87296f7cfa53df1c19c3b2348dd1a4ffb00199a8a06a0f0dbf285edd7e33edffad02e98a9f07c29fb72d'
        'eb7caf4bc1e66f0db898e56dd98926b96b7afbf5b1a561aff75f06e93bbe0ad45f169230f0938c76d9770ce82b4895295a7c47e94b1fbd1b7a70c455dbd0ad4a'
        'f6dbd4cbc3ae82e18647264f5246ccd8b372f2b180240faa59eb306e9c0235faac1dc9448a2578aeb1b823f970cef4260c9fa8e5e3c7cc8f4536840470a865a2'
        '1fe6d4c864f9e77aea37b673e41613a181a75ac46cf787a80488a5c927cd76d82bdb532ca42d6b616662b99d99a4ce60bdbc63e26f1a33aabf8e19a9d6a9f58b'
        '01fdb146ae319d157bcf6d449e36d012ef5bd660f13f246bcb0963f0c0b3daa44aa53bce26fe58bb13ff6b2888e03f6340efc59f3b0a6ac25660398e12f5a873'
        'f81bde25bcd98914ac1f7ed02040c78836cee033d5e66c63eff310a614f42ce595e50a9f239f1b112e31271f8eeb1cbde602d501352075ee9b5121e5877c3466'
        'ce04bc2194dd2ca59bedc16047090e361d9c06a1fafc6ce47814966a6d16a70046a547505221f0507e744a669e69cef356cdf6117920a15b4821332b2a792844'
        'c4f23c2cffc1ee91985059cff9d29d27f5629ade85d8819565f1fdec0a871b345b63f517cc9521241a3006a77410dae3c9dac887a765db0b6f3a3f97ccdaadc9'
        'c8e7bf349ffb0716c5e05b52f1c5b691b41fa2dced18655f181a08e40208fe556d722d2bf9dcfefcaf70bd5ae27bcfe738af6306d86db931e2ecc2658022d1d7'
        '20d853d0932504406e942bf43f395a974097d78a28af05c0c22c5972648da5b031999ff016ee55f781dca1c15f77f4ae2f714dc94e2560f96f76855d969b6478'
        '7685cb1496c71d074dccff047286242c2a28b9e1fe52a8ea33758414a8f2ab49c6591318f5983207f9bc3f5a3f7333e2e07c66974fa0bd4c35e3a52d1ad2eb66'
        'ad9c11820ca12ef1062f4a995edc015ce8ab902fee1f0c04a3c8666caca8770f4d8bb7352df10c4768b958d0ccdf50d8167c08e0aa8a560857c09c9e8bca10e5'
        '2f17356411c62bfe54df87a45e3c98a54a29dc5707fb587876d7f3df241c6d601dd013e090fd9960db19d113ef7b433f95843592221bde58c9027afbd99ed07f'
        'b7fd9be519714fa463423e16a51059e1e40d3dda14fc0c6df3f7154b9864ab37f8981117f9af4ad5a82c37c92fef943c89641f11bef905ef6fc6f315d6cb287a'
        '1464312d4f2b59164b8a72a2fc606117558faf1a37b3006440ba2ff0da3e037082ed7e79746819b5847dc063b323f80e7106be9a268a2359fc8e57b7d2d371b7'
        '7eda9399d135de262eea9510dbb5ef1d8542745315ed2b3fbd2719e7f11589fedbd9467c565df7c54d2b5e1ef7c5a99e7def66c3768c912e4bde55970f02dfde'
        'b9f4fc6dfea1045401b6ce200708b3e601bcaad66bc04365104ff5c7219e142b6d613211fcf80cd905989a7706405826d68c37c26744ec48c6c4453b693c8800'
        'fd791c688383b4003c11bfe60149c2323d3b235f503efb41caca1ff8726872b1a4ba1e020e7f8f89550c6dc24452ecd0068941601505d6aeb6084d523f4f4291'
        '3ddf57baed22ab1a10dc3508dbd5ddb7ee676ccb97b93f1a584cc62dd5966195b2db4cdddedc0664ff4344640841e47eb5f058ba62282daa2844e2e9271a0af9'
        'f59647eb4fab4e470f4ea315f671621f7e4275596c3166a469070ab1c7bec638a38ac60823d225bd4290ba62ef92a3bdc53e8b6e3cbda830bf1ed0574a555f09'
        '48f56d95504710dc4ee0dc790aa11323ff82eb90ede2dee7da1d398f00714648333e098bebe4722645404081f016bfea5fe55fe79dff96d9839d9a60622ed47d'
        '93eee495efa0b17d12c4ccb9f5a3c9e5e0943c8f970380a2f02ed6cb9234feb81e97cfbcb30ce05df90726b897d6364e16cacba4ee2db5aef619bb0b78fc168a'
        '52d35713d301522f310302200c6dc53d2b79f683002814cc39fcc0667bb1957b27f28d50d0311c07e8a558a02f617a20858d49d7cd4275d7943a69f60bb9601a'
)
package() {
    for helper in container_backend.py container_ui.py launch_monitor.py manager.py result_ui.py runtime_probe.py diagnostics_core.py diagnostics_ui.py url_install.py url_dialog.py; do
        install -Dm0644 "$srcdir/$helper" "$pkgdir/usr/bin/$helper"
    done
    install -Dm0644 "$srcdir/native_backend.py" "$pkgdir/usr/bin/native_backend.py"
    install -Dm0644 "$srcdir/appimage_backend.py" "$pkgdir/usr/bin/appimage_backend.py"
    install -Dm0644 "$srcdir/confirm.py" "$pkgdir/usr/bin/confirm.py"
    install -Dm0644 "$srcdir/package_meta.py" "$pkgdir/usr/bin/package_meta.py"
    install -Dm0644 "$srcdir/qt_compat.py" "$pkgdir/usr/bin/qt_compat.py"
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
    # Application icon: install the official AppInstall logo to the freedesktop
    # hicolor theme at every supported size, keeping the installed name
    # appinstall.png in each size directory.
    for size in 16 24 32 48 64 128 256 512; do
        install -Dm0644 "$srcdir/appinstall-${size}.png" \
            "$pkgdir/usr/share/icons/hicolor/${size}x${size}/apps/appinstall.png"
    done
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
