# Maintainer: Abood <abood@localhost>
pkgname=appinstall
pkgver=1.6.0
pkgrel=1
pkgdesc="Double-click installer for AppImage, Flatpak, DEB, and RPM files on Linux desktops"
arch=('any')
url="https://github.com/aboodmohd/-AppInstall"
license=('MIT')
depends=('bash' 'coreutils' 'xdg-utils' 'python' 'pyside6' 'curl'
         'qt6-declarative')
optdepends=('polkit: graphical update authentication' 'flatpak: Flatpak installation' 'kdialog: KDE dialogs' 'zenity: GNOME and Xfce dialogs' 'libnotify: notifications' 'fuse2: AppImage mounting' 'squashfs-tools: passive AppImage preview' 'podman: rootless DEB/RPM containers' 'distrobox: DEB/RPM integration' 'libarchive: package inspection' 'binutils: optional static ELF dependency checks')
backup=()

source=('install.sh'
        'appinstall'
        'appinstall.desktop'
        'appinstall-appimage-review.desktop'
        'confirm.py'
        'manager.py'
        'manager_qml.py'
        # QML prototype files. Like the icon sources above, the repo keeps
        # them under manager_ui/ and exposes them through distinct root-level
        # symlinks, because makepkg resolves every local source by its
        # basename at $startdir/ and cannot read subdirectory sources.
        'manager-ui-qmldir'
        'manager-ui-Theme.qml'
        'manager-ui-main.qml'
        'manager-ui-AppCard.qml'
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
        'flathub_catalog.py'
        'repository_catalog.py'
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
        '42fa4543364434f2ef443d93bd14bb814720d29f0cf570bd0c2f6fb3a817ceed61a4822e1cdc1cc1b565d429b11f394172dd8fa9a4ee3c17aba3a248c8887846'
        '2462afcd3863e1a3400ecd043f9f3814b5a6a895a992e2e971212f2a7e10591995fd347a6115669ae01bd824c93f4ab529f2bce20030796467ba9ec44ac95665'
        'f8da2822ad2a5638b9f7932728727fc624fae695db8cc30470783e1f7e26e719d1fa8624e0533ebcfd1713f99935d7752d0b8b3c46d90c06f2ff034f8b307d59'
        '5a0a824810d4c4d7a8f7f2603f3c4623874eef4de55ee4b360ab0321ecfae8edf42a9443c134e10272fba0b96f89f74cd45473e6ac09c6493595c9ad0cf9c0e5'
        'aa2943ff6d844443cb68654103a1aadadea9c3b000dffe66ef0601999f12e9a6e5cd3b8ab0b7aa7f5c60bebb1fe872ff51aebec12722cce31f98b04194b39cc8'
        '880d7fb3cd0ee1874d4412f6ab67a71eb4ba76e5ee06f7798bffd59e32ee2cf995a729816bc901524015cdd85c94a49aad0957fc52d9d494b6a66512527df3f5'
        'f47afa777c06db65a90aa42ca532bb2962aa7c2c223a0a6420708fcd1e819963ca02c5e160d4f95d3d250dd4d12b94e84a094f01e60203e7f5bbf74266d71e18'
        '45989cba16c5c75e2350ec185e4a0e86ed4f7646e8a612f6e1d1ef15c9a46a7048e1f47508440f549a2c1f154cdee45d30664de5a92acadae724e58995f0fa32'
        'ea7ad2d2634286fb2928065cab2a0f0368f0b420e09d57162e566ace57e2cdab67aff884b7a11daa65374ecd4a3b77fd0ef7c7acad4482384a35db38023521b1'
        '9c1cad3b2f9d6a1e0eb8bb66bfd993c855e5cb35711813b389f51b9e8171ce3b83b3b7fdc8e159ba4f5a23aebf6fdba83a4410461bb204e06cfd446cd508b56c'
        'b0c5aa25b5905576b011ead071718296a49d903b764483f764e636a4bd530a3206a3b72205d0c7be66aff71c58df2c950c0be314f9f13fcd2bd208510686942c'
        '2e05cd589ad5fe269caf53e4f15585792cf0be6fdd18068609e903164d5b976eb4a9bccd789e2fbd13efa9a23fa8ddce50cde9c73bfe1a109620102379d7a7a4'
        'ed13786f49c5f7bda53e4a0abf93c8b0cc21eeb1b43509e4a91929b08fb58baaf2fc8922e0554fca4ec0642c3a0f3f08a7118d6b3f5b5064bd10251289c7f5b7'
        'ecb167e735b2eb0756fa05ff729caa8494ca1a1d886fe15402f0d2da31087a2e42ec54c1a6b18baca25c66322e5d9ee09fc65e662152604f857f3a0eea58bd83'
        'aacf8a872f49e60a7185c7a0146f61faead1c4cb4800c9b91c76d587d03474c99cff6a857d1d5db6ee6051b1c2ac4d15026667e17ecc4f210adc312efee77872'
        '95dee6e7a69029c69fbd7136f3f650141380b84c4b8dc18bde982e0804e467186af82ee2dc20057acbf55f7086745df3e1927e1b75a6a701c1e762be780237c2'
        '523924a6aa9549689445302ed19c330e388c7ca2b6c69fbbab52a9d5d4149e52f2e068d62aabe9a6149df73eb13f99649a4986deae4a08ccb1e7cf283db7f809'
        '8e9b705959fc0b9d21b76a8d7b4aaf2294d13cf7bb84afbc8af114ef072ed4f1d592936d64afc824da3c9ff7786ef2601c8130d375ec342942adcde59e5fc85f'
        '7e72193ab6a02e984acc220370c8281bf9c949aaf497655bca8a2fe29cd865e817d95614413ed2a80e826fe1dc681eb9cf1029914d762b569d782f185de4804a'
        'b3a22465dffbaa5e03515a9408d0e03580fb8cd3e8b1e93a0030e7f8189c4f113b6b66b4c2c971481fa1b4727f2e9ec51ca8aed3852d5c22f3ce773a59c04206'
        '62d82779ae17fdd66dda9b269b68fd3913108e13003b666d8d83904bdd0cb43d9c51541b0c8c8c44e68a9d4cf174f37904acbc42bfa69149568362fb5b5fac89'
        'f4b39e8d3c36c643ecac3286b3f1208ea6761cad29a3fa53940881dbab212b0627162ca76731b06c1a97935e0276be3e1bd9cc4c3b5dd01b7c550d6e45c4233c'
        'a2af8af058c82f05ed82fe2bb76740edb19f54c058ad47036ad9025b68474cd2025a8faaaa72653848025f4f0c75c5eca9d8ba649dad9591fe73fbd7df28503b'
        '91e72a7e9bed260673d1f7fbeb7f7f8f80128e2acbe4b863ef22a39216d640939dac2e8353e6ec93e2bb50febfa157d4100466b148f7ffe234deb9d0b779a1ca'
        '40312bd4605b692791c1910d2126108ea84f34400131c4e03f00ae257c8d773523da493f687046d3c38a85d7231133bbb789a6f88d8f484e26d17bd5a8226307'
        'bb3f9b8d6a3916a3cb249ca5201489c1e3259fbf5f579b6a70b6f23400f45c91fc1d46cace131c4a825392f728b6ec731d5803ce8c9f36c99e1b405a77e3ff2a'
        '3058a18e869be5c0216601645e349f656a60da2af0cd4bc6d03e05bc208aa418c7f1b2b1ab03d04a4fc4948ded1b12724313772b27c70b49cf4397f81bf1e228'
        'b47672eb446cd89e0913637a2513230e64fced09e97b8092c5d6239294dc70601b49eb685610f98ee27f282d7ffb37fc2754c49577fd6fccc2cc4fdb177ed94c'
        '7ea5e55ffb3edf44f94a4c9d317dd12245b1b325d4d37fdb245eeeec30f99dad13ac70776b754d37b9b2587578c8ff795462c5c261785907e44de6d051ebdea4'
        'fb989f8ee11448944229f9268b47ac9c645191f1cf58943837b3215dd596decf989bd023d8bf7b1444f5d3be36aa58059e86e8693d192c606d6c3fe43ec47c77'
        'aa57bc6a30118876bba2d2360383e2bb13b43738dc8d87296f7cfa53df1c19c3b2348dd1a4ffb00199a8a06a0f0dbf285edd7e33edffad02e98a9f07c29fb72d'
        'eb7caf4bc1e66f0db898e56dd98926b96b7afbf5b1a561aff75f06e93bbe0ad45f169230f0938c76d9770ce82b4895295a7c47e94b1fbd1b7a70c455dbd0ad4a'
        '788c370f19ee61f04e35e24676739687fdfdbb506b6b3c4c6bb1f637bf1844ac99204ba0c6dc2750dbafa8e3eb10a06389e861d6afbff0899e9b99e7f858cb98'
        '23327a1be71cc05748ab98189006e9ce5f597ca25ba4abcd1d3eafe523080ce6c53b9dec2af4e4a1767e8df0e380386e4f2681f30161eb05083ae04566fecd87'
        'ec19c7e5f9e176885fab0cb0de2ea34b477af2228a7cdd71825014d24bed8cb2e6eb208c5ca677fc16618649c90cd94ea8bc32a64c8939dad7f12f1f625e3f1a'
        'f7879680815d68cca33767982b8ee8ba6d1e9122d220ff15d4f6f57356272f6d70fa2ebd34111fa17f82ac36c1059a11cfca7fb1c5c96f1f7e5f515e727307a7'
        '67c9854c3ac526386d32a47382ea6092469c29ae56921fd939035e06bd3a2db4060ab6e0d7a0066b75211a97846b1e7f938031f1e17e2703b258d7f89346a24b'
        'c4f23c2cffc1ee91985059cff9d29d27f5629ade85d8819565f1fdec0a871b345b63f517cc9521241a3006a77410dae3c9dac887a765db0b6f3a3f97ccdaadc9'
        'c8e7bf349ffb0716c5e05b52f1c5b691b41fa2dced18655f181a08e40208fe556d722d2bf9dcfefcaf70bd5ae27bcfe738af6306d86db931e2ecc2658022d1d7'
        '3c6861246c6d00c874019b00edc3e218e1dd41b71de8a6bcff3a3ac1a387cbe19cb84d1ea4c2fa71c675d9f374b7c00fd8bb347ec27f512ea65bda17baae645e'
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
    for helper in container_backend.py container_ui.py launch_monitor.py manager.py manager_qml.py result_ui.py runtime_probe.py diagnostics_core.py diagnostics_ui.py url_install.py url_dialog.py flathub_catalog.py repository_catalog.py; do
        install -Dm0644 "$srcdir/$helper" "$pkgdir/usr/bin/$helper"
    done
    # QML prototype of the My Applications screen (manager_qml.py loads it
    # from the directory next to the other helpers).
    install -Dm0644 "$srcdir/manager-ui-qmldir" "$pkgdir/usr/bin/manager_ui/qmldir"
    install -Dm0644 "$srcdir/manager-ui-Theme.qml" "$pkgdir/usr/bin/manager_ui/Theme.qml"
    install -Dm0644 "$srcdir/manager-ui-main.qml" "$pkgdir/usr/bin/manager_ui/main.qml"
    install -Dm0644 "$srcdir/manager-ui-AppCard.qml" "$pkgdir/usr/bin/manager_ui/AppCard.qml"
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
