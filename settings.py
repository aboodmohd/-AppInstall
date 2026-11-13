#!/usr/bin/env python3
"""Persistent user preferences for AppInstall.

Stores one JSON document at ${XDG_DATA_HOME}/appinstall/settings.json. A
missing or unreadable file means defaults; a corrupt file never raises and
is replaced on the next write. Writes are atomic (temporary file + rename)
with 0600 permissions inside a 0700 directory, matching the registry files.
"""
import json
import os
import uuid
from pathlib import Path

THEMES = ('auto', 'light', 'dark')
DEFAULTS = {'theme': 'auto', 'favorites': [], 'notifications': False}


def settings_path():
    root = Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))
    return root/'appinstall'/'settings.json'


def _sanitize(values):
    """Drop unknown or malformed keys; known keys fall back to defaults."""
    if not isinstance(values, dict):
        return dict(DEFAULTS)
    result = dict(DEFAULTS)
    theme = values.get('theme')
    result['theme'] = theme if theme in THEMES else DEFAULTS['theme']
    favorites = values.get('favorites')
    if isinstance(favorites, list):
        result['favorites'] = [key for key in favorites if isinstance(key, str)]
    notifications = values.get('notifications')
    if isinstance(notifications, bool):
        result['notifications'] = notifications
    return result


def read():
    try:
        values = json.loads(settings_path().read_text())
    except (OSError, ValueError):
        return dict(DEFAULTS)
    return _sanitize(values)


def write(values):
    clean = _sanitize(values)
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    fd = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as file:
        json.dump(clean, file, indent=2)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)
    return clean


def update(key, value):
    values = read()
    values[key] = value
    return write(values)
