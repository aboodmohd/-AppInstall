#!/usr/bin/env python3
"""Per-user desktop registration with recoverable source-file updates."""
import configparser
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys

home = Path.home()
data = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
state = data / 'appinstall'
apps = data / 'applications'
service_menu = data / 'kio' / 'servicemenus' / 'io.github.aboodmohd.AppInstall.AppImageReview.desktop'
bindir = home / '.local/bin'
mime_path = config / 'mimeapps.list'
record = state / 'associations.json'
mimes = [
    'application/vnd.debian.binary-package', 'application/x-deb',
    'application/x-rpm', 'application/vnd.flatpak',
    'application/vnd.flatpak.ref', 'application/vnd.flatpak.repo',
    'application/vnd.appimage', 'application/x-iso9660-appimage',
    'application/x-quickdrop-appimage',
]
modules = (
    'integration.py', 'source_transaction.py', 'confirm.py',
    'package_meta.py', 'ui_style.py', 'qt_compat.py', 'settings.py', 'appimage_backend.py', 'appimage_updates.py',
    'native_backend.py', 'container_backend.py', 'container_ui.py',
    'launch_monitor.py', 'manager.py', 'manager_qml.py', 'result_ui.py',
    'runtime_probe.py', 'diagnostics_core.py', 'diagnostics_ui.py',
    'url_install.py', 'url_dialog.py', 'flathub_catalog.py',
    'catalog_metadata.py', 'catalog_artwork.py', 'catalog_browse.py',
    'repository_catalog.py', 'update_engine.py', 'repository_upgrades.py',
    'portable_update.py',
)
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
# Flat, makepkg-compatible source basenames; installed to hicolor destinations.
icon_sources = tuple(f'appinstall-{size}.png' for size in ICON_SIZES)
icon_destinations = tuple(
    data / 'icons' / 'hicolor' / f'{size}x{size}' / 'apps' / 'io.github.aboodmohd.AppInstall.png'
    for size in ICON_SIZES)
# QML files that manager_qml.py loads at runtime: Theme.qml, main.qml,
# AppCard.qml, and the qmldir import descriptor. manager_qml.py resolves
# QML_DIR = Path(__file__).parent / 'manager_ui', so these must land in
# $state/manager_ui/ alongside the deployed manager_qml.py.
qml_sources = ('manager_ui/qmldir', 'manager_ui/Theme.qml',
               'manager_ui/main.qml', 'manager_ui/AppCard.qml')
qml_destinations = tuple(state / s for s in qml_sources)
uninstalling = sys.argv[1:] == ['--uninstall']
root = Path(__file__).resolve().parent

if not uninstalling:
    # Check every required file before writing any user-owned location.
    required = ('appinstall', 'io.github.aboodmohd.AppInstall.desktop',
                'io.github.aboodmohd.AppInstall.AppImageReview.desktop', *modules, *icon_sources,
                *qml_sources)
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        raise SystemExit(
            'Incomplete AppInstall source directory: missing '+
            ', '.join(missing)+'. No user files were changed.'
        )

# The source installer imports from the checkout; the installed uninstall
# helper imports from the deployed user directory.
from source_transaction import SourceTransaction

destinations = [
    *(state / name for name in modules),
    *icon_destinations,
    *qml_destinations,
    bindir / 'abood-appinstall',
    bindir / 'abood-appinstall-uninstall',
    apps / 'io.github.aboodmohd.AppInstall.desktop',
    service_menu,
    record,
    mime_path,
]


def current_mode(target, default):
    return stat.S_IMODE(target.stat().st_mode) if target.is_file() else default


def quoted(p):
    # Some xdg-mime versions cannot resolve a quoted Exec even without spaces.
    if re.fullmatch(r'/[A-Za-z0-9_./-]+', str(p)):
        return str(p)
    return '"' + str(p).replace('\\', '\\\\\\\\').replace('"', '\\\\\\"').replace('`', '\\\\\\`').replace('$', '\\\\\\$').replace('%', '%%') + '"'

# Recovery and publication are serialized across two source installers.
# The metadata journal is recovered before reading MIME defaults, otherwise
# we could reuse values from a partially applied previous attempt.
with SourceTransaction(state, destinations) as transaction:
    legacy_uninstaller = bindir / 'appinstall-uninstall'
    if not uninstalling and record.is_file() and legacy_uninstaller.is_file():
        legacy_command = ('#!/bin/sh\nexec python3 ' +
                          shlex.quote(str(state / 'integration.py')) +
                          ' --uninstall\n')
        if legacy_uninstaller.read_text(encoding='utf-8', errors='replace') == legacy_command:
            raise SystemExit(
                'A legacy portable AppInstall shares this data directory. '
                'Follow the portable migration in UPGRADE.md before continuing.'
            )
    parser = configparser.RawConfigParser(
        strict=False, delimiters=('=',), interpolation=None)
    parser.optionxform = str
    if mime_path.exists():
        parser.read(mime_path)
    if not parser.has_section('Default Applications'):
        parser.add_section('Default Applications')
    defaults = parser['Default Applications']
    old = json.loads(record.read_text()) if record.exists() else {}
    changes = {}

    if uninstalling:
        import launch_monitor
        detached = launch_monitor.restore_launchers(preserve_records=True)
        if detached['skipped_modified']:
            raise SystemExit('Some managed launchers were edited; review them before uninstalling.')
        for mime, previous in old.items():
            if defaults.get(mime) == 'io.github.aboodmohd.AppInstall.desktop;':
                if previous is None:
                    defaults.pop(mime, None)
                else:
                    defaults[mime] = previous
        # Do not remove managed application records, data, or launch logs.
        if service_menu.is_file() and not service_menu.is_symlink():
            if 'X-AppInstall-Managed=true' in service_menu.read_text(
                    encoding='utf-8').splitlines():
                changes[service_menu] = None
        for target in (
            apps / 'io.github.aboodmohd.AppInstall.desktop',
            *icon_destinations,
            *qml_destinations,
            bindir / 'abood-appinstall',
            bindir / 'abood-appinstall-uninstall',
            state / 'integration.py',
            state / 'source_transaction.py',
            state / 'confirm.py',
            state / 'manager_qml.py',
            state / 'flathub_catalog.py',
            state / 'catalog_browse.py',
            state / 'portable_update.py',
            state / 'repository_catalog.py',
            record,
        ):
            changes[target] = None
    else:
        for mime in mimes:
            if mime not in old:
                old[mime] = defaults.get(mime)
            defaults[mime] = 'io.github.aboodmohd.AppInstall.desktop;'
        if service_menu.exists() and not service_menu.is_symlink():
            # Never overwrite an unrelated user's same-named service menu.
            existing = service_menu.read_text(encoding='utf-8')
            if 'X-AppInstall-Managed=true' not in existing.splitlines():
                raise SystemExit('An unrelated AppImage service menu already exists at '+
                                 str(service_menu)+'. Nothing was installed.')
        changes[record] = (json.dumps(old).encode(), 0o600)
        for name in modules:
            source = root / name
            changes[state / name] = (
                source.read_bytes(), stat.S_IMODE(source.stat().st_mode))
        app = root / 'appinstall'
        changes[bindir / 'abood-appinstall'] = (
            app.read_bytes(), stat.S_IMODE(app.stat().st_mode))
        desktop = (root / 'io.github.aboodmohd.AppInstall.desktop').read_text().replace(
            'Exec=appinstall %F',
            'Exec=' + quoted(bindir / 'abood-appinstall') + ' %F')
        changes[apps / 'io.github.aboodmohd.AppInstall.desktop'] = (desktop.encode(), 0o644)
        review_menu = (root / 'io.github.aboodmohd.AppInstall.AppImageReview.desktop').read_text().replace(
            'Exec=appinstall %f',
            'Exec=' + quoted(bindir / 'abood-appinstall') + ' %f')
        changes[service_menu] = (review_menu.encode(), 0o755)
        for size in ICON_SIZES:
            src_icon = root / f'appinstall-{size}.png'
            dst_icon = data / 'icons' / 'hicolor' / f'{size}x{size}' / 'apps' / 'io.github.aboodmohd.AppInstall.png'
            changes[dst_icon] = (src_icon.read_bytes(), 0o644)
        for src in qml_sources:
            source = root / src
            changes[state / src] = (
                source.read_bytes(), stat.S_IMODE(source.stat().st_mode))
        uninstall = (
            '#!/bin/sh\nexec python3 '+
            shlex.quote(str(state / 'integration.py'))+
            ' --uninstall\n')
        changes[bindir / 'abood-appinstall-uninstall'] = (
            uninstall.encode(), 0o755)

    with io.StringIO() as buffer:
        parser.write(buffer, space_around_delimiters=False)
        changes[mime_path] = (
            buffer.getvalue().encode(),
            current_mode(mime_path, 0o600))
    try:
        transaction.apply(changes)
    except (OSError, RuntimeError) as error:
        raise SystemExit(
            'AppInstall source registration failed: ' + str(error)
        ) from error

if not uninstalling:
    # Launcher migrations are deliberately post-commit: the source modules
    # are ready before modifying existing managed application launchers.
    sys.path.insert(0, str(state))
    import launch_monitor
    for message in launch_monitor.synchronize():
        print('Launcher migration:', message, file=sys.stderr)
    # Older versions tracked user Flatpaks through local export overrides.
    for entry in apps.glob('*.desktop'):
        try:
            meta = launch_monitor.desktop_values(entry.read_text())
            if meta.get('X-Flatpak'):
                launch_monitor.adopt_flatpak(meta['X-Flatpak'])
        except (OSError, ValueError, RuntimeError, configparser.Error):
            pass
    try:
        migration = launch_monitor.migrate_flatpak_launchers()
        for name in migration['migrated']:
            print('Flatpak launcher migrated to native export: '+name, file=sys.stderr)
        for name in migration['skipped']:
            print('Flatpak launcher review needed (left unchanged): '+name, file=sys.stderr)
    except (OSError, ValueError, RuntimeError, configparser.Error) as error:
        print('Flatpak launcher migration skipped: '+str(error), file=sys.stderr)

if shutil.which('update-desktop-database'):
    subprocess.run(['update-desktop-database', str(apps)], check=False)
print('AppInstall desktop registration updated.')
