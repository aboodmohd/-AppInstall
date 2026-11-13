"""settings.py — preference storage tests under a disposable XDG_DATA_HOME.

A missing, unreadable or corrupt settings file must mean defaults, never an
exception. Writes must be atomic, drop unknown or malformed keys, and leave
no temporary files behind.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import settings


class SettingsBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(Path(self.temp.name)/'data'),
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def path(self):
        return settings.settings_path()


class DefaultsTests(SettingsBase):
    def test_missing_file_returns_defaults(self):
        self.assertEqual(settings.read(), settings.DEFAULTS)

    def test_corrupt_file_returns_defaults(self):
        self.path().parent.mkdir(parents=True)
        self.path().write_bytes(b'\x00\x01not json{')
        self.assertEqual(settings.read(), settings.DEFAULTS)

    def test_non_object_document_returns_defaults(self):
        self.path().parent.mkdir(parents=True)
        self.path().write_text('[]')
        self.assertEqual(settings.read(), settings.DEFAULTS)

    def test_missing_directory_read_never_creates_it(self):
        settings.read()
        self.assertFalse(self.path().parent.exists())


class SanitizeTests(SettingsBase):
    def test_malformed_keys_fall_back(self):
        self.path().parent.mkdir(parents=True)
        self.path().write_text(json.dumps({
            'theme': 'purple',
            'favorites': [1, 'kept', None, {'bad': 'shape'}, 'also-kept'],
            'notifications': 'yes',
            'unknown-key': 'dropped',
        }))
        self.assertEqual(settings.read(), {
            'theme': 'auto',
            'favorites': ['kept', 'also-kept'],
            'notifications': False,
            'last_update_check': 0,
        })

    def test_theme_accepts_all_supported_values(self):
        for theme in settings.THEMES:
            self.path().parent.mkdir(parents=True, exist_ok=True)
            self.path().write_text(json.dumps({'theme': theme}))
            self.assertEqual(settings.read()['theme'], theme)


class WriteTests(SettingsBase):
    def test_round_trip(self):
        values = {'theme': 'dark', 'favorites': ['appimage:z'],
                  'notifications': True, 'last_update_check': 0}
        self.assertEqual(settings.write(values), values)
        self.assertEqual(settings.read(), values)

    def test_permissions_are_private(self):
        settings.write({'theme': 'light'})
        mode = stat.S_IMODE(self.path().stat().st_mode)
        self.assertEqual(mode, 0o600)
        parent_mode = stat.S_IMODE(self.path().parent.stat().st_mode)
        self.assertEqual(parent_mode & 0o077, 0)

    def test_atomic_write_leaves_no_temporaries(self):
        settings.write({'theme': 'light'})
        settings.write({'theme': 'dark'})
        self.assertEqual([entry.name for entry in self.path().parent.iterdir()],
                         ['settings.json'])

    def test_overwrite_replaces_previous_values(self):
        settings.write({'theme': 'dark', 'favorites': ['old'], 'notifications': True})
        settings.write({'theme': 'light'})
        self.assertEqual(settings.read(),
                         {'theme': 'light', 'favorites': [], 'notifications': False,
                          'last_update_check': 0})


class UpdateTests(SettingsBase):
    def test_update_merges_without_clobbering_other_keys(self):
        settings.update('theme', 'light')
        settings.update('favorites', ['appimage:a'])
        self.assertEqual(settings.read(), {
            'theme': 'light',
            'favorites': ['appimage:a'],
            'notifications': False,
            'last_update_check': 0,
        })

    def test_update_sanitizes_value(self):
        settings.update('theme', 'neon')
        self.assertEqual(settings.read()['theme'], 'auto')

    def test_settings_path_tracks_environment(self):
        self.assertEqual(self.path().name, 'settings.json')
        self.assertEqual(self.path().parent.name, 'appinstall')


if __name__ == '__main__':
    unittest.main()
