# Maintainer: Abood <abood@localhost>
pkgname=appinstall
pkgver=1.1.2
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
        'dbf9f94eb6bdfd62ddd41f67118e0fa8d4d2c3adbc517d11002164d6d9611d8af36390f2c8322be97699dd4e9c08ff3ede1b6230a612ae0aab39aa602f80b9ff'
        'f8da2822ad2a5638b9f7932728727fc624fae695db8cc30470783e1f7e26e719d1fa8624e0533ebcfd1713f99935d7752d0b8b3c46d90c06f2ff034f8b307d59'
        '5a0a824810d4c4d7a8f7f2603f3c4623874eef4de55ee4b360ab0321ecfae8edf42a9443c134e10272fba0b96f89f74cd45473e6ac09c6493595c9ad0cf9c0e5'
        '0fdac362f01d045314ef86cb6bb703b9a43a99e2e1b47f35592b6ae7e8685571af567aad610c99d09f621467f98a871a5bb9102c342d535cfbd488baedc9fddd'
        'f8daf988347a97667ff112792ce0a59a8943be5bdeb7492cf4de575c32a2cb160536a0514d10375bef5929c9122e50c1cd14c8a213df125b010d49d782b4a1f3'
        '6617a84f3fc0c8c8006e9718619ff97d3ab11a706248277a87754e006177fe36cc72c34a43ec74c38ff3cca98293544189a2ec68b7babc2ce09a94efd8983fb3'
        '9acc9b0cb15dd2082ba078cf1240995d443bdf974d0fc37719cb42e982379343e38a7d35a397fb87a17d82f76b29cc4bdaac0c9902c9387126f99e52d5ee47c9'
        'fb79957f8c55268b58cad39efe05173bd614f801c3af5b0fc21aab74eb4e07ba30630dcdcd56524cc1c69a8dc30808490e3e196136cb798457d734934afaae09'
        '523924a6aa9549689445302ed19c330e388c7ca2b6c69fbbab52a9d5d4149e52f2e068d62aabe9a6149df73eb13f99649a4986deae4a08ccb1e7cf283db7f809'
        '8e9b705959fc0b9d21b76a8d7b4aaf2294d13cf7bb84afbc8af114ef072ed4f1d592936d64afc824da3c9ff7786ef2601c8130d375ec342942adcde59e5fc85f'
        'a70357db526a6c879c8e9edeaa2385df81ade78783c48a4f802b4d7322953b82472c3781b7a42ad266f3b81dcfff45cd412282a05d352fdf5d8a476f6ee627ce'
        '89d058b8c9f63c621c36541db36b0884ebb716fddf40b45b26458617b30076574de86960a94f0e5f245b091fa8379930fdec44b2bc3e1f28bcbd502236087bf1'
        'dab8c43824311c61ceeca64459165a91c712ba2f5a4773862e094f23956ea6c0dc3e2b7c210076ac4e734ee20f465c56fd605e2c58235fb25d84757825efecc6'
        'f4b39e8d3c36c643ecac3286b3f1208ea6761cad29a3fa53940881dbab212b0627162ca76731b06c1a97935e0276be3e1bd9cc4c3b5dd01b7c550d6e45c4233c'
        'e59b0098ba2649a51335eb89784c69bacb64089a6932cbb692d5c6f74d8f38a590cf3682e858c60c724bcaf7802f83ade8f758f922cbd3a80fcb2615190f6348'
        '91e6f4fc34630a9ccdf025133803de3c012d4ee308c2fe9f5721c0076dff0cda34f615580a35b23b0c6e717922e557ccdcd2049d06c24333dfbf22d91206df3d'
        'de544413350b39576175dc492836688e7324c27847deeba630d8fabc870c75983cf6902cda2784823d7111032bee8403d6892d86a7055f0b0665117eee93ae4f'
        '6cb1f35c13abff0d7f27be11b05dcb927e030fa03548ebdf69302dbdda1ec92990ee77658ac5ae43a9e012fcfee97e5c86c264910cf52498629ed4a2ea4e3bac'
        'b7df93a6675e3d6c6fccc7691e0e7ef5d1ab96a60f1f1650d10a15afc5621b97b339d2590fc83521c18ef79e0d5e3b46eb5a093b40a9313432fa90aeff650ca7'
        'fb989f8ee11448944229f9268b47ac9c645191f1cf58943837b3215dd596decf989bd023d8bf7b1444f5d3be36aa58059e86e8693d192c606d6c3fe43ec47c77'
        'aa57bc6a30118876bba2d2360383e2bb13b43738dc8d87296f7cfa53df1c19c3b2348dd1a4ffb00199a8a06a0f0dbf285edd7e33edffad02e98a9f07c29fb72d'
        'eb7caf4bc1e66f0db898e56dd98926b96b7afbf5b1a561aff75f06e93bbe0ad45f169230f0938c76d9770ce82b4895295a7c47e94b1fbd1b7a70c455dbd0ad4a'
        'ecd34432755121545f384aa50f2a5608b79e35e76ea7151ba06cb3204119329e3916d68f97a87508caf5ee8df0348f0d5797e7ea89b1e8caee030f0246954de8'
        'e135df0e133bbe63eb498fc125ece4811cf87a90d8bb74186f6fe15bf3f5afbb3424930a7f0772099e73589eb636b810672e1e1a087632660ec26dc4542c0c91'
        '7a722ebc57813bf053afb04a3a13bd4ce05a85f00c63c95c53296235bdba5ac0603db8fbdcd97dd500fd8315887bbbd09762c0e8366c27f888bed899046d8887'
        'f81bde25bcd98914ac1f7ed02040c78836cee033d5e66c63eff310a614f42ce595e50a9f239f1b112e31271f8eeb1cbde602d501352075ee9b5121e5877c3466'
        'ce04bc2194dd2ca59bedc16047090e361d9c06a1fafc6ce47814966a6d16a70046a547505221f0507e744a669e69cef356cdf6117920a15b4821332b2a792844'
        'c4f23c2cffc1ee91985059cff9d29d27f5629ade85d8819565f1fdec0a871b345b63f517cc9521241a3006a77410dae3c9dac887a765db0b6f3a3f97ccdaadc9'
        'c8e7bf349ffb0716c5e05b52f1c5b691b41fa2dced18655f181a08e40208fe556d722d2bf9dcfefcaf70bd5ae27bcfe738af6306d86db931e2ecc2658022d1d7'
        '568c16b23b516af097bf1e3686a7a11512963d9de4921cfa7f205fce913ec68fb531f502a3eb30065763fd488415beb99ff44f8c53f0e6f81099d0e33daeac84'
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
