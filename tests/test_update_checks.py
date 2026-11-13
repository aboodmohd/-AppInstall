"""Update check tests: TTL caching and desktop notifications.

Covers the auto/manual update check flow with TTL caching (~12h) and
best-effort notify-send notifications. The appinstall-installer helper is
stubbed so no network access is required.
"""
import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location('manager', ROOT / 'manager.py')
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)

import settings as settings_mod


class TTLCachingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_STATE_HOME': str(self.root / 'state'),
        })
        self.env.start()
        settings_mod.write({'theme': 'auto', 'favorites': [], 'notifications': False,
                            'last_update_check': 0})

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_auto_check_skipped_within_ttl(self):
        """An automatic check within the TTL does not spawn the installer."""
        now = time.time()
        settings_mod.update('last_update_check', int(now))
        from qt_compat import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        window = manager.ManagerWindow()
        with patch.object(window.update_process, 'start') as start:
            window._check_updates(manual=False)
            start.assert_not_called()
        window.close()

    def test_auto_check_runs_after_ttl_expired(self):
        """An automatic check after the TTL has expired spawns the installer."""
        settings_mod.update('last_update_check', 0)
        from qt_compat import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        window = manager.ManagerWindow()
        with patch.object(window.update_process, 'start') as start:
            window._check_updates(manual=False)
            start.assert_called_once()
        window.close()

    def test_manual_check_bypasses_ttl(self):
        """A manual Check now always spawns the installer even within TTL."""
        now = time.time()
        settings_mod.update('last_update_check', int(now))
        from qt_compat import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        window = manager.ManagerWindow()
        with patch.object(window.update_process, 'start') as start:
            window._check_updates(manual=True)
            start.assert_called_once()
        window.close()

    def test_last_update_check_saved_after_check(self):
        """last_update_check is written to settings after a check completes."""
        settings_mod.update('last_update_check', 0)
        from qt_compat import QtWidgets, QtCore
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        window = manager.ManagerWindow()
        class FakeByteArray:
            def __init__(self, data): self._data = data
            def __bytes__(self): return self._data
        proc = MagicMock()
        proc.readAll.return_value = FakeByteArray(b'APPINSTALL_UPDATE=v1.4.0\n')
        window.update_process = proc
        window.update_operation = 'check'
        window._update_finished(0, QtCore.QProcess.ExitStatus.NormalExit)
        self.assertGreaterEqual(
            settings_mod.read()['last_update_check'],
            int(time.time()) - 1)
        window.close()

    def test_ttl_respected_on_manager_open(self):
        """Manager opening within TTL does not trigger an auto check."""
        now = time.time()
        settings_mod.update('last_update_check', int(now))
        from qt_compat import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        with patch.object(manager.ManagerWindow, '_check_updates') as check:
            window = manager.ManagerWindow()
            app.processEvents()
            app.processEvents()
            check.assert_not_called()
        window.close()


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_STATE_HOME': str(self.root / 'state'),
        })
        self.env.start()
        settings_mod.write({'theme': 'auto', 'favorites': [], 'notifications': True,
                            'last_update_check': 0})

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_notification_sent_when_update_available(self):
        from qt_compat import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        window = manager.ManagerWindow()
        with patch('subprocess.run') as run:
            window._notify_update('v1.4.0')
            run.assert_called_once()
            args = run.call_args.args[0]
            self.assertEqual(args[0], 'notify-send')
            self.assertIn('v1.4.0', args[2])
        window.close()

    def test_notification_skipped_when_disabled(self):
        settings_mod.update('notifications', False)
        from qt_compat import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        window = manager.ManagerWindow()
        with patch('subprocess.run') as run:
            window._notify_update('v1.4.0')
            run.assert_not_called()
        window.close()

    def test_notification_headless_safe(self):
        """notify-send failure never crashes the update flow."""
        from qt_compat import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        window = manager.ManagerWindow()
        with patch('subprocess.run', side_effect=OSError('no notify-send')):
            window._notify_update('v1.4.0')
        window.close()


class SettingsSanitizeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(self.root / 'data'),
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_last_update_check_sanitized(self):
        settings_mod.write({'last_update_check': 'not-a-number'})
        self.assertEqual(settings_mod.read()['last_update_check'], 0)

    def test_last_update_check_round_trip(self):
        settings_mod.write({'last_update_check': 1234567890})
        self.assertEqual(settings_mod.read()['last_update_check'], 1234567890)


if __name__ == '__main__':
    unittest.main()
