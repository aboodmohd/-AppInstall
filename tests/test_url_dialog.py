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


class _DialogTestBase:
    """Shared fixture: an offscreen dialog plus a fake per-download temp dir."""

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


@unittest.skipIf(url_dialog is None, "PySide6 is optional")
class UrlDialogTests(_DialogTestBase, unittest.TestCase):

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

    def test_retry_preserves_url_and_checksum(self):
        url = "https://example.com/app.AppImage"
        checksum = "a" * 64
        self.dialog.url_edit.setText(url)
        self.dialog.checksum_edit.setText(checksum)
        self.dialog._download_failed("Connection lost")
        self.assertEqual(self.dialog.download_btn.text(), "&Retry Download")
        self.assertFalse(self.dialog.download_btn.isEnabled())
        self.dialog._download_worker_stopped()
        worker = MagicMock()
        worker.isRunning.return_value = False
        with patch.object(url_install, "validate_url"), \
             patch.object(url_dialog, "DownloadWorker", return_value=worker) as create:
            self.dialog.download_btn.click()
            create.assert_called_once_with(url, checksum, self.dialog.cancel)

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


@unittest.skipIf(url_dialog is None, "PySide6 is optional")
class DownloadCleanupTests(_DialogTestBase, unittest.TestCase):
    """Regression tests: a download that is never installed leaves no temp files.

    Completed downloads must be discarded (with their per-download
    ``appinstall-url-*`` directory) when the dialog is closed, rejected,
    returned from an unsuccessful review, or when installation fails —
    but files must stay untouched while a download worker is active.
    """

    def _fake_result(self, name="downloaded.AppImage", kind="appimage"):
        result = MagicMock()
        result.detected_format = kind
        result.final_url = "https://example.com/" + name
        result.size = 12345
        result.sha256 = "abcd1234"
        result.checksum_verified = None
        result.path = self.tempdir / name
        return result

    def _complete_download(self, **kwargs):
        """Put the dialog on the download-complete page with a real temp file."""
        result = self._fake_result(**kwargs)
        Path(result.path).write_bytes(b"package-bytes")
        self.dialog._download_finished(result)
        self.app.processEvents()
        return result

    # ── closing / rejecting after a completed download ────────────────

    def test_close_after_download_removes_temp_dir(self):
        self._complete_download()
        self.assertTrue(self.dialog.complete_page.isVisible())
        self.dialog.close()
        self.assertFalse(self.tempdir.exists())
        self.assertIsNone(self.dialog._download_result)
        self.assertFalse(self.dialog.isVisible())

    def test_reject_after_download_removes_temp_dir(self):
        self._complete_download()
        self.dialog.reject()
        self.assertFalse(self.tempdir.exists())
        self.assertIsNone(self.dialog._download_result)
        self.assertEqual(self.dialog.result(), url_dialog.QDialog.Rejected)

    def test_discard_is_idempotent(self):
        result = self._complete_download()
        self.dialog._discard_download()
        self.dialog._discard_download()  # second call must be a no-op
        self.assertFalse(self.tempdir.exists())
        self.assertIsNone(self.dialog._download_result)
        self.assertFalse(Path(result.path).exists())

    # ── unsuccessful review paths ─────────────────────────────────────

    def _review_with_returncode(self, code):
        fake_rc = MagicMock()
        fake_rc.returncode = code
        with patch.object(url_dialog.subprocess, "run", return_value=fake_rc), \
             patch.object(url_dialog.QMessageBox, "warning", return_value=0) as warn, \
             patch.object(url_dialog.QMessageBox, "information", return_value=0):
            self.dialog._review_and_install()
        return warn

    def test_cancel_at_preview_removes_dir_and_returns_to_url_page(self):
        self.dialog.url_edit.setText("https://example.com/app.AppImage")
        self._complete_download()
        warn = self._review_with_returncode(1)
        warn.assert_not_called()
        self.assertFalse(self.tempdir.exists())
        self.assertIsNone(self.dialog._download_result)
        self.assertTrue(self.dialog.url_page.isVisible())
        self.assertFalse(self.dialog.complete_page.isVisible())
        self.assertFalse(self.dialog.review_btn.isEnabled())
        self.assertEqual(self.dialog.url_edit.text(), "https://example.com/app.AppImage")

    def test_review_window_failure_cleans_up(self):
        self._complete_download()
        warn = self._review_with_returncode(3)
        warn.assert_called_once()
        self.assertFalse(self.tempdir.exists())
        self.assertTrue(self.dialog.url_page.isVisible())
        self.assertFalse(self.dialog.complete_page.isVisible())

    def test_review_other_failure_cleans_up(self):
        self._complete_download()
        warn = self._review_with_returncode(2)
        warn.assert_called_once()
        self.assertFalse(self.tempdir.exists())
        self.assertTrue(self.dialog.url_page.isVisible())

    def test_missing_review_module_cleans_up(self):
        self._complete_download()
        with patch.object(self.dialog, "_locate", return_value=None) as locate, \
             patch.object(url_dialog.QMessageBox, "warning", return_value=0):
            self.dialog._review_and_install()
        locate.assert_called_once_with("confirm.py")
        self.assertFalse(self.tempdir.exists())
        self.assertTrue(self.dialog.url_page.isVisible())

    def test_review_start_failure_cleans_up(self):
        self._complete_download()
        with patch.object(url_dialog.subprocess, "run", side_effect=OSError("boom")), \
             patch.object(url_dialog.QMessageBox, "warning", return_value=0) as warn:
            self.dialog._review_and_install()
        warn.assert_called_once()
        self.assertFalse(self.tempdir.exists())
        self.assertTrue(self.dialog.url_page.isVisible())

    # ── installation errors ───────────────────────────────────────────

    def test_failed_install_removes_temp_dir(self):
        # "deb" skips the graphical review and goes straight to the backend.
        self._complete_download(kind="deb")
        warn = self._review_with_returncode(1)
        warn.assert_called_once()
        self.assertFalse(self.tempdir.exists())
        self.assertIsNone(self.dialog._download_result)
        self.assertFalse(self.dialog.review_btn.isEnabled())
        self.assertTrue(self.dialog.url_page.isVisible())
        self.assertFalse(self.dialog.complete_page.isVisible())
        self.assertFalse(self.dialog.progress_page.isVisible())

    def test_install_start_failure_cleans_up(self):
        self._complete_download(kind="deb")
        with patch.object(url_dialog.subprocess, "run", side_effect=OSError("no backend")), \
             patch.object(url_dialog.QMessageBox, "warning", return_value=0) as warn:
            self.dialog._review_and_install()
        warn.assert_called_once()
        self.assertFalse(self.tempdir.exists())

    def test_missing_entry_point_cleans_up(self):
        result = self._complete_download(kind="deb")
        with patch.object(self.dialog, "_locate", return_value=None) as locate, \
             patch.object(url_dialog.QMessageBox, "warning", return_value=0):
            self.dialog._install_file(result.path, self.tempdir)
        locate.assert_called_once_with("appinstall")
        self.assertFalse(self.tempdir.exists())

    # ── active downloads are preserved ────────────────────────────────

    def test_reject_during_download_preserves_active_file(self):
        worker = MagicMock()
        worker.isRunning.return_value = True
        self.dialog.worker = worker
        partial = self.tempdir / "partial.AppImage"
        partial.write_bytes(b"partial")
        self.dialog.reject()
        self.assertTrue(self.dialog.cancel.is_set())
        self.assertTrue(partial.exists())
        self.assertTrue(self.dialog.isVisible())
        # Once the worker has stopped, closing discards nothing extra: the
        # worker already removed its own partial file on cancellation.
        worker.isRunning.return_value = False
        self.dialog.reject()
        self.assertFalse(self.dialog.isVisible())

    def test_close_during_download_preserves_active_file(self):
        worker = MagicMock()
        worker.isRunning.return_value = True
        self.dialog.worker = worker
        partial = self.tempdir / "partial.AppImage"
        partial.write_bytes(b"partial")
        captured = []
        with patch.object(url_dialog.QTimer, "singleShot",
                          lambda ms, fn=None: captured.append(fn) if fn is not None else None):
            self.dialog.close()
        self.assertTrue(self.dialog.cancel.is_set())
        self.assertTrue(self.dialog.isVisible())  # close ignored while working
        self.assertTrue(partial.exists())         # active file preserved
        self.assertTrue(self.tempdir.exists())
        # The worker thread finishes and the recheck timer completes the close.
        worker.isRunning.return_value = False
        for fn in captured:
            fn()
        self.assertFalse(self.dialog.isVisible())

    def test_download_completing_after_close_is_discarded(self):
        worker = MagicMock()
        worker.isRunning.return_value = True
        self.dialog.worker = worker
        captured = []
        with patch.object(url_dialog.QTimer, "singleShot",
                          lambda ms, fn=None: captured.append(fn) if fn is not None else None):
            self.dialog.close()
        result = self._fake_result()
        Path(result.path).write_bytes(b"package-bytes")
        # The completion signal is delivered after the close was requested.
        self.dialog._download_finished(result)
        self.assertFalse(self.tempdir.exists())
        self.assertIsNone(self.dialog._download_result)
        self.assertFalse(self.dialog.complete_page.isVisible())
        worker.isRunning.return_value = False
        for fn in captured:
            fn()
        self.assertFalse(self.dialog.isVisible())

    def test_download_completing_after_cancel_is_discarded(self):
        self.dialog._cancel_download()
        self._complete_download()
        self.assertFalse(self.tempdir.exists())
        self.assertIsNone(self.dialog._download_result)
        self.assertFalse(self.dialog.complete_page.isVisible())

    def test_download_completing_after_reject_is_discarded(self):
        worker = MagicMock()
        worker.isRunning.return_value = True
        self.dialog.worker = worker
        with patch.object(url_dialog.QTimer, "singleShot"):
            self.dialog.reject()
        self._complete_download()
        self.assertFalse(self.tempdir.exists())
        worker.isRunning.return_value = False
        self.dialog._recheck_close()
        self.assertFalse(self.dialog.isVisible())

    def test_install_keeps_file_until_backend_returns(self):
        result = self._complete_download(kind="deb")
        def backend(*args, **kwargs):
            self.assertTrue(result.path.exists())
            return MagicMock(returncode=1)
        with patch.object(url_dialog.subprocess, "run", side_effect=backend), \
             patch.object(url_dialog.QMessageBox, "warning", return_value=0):
            self.dialog._review_and_install()
        self.assertFalse(self.tempdir.exists())


if __name__ == "__main__":
    unittest.main()
