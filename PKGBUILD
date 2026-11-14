# Maintainer: Abood <abood@localhost>
pkgname=appinstall
pkgver=1.4.0
pkgrel=1
pkgdesc="Double-click installer for AppImage, Flatpak, DEB, and RPM files on Linux desktops"
arch=('any')
url="https://github.com/aboodmohd/-AppInstall"
license=('MIT')
depends=('bash' 'coreutils' 'xdg-utils' 'python' 'pyside6' 'curl')
optdepends=('polkit: graphical update authentication' 'flatpak: Flatpak installation' 'kdialog: KDE dialogs' 'zenity: GNOME and Xfce dialogs' 'libnotify: notifications' 'fuse2: AppImage mounting' 'squashfs-tools: passive AppImage preview' 'podman: rootless DEB/RPM containers' 'distrobox: DEB/RPM integration' 'libarchive: package inspection' 'binutils: optional static ELF dependency checks')
backup=()

source=('install.sh'
        'appinstall'
        'appinstall.desktop'
        'appinstall-appimage-review.desktop'
        'confirm.py'
        'manager.py'
        'result_ui.py'
        'package_meta.py'
        'qt_compat.py'
        'ui_style.py'
        'settings.py'
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
        'c7264db7f7f741b428b8fa5650978a16e3136a5a9f8a4af3d141a07be861903bb33a21dc0ade81bdeba52b0a0480d7131fd84d94dfbd2809679ef29e657cbb83'
        '6e61f3b67184e76ca3c878f3e2e85ad1f9ea474aa96a9352a8d45bb6565938add46d8dc31ff6c7b2cd039a939a16cb2f57954cb72d31c19f30668354560e62c8'
        'f8da2822ad2a5638b9f7932728727fc624fae695db8cc30470783e1f7e26e719d1fa8624e0533ebcfd1713f99935d7752d0b8b3c46d90c06f2ff034f8b307d59'
        '5a0a824810d4c4d7a8f7f2603f3c4623874eef4de55ee4b360ab0321ecfae8edf42a9443c134e10272fba0b96f89f74cd45473e6ac09c6493595c9ad0cf9c0e5'
        'aa2943ff6d844443cb68654103a1aadadea9c3b000dffe66ef0601999f12e9a6e5cd3b8ab0b7aa7f5c60bebb1fe872ff51aebec12722cce31f98b04194b39cc8'
        'f98e5f080c7a4dfff9a52913c8b64e2a803a83275123e145477cd74c0f08d54f5f1430f8a02fb124b47b6b7af21aba481fb126e4b5721b670333ad7d9f664fe5'
        '2e05cd589ad5fe269caf53e4f15585792cf0be6fdd18068609e903164d5b976eb4a9bccd789e2fbd13efa9a23fa8ddce50cde9c73bfe1a109620102379d7a7a4'
        'ed13786f49c5f7bda53e4a0abf93c8b0cc21eeb1b43509e4a91929b08fb58baaf2fc8922e0554fca4ec0642c3a0f3f08a7118d6b3f5b5064bd10251289c7f5b7'
        'ecb167e735b2eb0756fa05ff729caa8494ca1a1d886fe15402f0d2da31087a2e42ec54c1a6b18baca25c66322e5d9ee09fc65e662152604f857f3a0eea58bd83'
        'aacf8a872f49e60a7185c7a0146f61faead1c4cb4800c9b91c76d587d03474c99cff6a857d1d5db6ee6051b1c2ac4d15026667e17ecc4f210adc312efee77872'
        '5d7de181352227555695c96a2e4216460ac10f0817d0bb5a3b5f7a82cbdde74d24b188686b6f528a621eae95da81e05d71cf3d7e867c240469f43ca55369b8db'
        '523924a6aa9549689445302ed19c330e388c7ca2b6c69fbbab52a9d5d4149e52f2e068d62aabe9a6149df73eb13f99649a4986deae4a08ccb1e7cf283db7f809'
        '8e9b705959fc0b9d21b76a8d7b4aaf2294d13cf7bb84afbc8af114ef072ed4f1d592936d64afc824da3c9ff7786ef2601c8130d375ec342942adcde59e5fc85f'
        'fe126752945f617a5bfd2c849d09672eea7c48a9901aef08efa17a0136432c9c52dc9251700a226eeffcf463becd7649b550a7f388e94ba6d40de90572adca15'
        '3eb8960e6c85450515295d0adae9f0e182a0137d3801a91afffba119c6a42528187e468d85bbbb19ed6c2a8e13a3cd0b5e3e1a1b3f5c15a5973d3d6c1474a2cc'
        '62d82779ae17fdd66dda9b269b68fd3913108e13003b666d8d83904bdd0cb43d9c51541b0c8c8c44e68a9d4cf174f37904acbc42bfa69149568362fb5b5fac89'
        'f4b39e8d3c36c643ecac3286b3f1208ea6761cad29a3fa53940881dbab212b0627162ca76731b06c1a97935e0276be3e1bd9cc4c3b5dd01b7c550d6e45c4233c'
        'a47ea23e7cdff194275abdfd7e1ac4511ac4cbca79bc799af993172f0a3bb31290d185341d20b9e0335084b3cad9e5ddec48239b418c2d0122b6d9a21447acf9'
        '91e72a7e9bed260673d1f7fbeb7f7f8f80128e2acbe4b863ef22a39216d640939dac2e8353e6ec93e2bb50febfa157d4100466b148f7ffe234deb9d0b779a1ca'
        '40312bd4605b692791c1910d2126108ea84f34400131c4e03f00ae257c8d773523da493f687046d3c38a85d7231133bbb789a6f88d8f484e26d17bd5a8226307'
        'bb3f9b8d6a3916a3cb249ca5201489c1e3259fbf5f579b6a70b6f23400f45c91fc1d46cace131c4a825392f728b6ec731d5803ce8c9f36c99e1b405a77e3ff2a'
        'd6ccc4dd9c61ccb6cd6cfae8506f368a03cbdf316a3ca4d2e70d98a48b958668830bcde700edeb6e2391ded24e27ad8d32b4e83671c3e301247b9f56e6876626'
        'fb989f8ee11448944229f9268b47ac9c645191f1cf58943837b3215dd596decf989bd023d8bf7b1444f5d3be36aa58059e86e8693d192c606d6c3fe43ec47c77'
        'aa57bc6a30118876bba2d2360383e2bb13b43738dc8d87296f7cfa53df1c19c3b2348dd1a4ffb00199a8a06a0f0dbf285edd7e33edffad02e98a9f07c29fb72d'
        'eb7caf4bc1e66f0db898e56dd98926b96b7afbf5b1a561aff75f06e93bbe0ad45f169230f0938c76d9770ce82b4895295a7c47e94b1fbd1b7a70c455dbd0ad4a'
        'e165190992822c00578f44fdbd420820fbe71b9d33b8810fe5e79173fd5420ff20e5ea9734fd6ec4b0edbea09cf9b224bb6235ceddf723698cd67ceaa0474259'
        '9ac94577648ced89a8ff26e735a9ff37acdb237e65c1f04446d182de3dda91b82add7ee0d43d62011e160897addc6fb1f5ceb7f7b7e80f992341abd8504db63b'
        '01fdb146ae319d157bcf6d449e36d012ef5bd660f13f246bcb0963f0c0b3daa44aa53bce26fe58bb13ff6b2888e03f6340efc59f3b0a6ac25660398e12f5a873'
        'f81bde25bcd98914ac1f7ed02040c78836cee033d5e66c63eff310a614f42ce595e50a9f239f1b112e31271f8eeb1cbde602d501352075ee9b5121e5877c3466'
        'ce04bc2194dd2ca59bedc16047090e361d9c06a1fafc6ce47814966a6d16a70046a547505221f0507e744a669e69cef356cdf6117920a15b4821332b2a792844'
        'c4f23c2cffc1ee91985059cff9d29d27f5629ade85d8819565f1fdec0a871b345b63f517cc9521241a3006a77410dae3c9dac887a765db0b6f3a3f97ccdaadc9'
        'c8e7bf349ffb0716c5e05b52f1c5b691b41fa2dced18655f181a08e40208fe556d722d2bf9dcfefcaf70bd5ae27bcfe738af6306d86db931e2ecc2658022d1d7'
        '72879d925e2fdf60733e0e96039f0b09ee608551610f10bbccfbf68ba1dfd7364f865c001315cd09b8a1fa2dd3187b4f6ddc406c06670721a4f24b6d1e55dfef'
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
    install -Dm0644 "$srcdir/RELEASE_NOTES.md" "$pkgdir/usr/share/appinstall/RELEASE_NOTES.md"
    install -Dm0755 "$srcdir/install.sh" "$pkgdir/usr/bin/appinstall-installer"
    for helper in container_backend.py container_ui.py launch_monitor.py manager.py result_ui.py runtime_probe.py diagnostics_core.py diagnostics_ui.py url_install.py url_dialog.py; do
        install -Dm0644 "$srcdir/$helper" "$pkgdir/usr/bin/$helper"
    done
    install -Dm0644 "$srcdir/native_backend.py" "$pkgdir/usr/bin/native_backend.py"
    install -Dm0644 "$srcdir/appimage_backend.py" "$pkgdir/usr/bin/appimage_backend.py"
    install -Dm0644 "$srcdir/confirm.py" "$pkgdir/usr/bin/confirm.py"
    install -Dm0644 "$srcdir/package_meta.py" "$pkgdir/usr/bin/package_meta.py"
    install -Dm0644 "$srcdir/qt_compat.py" "$pkgdir/usr/bin/qt_compat.py"
    install -Dm0644 "$srcdir/ui_style.py" "$pkgdir/usr/bin/ui_style.py"
    install -Dm0644 "$srcdir/settings.py" "$pkgdir/usr/bin/settings.py"
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
