#!/usr/bin/env python3
"""Detect AppInstall's installation mode and repair stale desktop entries.

Read-only by default. The only mutation is an explicit desktop-entry repair,
which rewrites the Exec line of an AppInstall entry whose launcher is missing
or points outside the verified native installation.
"""
import os
from pathlib import Path
import subprocess
import sys

PACKAGE = 'abood-appinstall'
NATIVE_EXEC = Path('/usr/bin/abood-appinstall')
NATIVE_MODULE_DIR = Path('/usr/lib/abood-appinstall')
DESKTOP_ID = 'io.github.aboodmohd.AppInstall.desktop'


def owner(path):
    """Return the package owning path, or an empty string on any failure."""
    checks = (
        ('pacman', ['pacman', '-Qoq', '--', str(path)]),
        ('dpkg', ['dpkg-query', '-S', str(path)]),
        ('rpm', ['rpm', '-qf', '--qf', '%{NAME}\n', str(path)]),
    )
    for manager, argv in checks:
        try:
            result = subprocess.run(argv, capture_output=True, text=True,
                                    timeout=8, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            value = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ''
            if manager == 'dpkg' and ':' in value:
                value = value.split(':', 1)[0]
            if value == PACKAGE:
                return value
    return ''


def native_installation():
    """True only when a verified native package owns the CLI."""
    return NATIVE_EXEC.is_file() and owner(NATIVE_EXEC) == PACKAGE


def packaged_helper():
    for candidate in (NATIVE_MODULE_DIR/'appinstall-installer',
                      Path(__file__).resolve().parent/'appinstall-installer'):
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    return None


def user_desktop_entry(home=None):
    root = (Path(home)/'.local/share' if home else
            Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share')))
    return root/'applications'/DESKTOP_ID


def repair_user_desktop_entry(home=None):
    """Repair only an AppInstall entry with a stale/missing launcher.

    Native installations must execute the package-owned CLI. Other desktop
    entries and user-edited fields are preserved.
    """
    if not native_installation():
        return False
    entry = user_desktop_entry(home)
    if not entry.is_file() or entry.is_symlink():
        return False
    try:
        lines = entry.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError):
        return False
    exec_index = next((i for i, line in enumerate(lines)
                       if line.startswith('Exec=')), None)
    if exec_index is None:
        return False
    current = lines[exec_index][5:].strip().split()[0].strip('"')
    expected = str(NATIVE_EXEC)
    if current == expected:
        return False
    # Only repair entries that clearly belong to AppInstall and point to a
    # launcher that is absent or outside a current verified installation.
    text = '\n'.join(lines)
    is_ours = ('Name=AppInstall' in text or 'abood-appinstall' in current or
               '/appinstall' in current)
    if not is_ours:
        return False
    target = Path(os.path.expanduser(current)) if current.startswith(('~', '/')) else None
    if target is not None and target.is_file():
        return False
    lines[exec_index] = 'Exec='+expected+' %F'
    temp = entry.with_name('.'+entry.name+'.appinstall-repair.tmp')
    temp.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    os.replace(temp, entry)
    return True


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ['--repair-native-desktop']:
        changed = repair_user_desktop_entry()
        print('repaired' if changed else 'unchanged')
        return 0
    print('usage: install_mode.py --repair-native-desktop', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
