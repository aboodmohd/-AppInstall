#!/usr/bin/env python3
"""Persistent user preferences for AppInstall.

Stores one JSON document at ${XDG_DATA_HOME}/appinstall/settings.json. A
missing or unreadable file means defaults; a corrupt file never raises and
is replaced on the next write. Writes are atomic (temporary file + rename)
with 0600 permissions inside a 0700 directory, matching the registry files.
"""
import json
import os
import re
import uuid
from pathlib import Path

THEMES = ('auto', 'light', 'dark')
DEFAULTS = {'theme': 'auto', 'favorites': [], 'notifications': False,
            'last_update_check': 0}


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
    last_check = values.get('last_update_check')
    if isinstance(last_check, (int, float)):
        result['last_update_check'] = int(last_check)
    else:
        result['last_update_check'] = DEFAULTS['last_update_check']
    cached = values.get('update_check_result')
    if isinstance(cached, dict):
        tag = cached.get('tag')
        checked_at = cached.get('checked_at')
        if (isinstance(tag, str) and
                (tag == '' or re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag)) and
                isinstance(checked_at, int) and checked_at > 0 and
                checked_at == result['last_update_check']):
            result['update_check_result'] = {'checked_at': checked_at, 'tag': tag}
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
