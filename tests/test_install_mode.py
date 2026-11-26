"""Installation-mode detection and stale desktop-entry repair."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import install_mode as mode


class InstallModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_repairs_stale_native_desktop_entry(self):
        entry = self.root/'.local/share/applications'/mode.DESKTOP_ID
        entry.parent.mkdir(parents=True)
        entry.write_text('[Desktop Entry]\nName=AppInstall\n'
                         'Exec=/tmp/existing-portable/bin/abood-appinstall %F\n'
                         'Icon=custom\n')
        with patch.object(mode, 'native_installation', return_value=True):
            self.assertTrue(mode.repair_user_desktop_entry(self.root))
        lines = entry.read_text().splitlines()
        self.assertIn('Exec='+str(mode.NATIVE_EXEC)+' %F', lines)
        self.assertIn('Icon=custom', lines)

    def test_keeps_legitimate_existing_portable_launcher(self):
        entry = self.root/'.local/share/applications'/mode.DESKTOP_ID
        entry.parent.mkdir(parents=True)
        launcher = self.root/'.local/bin/abood-appinstall'
        launcher.parent.mkdir(parents=True)
        launcher.write_text('#!/bin/sh\n')
        entry.write_text('[Desktop Entry]\nName=AppInstall\n'
                         'Exec='+str(launcher)+' %F\nIcon=custom\n')
        with patch.object(mode, 'native_installation', return_value=True):
            self.assertFalse(mode.repair_user_desktop_entry(self.root))
        self.assertIn('Exec='+str(launcher)+' %F', entry.read_text())

    def test_keeps_existing_quoted_launcher_with_spaces(self):
        entry = self.root/'.local/share/applications'/mode.DESKTOP_ID
        entry.parent.mkdir(parents=True)
        launcher = self.root/'My Apps'/'abood-appinstall'
        launcher.parent.mkdir(parents=True)
        launcher.write_text('#!/bin/sh\n')
        entry.write_text('[Desktop Entry]\nName=AppInstall\n'
                         'Exec="'+str(launcher)+'" %F\nIcon=custom\n')
        with patch.object(mode, 'native_installation', return_value=True):
            self.assertFalse(mode.repair_user_desktop_entry(self.root))
        self.assertIn('Exec="'+str(launcher)+'" %F', entry.read_text())

    def test_preserves_exec_arguments_when_repairing(self):
        entry = self.root/'.local/share/applications'/mode.DESKTOP_ID
        entry.parent.mkdir(parents=True)
        entry.write_text('[Desktop Entry]\nName=AppInstall\n'
                         'Exec="/tmp/gone/My Apps/abood-appinstall" --widgets %F\n')
        with patch.object(mode, 'native_installation', return_value=True):
            self.assertTrue(mode.repair_user_desktop_entry(self.root))
        self.assertIn('Exec='+str(mode.NATIVE_EXEC)+' --widgets %F',
                      entry.read_text())

    def test_does_not_repair_unrelated_entry(self):
        entry = self.root/'.local/share/applications'/mode.DESKTOP_ID
        entry.parent.mkdir(parents=True)
        entry.write_text('[Desktop Entry]\nName=Other App\nExec=/bin/true\n')
        with patch.object(mode, 'native_installation', return_value=True):
            self.assertFalse(mode.repair_user_desktop_entry(self.root))
        self.assertIn('Exec=/bin/true', entry.read_text())

    def test_no_repair_without_native_package(self):
        with patch.object(mode, 'native_installation', return_value=False):
            self.assertFalse(mode.repair_user_desktop_entry(self.root))


if __name__ == '__main__':
    unittest.main()
