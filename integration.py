#!/usr/bin/env python3
"""Per-user desktop registration; preserve unrelated defaults."""
import configparser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

home = Path.home()
data = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
state = data / 'appinstall'
apps = data / 'applications'
mimes = ['application/vnd.debian.binary-package', 'application/x-deb', 'application/x-rpm','application/vnd.flatpak', 'application/vnd.flatpak.ref', 'application/vnd.flatpak.repo', 'application/vnd.appimage', 'application/x-iso9660-appimage']
path = config / 'mimeapps.list'
parser = configparser.RawConfigParser(strict=False, delimiters=('=',), interpolation=None)
parser.optionxform = str
if path.exists():
    parser.read(path)
if not parser.has_section('Default Applications'):
    parser.add_section('Default Applications')
defaults = parser['Default Applications']
record = state / 'associations.json'
if sys.argv[1:] == ['--uninstall']:
    old = json.loads(record.read_text()) if record.exists() else {}
    for mime, previous in old.items():
        if defaults.get(mime) == 'appinstall.desktop;':
            if previous is None:
                defaults.pop(mime, None)
            else:
                defaults[mime] = previous
    for f in (apps / 'appinstall.desktop', home / '.local/bin/appinstall', home / '.local/bin/appinstall-uninstall', state / 'integration.py', state / 'confirm.py', record):
        f.unlink(missing_ok=True)
else:
    root = Path(__file__).resolve().parent
    state.mkdir(parents=True, exist_ok=True)
    apps.mkdir(parents=True, exist_ok=True)
    bindir = home / '.local/bin'
    bindir.mkdir(parents=True, exist_ok=True)
    old = json.loads(record.read_text()) if record.exists() else {}
    for mime in mimes:
        if mime not in old:
            old[mime] = defaults.get(mime)
        defaults[mime] = 'appinstall.desktop;'
    record.write_text(json.dumps(old))
    shutil.copy2(root / 'appinstall', bindir / 'appinstall')
    shutil.copy2(__file__, state / 'integration.py')
    shutil.copy2(root / 'confirm.py', state / 'confirm.py')
    shutil.copy2(root / 'package_meta.py', state / 'package_meta.py')
    shutil.copy2(root / 'ui_style.py', state / 'ui_style.py')
    shutil.copy2(root / 'appimage_backend.py', state / 'appimage_backend.py')
    shutil.copy2(root / 'native_backend.py', state / 'native_backend.py')
    for helper in ('container_backend.py', 'container_ui.py','launch_monitor.py','manager.py','runtime_probe.py','diagnostics_core.py','diagnostics_ui.py'):
        shutil.copy2(root / helper, state / helper)
    def quoted(p):
        return '"' + str(p).replace('\\', '\\\\\\\\').replace('"', '\\\\\\"').replace('`', '\\\\\\`').replace('$', '\\\\\\$').replace('%', '%%') + '"'
    desktop = (root / 'appinstall.desktop').read_text().replace('Exec=appinstall %F', 'Exec=' + quoted(bindir / 'appinstall') + ' %F')
    (apps / 'appinstall.desktop').write_text(desktop)
    sys.path.insert(0,str(state))
    import launch_monitor
    for message in launch_monitor.synchronize():
        print('Launcher migration:',message, file=sys.stderr)
    # Prior versions tracked user Flatpaks through a local export override.
    for entry in apps.glob('*.desktop'):
        try:
            meta=launch_monitor.desktop_values(entry.read_text())
            if meta.get('X-Flatpak') and not meta.get('X-AppInstall-LaunchID'):
                launch_monitor.adopt_flatpak(meta['X-Flatpak'])
        except (OSError,ValueError,RuntimeError,configparser.Error):
            pass
    import shlex
    uninstall = bindir / 'appinstall-uninstall'
    uninstall.write_text('#!/bin/sh\nexec python3 ' + shlex.quote(str(state / 'integration.py')) + ' --uninstall\n')
    uninstall.chmod(0o755)
config.mkdir(parents=True, exist_ok=True)
tmp = path.with_suffix('.appinstall.tmp')
with tmp.open('w') as stream:
    parser.write(stream, space_around_delimiters=False)
tmp.replace(path)
if shutil.which('update-desktop-database'):
    subprocess.run(['update-desktop-database', str(apps)], check=False)
print('AppInstall desktop registration updated.')
