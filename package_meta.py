"""Local package metadata for previews. Never executes packages or shells out."""
import configparser
import os
import re
import shlex
import shutil
from pathlib import Path

APPID_PATTERN = re.compile(r'^[A-Za-z0-9_]+(\.[A-Za-z0-9_-]+)+$')


def values(path, section):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(path)
        return dict(parser[section])
    except (OSError, KeyError, configparser.Error, UnicodeError):
        return {}


def metadata_roots():
    return [Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share')),
            Path.home()/'.local/share/flatpak/exports/share',
            Path('/var/lib/flatpak/exports/share'), Path('/usr/share')]


def display_metadata(file, kind, roots):
    """App name, description and icon from local config only.

    The reference application ID is joined into a path only when it matches
    the desktop-ID pattern; anything else is discarded instead of resolving
    traversal fragments into unrelated files."""
    ref = values(file, 'Flatpak Ref') if kind == 'flatpakref' else {}
    raw_id = ref.get('name', '')
    appid = raw_id if APPID_PATTERN.match(raw_id) else ''
    name = appid.rsplit('.', 1)[-1] if appid else Path(file).stem
    description = ref.get('comment', ref.get('description', ''))
    icon = ref.get('icon', '')
    if appid:
        for root in roots:
            meta = values(Path(root)/'applications'/f'{appid}.desktop', 'Desktop Entry')
            if meta:
                name = meta.get('name', name)
                description = meta.get('comment', description)
                icon = meta.get('icon', icon)
                break
    return dict(appid=appid, name=name, description=description, icon=icon)


def human_size(value):
    try: size = int(value)
    except (TypeError, ValueError): return ''
    step, units = 1024, ('%d B', '%d KiB', '%.1f MiB', '%.2f GiB')
    index = 0
    size = float(size)
    while size >= step and index < len(units)-1:
        size /= float(step); index += 1
    return units[index] % size

def require_backend_tools(*tools):
    """Report missing host tools and a command for the host package manager."""
    missing = [tool for tool in tools if not shutil.which(tool)]
    if not missing:
        return
    message = "Missing required host tools: " + ", ".join(missing) + "."
    if shutil.which("pacman"):
        command, archive = "sudo pacman -S --needed", "libarchive"
    elif shutil.which("apt-get"):
        command, archive = "sudo apt install", "libarchive-tools"
    elif shutil.which("dnf"):
        command, archive = "sudo dnf install", "bsdtar"
    else:
        raise RuntimeError(message + " Install them with your distribution's package manager.")
    packages = [archive if tool == "bsdtar" else tool for tool in missing]
    raise RuntimeError(message + "\nSetup: " + command + " " + shlex.join(packages))
