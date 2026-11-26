# Maintainer: Abood <abood@localhost>
pkgname=abood-appinstall
pkgver=1.9.5
pkgrel=1
pkgdesc="Double-click installer for AppImage, Flatpak, DEB, and RPM files on Linux desktops"
arch=('any')
install=appinstall.install
url="https://github.com/aboodmohd/-AppInstall"
license=('MIT')
depends=('bash' 'coreutils' 'xdg-utils' 'python' 'pyside6' 'curl'
         'qt6-declarative')
optdepends=('polkit: graphical update authentication' 'flatpak: Flatpak installation' 'kdialog: KDE dialogs' 'zenity: GNOME and Xfce dialogs' 'libnotify: notifications' 'fuse2: AppImage mounting' 'squashfs-tools: passive AppImage preview' 'podman: rootless DEB/RPM containers' 'distrobox: DEB/RPM integration' 'libarchive: package inspection' 'binutils: optional static ELF dependency checks')
backup=()

source=('install.sh'
        'appinstall'
        'io.github.aboodmohd.AppInstall.desktop'
        'io.github.aboodmohd.AppInstall.AppImageReview.desktop'
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
        'install_mode.py'
        'appinstall.install'
        'qt_compat.py'
        'ui_style.py'
        'settings.py'
        'appimage_backend.py'
        'appimage_updates.py'
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
        'catalog_metadata.py'
        'catalog_artwork.py'
        'catalog_browse.py'
        'repository_catalog.py'
        'update_engine.py'
        'repository_upgrades.py'
        'portable_update.py'
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
        'f33842fffe1b6d1ecc996304e5ea3eba5d4bc52157b81747b8c8a9664953c9c3437f798b401cf5d6643b4b97d2395b801a67792420467fba33b4fdbf5bab5cb2'
        '16fe8e22a871881e917f1994cd45462bb6a27289314dd2285cf1e9f723fe1abdbe95e3f842b38bb12940ef29536c028158c90e00046a896975120c4f4d08fd1c'
        'e9c70963450a6d407b94498d3f13afe5bacd0e15631f43a4eb6131636b077cd90e3d9b1055817b24d5143a40864fde7a5d3d0f64e5203e8851a047854fda1d4c'
        'fc142c2b03f263a36ab1d024beaecebccf29af32e15f7ec78b27b21ccdc81675a812b54dba6015601c6b4d57fb4ba00a54f19f5bad4a97e864b4e450a06375a4'
        'fd08e33dc161ee0d125c83354a59e84586081f21274a4a49f683c474864952b26da8f4671e45b665d267dc41bb4826dbf4a765b2ac1531d304816a8b719a571f'
        'b618fc32fe9f62b3e256287d038bb22885042211d4337ed78efe1faba920e3ba6deceb4b8e21a22d430a0e24a347e50cbde99c796633a61dc1813517a4ef0b82'
        '61e1ba4be6bbb44d28d29fa1253bfaddf36f096e9a0b29a4c684c3fba7cae5613b119d4c0ffbef8c21d8a41b46b217a239ee45e454d4a8d1bd0e99d61a63da61'
        '45989cba16c5c75e2350ec185e4a0e86ed4f7646e8a612f6e1d1ef15c9a46a7048e1f47508440f549a2c1f154cdee45d30664de5a92acadae724e58995f0fa32'
        'fc297826f880bcbf84243020009d5b8bdd224d1cd6a6cd4ad15c4124738211fe24a35020f366204b2575f7b758d6ca09e5a4dc99b0739432a94f397dc9c28fe7'
        '6c28640acd705f0b4297f53d057ccae7646b1bcc4cf12d1984590f9f9dd99a3a2462a3604d70dc3c58a8e06997ad4a903a59fdb1c66acc2a3b0a265756dbbf8c'
        '1e64cd014a7212a9d5e8b9311852193789b20dbafb6cb7558a0e40149e048e202194e0c1bc359758efeb06a9f656fa0a5946743bd1fc6272effe961577eaea27'
        '4335b56f8ab40656a9eb98e55fc17d74b683dda0ceff0b815dc7e3c8b33cb2219b52ff60ac1a4350c2b7d2520a794815a4f7a1b6b17a3300a6b289e7da9383be'
        'ed13786f49c5f7bda53e4a0abf93c8b0cc21eeb1b43509e4a91929b08fb58baaf2fc8922e0554fca4ec0642c3a0f3f08a7118d6b3f5b5064bd10251289c7f5b7'
        '699ba0b8a398fcd4a88cfd02e36a0e79fc6c92d9160b88ce80ff7ce76d3420f3a3686b8d7bd12589e02b39c652e28d566d95f2718ea3c04314c09719dddb7e5f'
        '0dc54bce4b0c6517693bba7274e4770fb19e61d4fc361d3405087212220ff3a376ba7ec4038635d0e432656c6d715ecb8210d8b853d58eed2aa8d3dcaf608dfe'
        'ecb167e735b2eb0756fa05ff729caa8494ca1a1d886fe15402f0d2da31087a2e42ec54c1a6b18baca25c66322e5d9ee09fc65e662152604f857f3a0eea58bd83'
        '70860dff7f45ec53052553484d0ef0f1a9265fefb6a4fa925db78cec603a6b21ae45932302d59135b6c7d91a7c0cea282a607060aa286993d970a747bcc5863d'
        '95dee6e7a69029c69fbd7136f3f650141380b84c4b8dc18bde982e0804e467186af82ee2dc20057acbf55f7086745df3e1927e1b75a6a701c1e762be780237c2'
        '2965a233482c23409caea706370dbcb2623f1ad7fcb4e3cc371a1c6de977d4d43889d98c918a58e3bc53208f1091ea656bd9451caf300a1b99b8f36cabe2e1a6'
        'e4c07e449b37899e8640f62605cb2f768f81d24dcc1517de2be3c2e1320d9ca5269d596c98daeb37287642f39c9e9d2c2ead798f605330b569b20cc5d29bde04'
        '8e9b705959fc0b9d21b76a8d7b4aaf2294d13cf7bb84afbc8af114ef072ed4f1d592936d64afc824da3c9ff7786ef2601c8130d375ec342942adcde59e5fc85f'
        '381f4fd13b9c76316dfba7f45f47e4cc26aeba5212628398b7b03b4a3cfefb21b1c85e167e8804e5d1893c9df1f70d817620a6f697a674df5d38ac1757960fd5'
        'd5d0a4657227c2031f5584be1e8e46e51d55be7b03254db8e4c981478fd7bfd84e378c7050e7382632800d1e1767eadf71a409f0e26e66c144876e9bd87a4811'
        '55460a30d411c75861ecc20895a87f9f4f31202343347da30190f2738294cf989dcd6ec529712aa3d48d6e9082affdefcac3d5d479572edcdaba066ea29dca1c'
        'f4b39e8d3c36c643ecac3286b3f1208ea6761cad29a3fa53940881dbab212b0627162ca76731b06c1a97935e0276be3e1bd9cc4c3b5dd01b7c550d6e45c4233c'
        'a2af8af058c82f05ed82fe2bb76740edb19f54c058ad47036ad9025b68474cd2025a8faaaa72653848025f4f0c75c5eca9d8ba649dad9591fe73fbd7df28503b'
        '62c79aced81fd4014de22694c96c021694c293731cb6c7766f1d1bb6412ceb43fc48556f2f2dea2db621d8f1ef64894441fd46354912b7269ce04c2b749acc78'
        'de38a99107a00612b9628dbdf83bd1a1807ae541b6b52e023b3b0495f0eddf7e6245c5dc4155486758df787690adc0ff55e9ce94a3d380a5f32da1f2b48525bb'
        '68abf6af5dd5f7d5633d2a255e07803344d390b04c4192137e2fa79640acb70a93d6004389b2a858c28d0bcb0d402adf5029e2676d67b78bb934871d83f29f1e'
        '2dc7bd3fadb20d198c508e62aa37788488c2e2691d419daf729a77078963fb337dfee91981401b136045428503670159a7601097ac2c8c3247d067149935b8e4'
        '7ff2586c88a8cf9c3819fce91e1068ef8c409108b9b3ae859d1518e720863a6090b7973cec2c1606dac288421e30375390034f490d66478ab669c2dafcf6a568'
        'da55cae1a112f5b2b53e3ecf3feb24079bac8c0acecc8d9895c2361d8dfac4d2d7d9bf3008e2c11327fc91eedb7529ece66e0548f53f101976cd22cc7423826e'
        '35d905cfe9945674c4337808552eccdd9936d7ce56d90c41f5639dbc32856049e024e8aa3ecb31814c946d54f618a9bd35163e77803ca7fcf90aa448bd10102d'
        '0e2d5052d3db14a91f92af09defd75206a2a247697377e6ea0a002ffe559924abc953bb6335b9641c527576222a3b6cad8599cad2bade9636ab061cb3adfaf14'
        '2ab859878824a1bbae2fe0c1616e20f8b65461e4eb5c931a6ccc31691d489a346244f7e1cc99fb5108c048d8d097cdb077e6fb9f018f7d4e941ef1755929b434'
        '53f5d4bd0510d6d52ecca621e30e57b382e566521b8084446faf9c0b34925353c806d32de96b1302616231d906c9bf58340e871c427c99b546747dea50e0c83f'
        '3ced14ded4482e77cf482362cb2f3c5bf7a9d6ac994e03de910a12c3d94e4d5e53fe6e695c0c2122cab6c50c76aa63a80293fafeb94e08b79912c1e34f2a5d88'
        '1787dc142bcc13184723ff89a50e37ac43910b7e8b12fe687ae2a2c714ac9bd43b90bc8dec1e118ce39bff1b3571177128fa77f5b7ecbc04baddbc21d4a22bf9'
        'fb989f8ee11448944229f9268b47ac9c645191f1cf58943837b3215dd596decf989bd023d8bf7b1444f5d3be36aa58059e86e8693d192c606d6c3fe43ec47c77'
        'aa57bc6a30118876bba2d2360383e2bb13b43738dc8d87296f7cfa53df1c19c3b2348dd1a4ffb00199a8a06a0f0dbf285edd7e33edffad02e98a9f07c29fb72d'
        'eb7caf4bc1e66f0db898e56dd98926b96b7afbf5b1a561aff75f06e93bbe0ad45f169230f0938c76d9770ce82b4895295a7c47e94b1fbd1b7a70c455dbd0ad4a'
        '36e8f214f40f58e0c821ff5e155b7941ae3be5a81df1939d1f5231f47bc3a9ccc3706ef7d58ac3c769fed4b9436b3d3cc6226c95453e339b69efa73568de614b'
        '8e2e90a351fd7e071f4357e90885a28d8a8a1556dbe0a34085ebfa16193eb28faa4c6f47502ca476f54209f1c0ea25e8017bae1d014fc9c57fd7d86daa71c328'
        '92de4ed2ba292b90939ba481c6543e10115ae39bebadd4598469b87b4cee9467f6f6d6f8027817f332689a70e274d0f0c29e2f0b11adf6b90dde8b9bca6b9308'
        '02503499e903094c7914562a65ffb54cde94314ea5a9f3bad15915a225c67595976492364affef842211fa09c54aa79b245fafea0a278c316746eacc69f7e166'
        '67c9854c3ac526386d32a47382ea6092469c29ae56921fd939035e06bd3a2db4060ab6e0d7a0066b75211a97846b1e7f938031f1e17e2703b258d7f89346a24b'
        '0d31afab667717c0a490af8da91675455a5178c6607c5aa3953b9bec0c6a7adb915f028da0793a155f1f3443ad528a22c8558dd72c763c788764728e7131aab6'
        'c8e7bf349ffb0716c5e05b52f1c5b691b41fa2dced18655f181a08e40208fe556d722d2bf9dcfefcaf70bd5ae27bcfe738af6306d86db931e2ecc2658022d1d7'
        'e82094a1cfb1da28a09ee04e0b7b9d77fd965dc5a97b7074b965d5c018f781a8030bfaf421277550b871d15f058693c2c75bc20f8f4411a87396f63659ea7cc4'
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
    install -Dm0644 "$srcdir/RELEASE_NOTES.md" "$pkgdir/usr/share/abood-appinstall/RELEASE_NOTES.md"
    install -Dm0755 "$srcdir/install.sh" "$pkgdir/usr/lib/$pkgname/appinstall-installer"
    for helper in container_backend.py container_ui.py launch_monitor.py manager.py manager_qml.py result_ui.py runtime_probe.py diagnostics_core.py diagnostics_ui.py url_install.py url_dialog.py flathub_catalog.py catalog_metadata.py catalog_artwork.py catalog_browse.py repository_catalog.py update_engine.py repository_upgrades.py portable_update.py; do
        install -Dm0644 "$srcdir/$helper" "$pkgdir/usr/lib/$pkgname/$helper"
    done
    # QML prototype of the My Applications screen (manager_qml.py loads it
    # from the directory next to the other helpers).
    install -Dm0644 "$srcdir/manager-ui-qmldir" "$pkgdir/usr/lib/$pkgname/manager_ui/qmldir"
    install -Dm0644 "$srcdir/manager-ui-Theme.qml" "$pkgdir/usr/lib/$pkgname/manager_ui/Theme.qml"
    install -Dm0644 "$srcdir/manager-ui-main.qml" "$pkgdir/usr/lib/$pkgname/manager_ui/main.qml"
    install -Dm0644 "$srcdir/manager-ui-AppCard.qml" "$pkgdir/usr/lib/$pkgname/manager_ui/AppCard.qml"
    install -Dm0644 "$srcdir/native_backend.py" "$pkgdir/usr/lib/$pkgname/native_backend.py"
    install -Dm0644 "$srcdir/appimage_backend.py" "$pkgdir/usr/lib/$pkgname/appimage_backend.py"
    install -Dm0644 "$srcdir/appimage_updates.py" "$pkgdir/usr/lib/$pkgname/appimage_updates.py"
    install -Dm0644 "$srcdir/confirm.py" "$pkgdir/usr/lib/$pkgname/confirm.py"
    install -Dm0644 "$srcdir/package_meta.py" "$pkgdir/usr/lib/$pkgname/package_meta.py"
    install -Dm0644 "$srcdir/install_mode.py" "$pkgdir/usr/lib/$pkgname/install_mode.py"
    install -Dm0644 "$srcdir/qt_compat.py" "$pkgdir/usr/lib/$pkgname/qt_compat.py"
    install -Dm0644 "$srcdir/ui_style.py" "$pkgdir/usr/lib/$pkgname/ui_style.py"
    install -Dm0644 "$srcdir/settings.py" "$pkgdir/usr/lib/$pkgname/settings.py"
    install -Dm0755 "$srcdir/appinstall" \
        "$pkgdir/usr/lib/$pkgname/appinstall"
    install -d "$pkgdir/usr/bin"
    ln -s "../lib/$pkgname/appinstall" "$pkgdir/usr/bin/$pkgname"
    install -Dm0644 "$srcdir/io.github.aboodmohd.AppInstall.desktop" \
        "$pkgdir/usr/share/applications/io.github.aboodmohd.AppInstall.desktop"
    # Pin the system launcher to the pacman-owned executable. A separate
    # source/user install may place an older appinstall first in PATH.
    # integration.py still rewrites its user-level launcher independently.
    sed -i 's|^Exec=appinstall %F$|Exec=/usr/bin/abood-appinstall %F|' \
        "$pkgdir/usr/share/applications/io.github.aboodmohd.AppInstall.desktop"
    install -Dm0755 "$srcdir/io.github.aboodmohd.AppInstall.AppImageReview.desktop" \
        "$pkgdir/usr/share/kio/servicemenus/io.github.aboodmohd.AppInstall.AppImageReview.desktop"
    # Use the pacman-owned executable even when ~/.local/bin/abood-appinstall
    # from a source/beta installation appears first in PATH.
    # The source installer rewrites its own menu to the user-local path.
    sed -i 's|^Exec=appinstall %f$|Exec=/usr/bin/abood-appinstall %f|' \
        "$pkgdir/usr/share/kio/servicemenus/io.github.aboodmohd.AppInstall.AppImageReview.desktop"
    # Application icon: install the official AppInstall logo to the freedesktop
    # hicolor theme at every supported size, keeping the installed name
    # io.github.aboodmohd.AppInstall.png in each size directory.
    for size in 16 24 32 48 64 128 256 512; do
        install -Dm0644 "$srcdir/appinstall-${size}.png" \
            "$pkgdir/usr/share/icons/hicolor/${size}x${size}/apps/io.github.aboodmohd.AppInstall.png"
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
