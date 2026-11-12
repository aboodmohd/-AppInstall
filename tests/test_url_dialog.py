"""GUI tests for url_dialog.py (offscreen Qt). No real network is used."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    import url_dialog
    import url_install
except ImportError:
    url_dialog = None


@unittest.skipIf(url_dialog is None, "PySide6 is optional")
class UrlDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        import tempfile
        import shutil
        # Fake downloads live in a private directory that mimics the real
        # per-download temp dir; never directly in the system temp root.
        self.tempdir = Path(tempfile.mkdtemp(prefix="appinstall-url-test-"))
        self.addCleanup(shutil.rmtree, self.tempdir, ignore_errors=True)
        self.dialog = url_dialog.UrlInstallDialog()
        self.dialog.show()
        self.app.processEvents()

    def tearDown(self):
        self.dialog.close()
        self.app.processEvents()

    def test_dialog_opens_on_url_page(self):
        self.assertTrue(self.dialog.url_page.isVisible())
        self.assertFalse(self.dialog.progress_page.isVisible())
        self.assertFalse(self.dialog.complete_page.isVisible())
        self.assertFalse(self.dialog.download_btn.isEnabled())
        self.assertEqual(self.dialog.windowTitle(), "Install from URL")

    def test_download_enabled_only_for_https(self):
        self.dialog.url_edit.setText("https://example.com/app.AppImage")
        self.dialog._update_download_state()
        self.assertTrue(self.dialog.download_btn.isEnabled())

        self.dialog.url_edit.setText("http://example.com/app.AppImage")
        self.dialog._update_download_state()
        self.assertFalse(self.dialog.download_btn.isEnabled())

        self.dialog.url_edit.setText("not a url")
        self.dialog._update_download_state()
        self.assertFalse(self.dialog.download_btn.isEnabled())

    def test_paste_sets_url_from_clipboard(self):
        self.dialog.url_edit.clear()
        self.app.clipboard().setText("https://example.com/pasted.AppImage")
        self.dialog._paste()
        self.assertEqual(self.dialog.url_edit.text(), "https://example.com/pasted.AppImage")
        self.assertTrue(self.dialog.download_btn.isEnabled())

    def test_invalid_url_shows_error(self):
        self.dialog.url_edit.setText("https://localhost/evil.AppImage")
        self.dialog._start_download()
        self.assertTrue(self.dialog.url_error.isVisible())
        self.assertTrue(self.dialog.url_page.isVisible())

    def test_valid_url_starts_download_and_switches_page(self):
        self.dialog.url_edit.setText("https://example.com/app.AppImage")
        self.dialog._update_download_state()
        fake_result = MagicMock()
        fake_result.detected_format = "appimage"
        fake_result.size = 12345
        fake_result.sha256 = "abcd1234"
        fake_result.final_url = "https://example.com/app.AppImage"
        fake_result.path = self.tempdir / "fake.AppImage"
        fake_worker = MagicMock()
        fake_worker.result = fake_result
        with patch.object(url_install.socket, "getaddrinfo",
                          return_value=[("AF_INET", None, None, None, ("93.184.216.34", 0))]), \
             patch.object(url_dialog, "DownloadWorker", return_value=fake_worker) as dw:
            self.dialog._start_download()
            dw.assert_called_once()
            fake_worker.start.assert_called_once()
        self.app.processEvents()
        self.assertTrue(self.dialog.progress_page.isVisible())
        self.assertFalse(self.dialog.url_page.isVisible())

    def test_download_finished_shows_complete_page(self):
        fake_result = MagicMock()
        fake_result.detected_format = "flatpak"
        fake_result.size = 999
        fake_result.sha256 = "deadbeef"
        self.dialog._download_finished(fake_result)
        self.assertTrue(self.dialog.complete_page.isVisible())
        self.assertFalse(self.dialog.progress_page.isVisible())
        self.assertIn(fake_result.detected_format.upper(), self.dialog.cp_format.text())
        self.assertIn("deadbeef", self.dialog.cp_sha.text())

    def test_review_and_install_emits_installed(self):
        self.dialog._download_result = MagicMock()
        self.dialog._download_result.detected_format = "appimage"
        self.dialog._download_result.final_url = "https://example.com/x.AppImage"
        self.dialog._download_result.size = 100
        self.dialog._download_result.sha256 = "aaaa"
        self.dialog._download_result.path = self.tempdir / "x.AppImage"
        emitted = []
        self.dialog.installed.connect(lambda: emitted.append(True))
        fake_rc = MagicMock()
        fake_rc.returncode = 0
        with patch.object(url_dialog.subprocess, "run", return_value=fake_rc), \
             patch.object(url_dialog.QMessageBox, "information", return_value=0), \
             patch.object(url_dialog.QMessageBox, "warning", return_value=0):
            self.dialog._review_and_install()
        self.assertEqual(emitted, [True])
        self.assertEqual(self.dialog.result(), url_dialog.QDialog.Accepted)

    def test_cancel_disables_cancel_button(self):
        self.dialog.progress_page.show()
        self.dialog._cancel_download()
        self.assertFalse(self.dialog.pg_cancel.isEnabled())
        self.assertEqual(self.dialog.pg_cancel.text(), "Cancelling…")


if __name__ == "__main__":
    unittest.main()
