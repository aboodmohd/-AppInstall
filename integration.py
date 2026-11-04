#!/usr/bin/env python3
"""Per-user desktop registration with recoverable source-file updates."""
import configparser
import io
import json
import os
from pathlib import Path
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
bindir = home / '.local/bin'
mime_path = config / 'mimeapps.list'
record = state / 'associations.json'
mimes = [
    'application/vnd.debian.binary-package', 'application/x-deb',
    'application/x-rpm', 'application/vnd.flatpak',
    'application/vnd.flatpak.ref', 'application/vnd.flatpak.repo',
    'application/vnd.appimage', 'application/x-iso9660-appimage',
]
modules = (
    'integration.py', 'source_transaction.py', 'confirm.py',
    'package_meta.py', 'ui_style.py', 'appimage_backend.py',
    'native_backend.py', 'container_backend.py', 'container_ui.py',
    'launch_monitor.py', 'manager.py', 'result_ui.py',
    'runtime_probe.py', 'diagnostics_core.py', 'diagnostics_ui.py',
)
uninstalling = sys.argv[1:] == ['--uninstall']
root = Path(__file__).resolve().parent

if not uninstalling:
    # Check every required file before writing any user-owned location.
    required = ('appinstall', 'appinstall.desktop', *modules)
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
    bindir / 'appinstall',
    bindir / 'appinstall-uninstall',
    apps / 'appinstall.desktop',
    record,
    mime_path,
]


def current_mode(target, default):
    return stat.S_IMODE(target.stat().st_mode) if target.is_file() else default


def quoted(p):
    return '"' + str(p).replace('\\', '\\\\\\\\').replace('"', '\\\\\\"').replace('`', '\\\\\\`').replace('$', '\\\\\\$').replace('%', '%%') + '"'

# Recovery and publication are serialized across two source installers.
# The metadata journal is recovered before reading MIME defaults, otherwise
# we could reuse values from a partially applied previous attempt.
with SourceTransaction(state, destinations) as transaction:
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
        for mime, previous in old.items():
            if defaults.get(mime) == 'appinstall.desktop;':
                if previous is None:
                    defaults.pop(mime, None)
                else:
                    defaults[mime] = previous
        # Do not remove managed application records, data, or launch logs.
        for target in (
            apps / 'appinstall.desktop',
            bindir / 'appinstall',
            bindir / 'appinstall-uninstall',
            state / 'integration.py',
            state / 'source_transaction.py',
            state / 'confirm.py',
            record,
        ):
            changes[target] = None
    else:
        for mime in mimes:
            if mime not in old:
                old[mime] = defaults.get(mime)
            defaults[mime] = 'appinstall.desktop;'
        changes[record] = (json.dumps(old).encode(), 0o600)
        for name in modules:
            source = root / name
            changes[state / name] = (
                source.read_bytes(), stat.S_IMODE(source.stat().st_mode))
        app = root / 'appinstall'
        changes[bindir / 'appinstall'] = (
            app.read_bytes(), stat.S_IMODE(app.stat().st_mode))
        desktop = (root / 'appinstall.desktop').read_text().replace(
            'Exec=appinstall %F',
            'Exec=' + quoted(bindir / 'appinstall') + ' %F')
        changes[apps / 'appinstall.desktop'] = (desktop.encode(), 0o644)
        uninstall = (
            '#!/bin/sh\nexec python3 '+
            shlex.quote(str(state / 'integration.py'))+
            ' --uninstall\n')
        changes[bindir / 'appinstall-uninstall'] = (
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
            if meta.get('X-Flatpak') and not meta.get('X-AppInstall-LaunchID'):
                launch_monitor.adopt_flatpak(meta['X-Flatpak'])
        except (OSError, ValueError, RuntimeError, configparser.Error):
            pass

if shutil.which('update-desktop-database'):
    subprocess.run(['update-desktop-database', str(apps)], check=False)
print('AppInstall desktop registration updated.')
