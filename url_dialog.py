#!/usr/bin/env python3
"""Qt dialogs for AppInstall "Install from URL".

A single dialog transitions through three pages:

1. URL entry — paste a direct HTTPS package URL, optionally an expected
   SHA-256 checksum, then start the download.
2. Download progress — streaming download in a worker thread with name, bytes,
   total size, percentage, speed, progress bar and a cancel button.
3. Download complete — detected format, size and SHA-256, followed by the
   existing package preview/confirmation and installation through the normal
   AppInstall backends.

The GUI thread is never blocked: the network transfer runs in a QThread and
reports progress through Qt signals. Cancellation closes the response and removes
the partial temporary file.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

try:
    from PySide6.QtCore import Qt, QThread, QTimer, Signal
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout,
                                   QLabel, QLineEdit, QMessageBox, QProgressBar,
                                   QPushButton, QVBoxLayout)
except ImportError as error:  # pragma: no cover - import guard
    print("PySide6 is required for Install from URL: " + str(error), file=sys.stderr)
    sys.exit(3)

import ui_style
import url_install
from package_meta import human_size

CONFIRM_KINDS_WITH_PREVIEW = ("appimage", "flatpak", "flatpakref", "flatpakrepo")


class DownloadWorker(QThread):
    """Background worker that streams a URL download without blocking the GUI."""

    progress = Signal(dict)
    finished = Signal(object)  # url_install.DownloadResult
    failed = Signal(str)

    def __init__(self, url, expected_checksum, cancel):
        super().__init__()
        self.url = url
        self.expected_checksum = expected_checksum
        self.cancel = cancel
        self.result = None

    def run(self):
        try:
            self.result = url_install.download_url(
                self.url,
                expected_checksum=self.expected_checksum,
                cancel=self.cancel,
                progress=self._on_progress,
            )
        except BaseException as error:  # noqa: BLE001 - surface any download failure
            self.failed.emit(str(error))
            return
        self.finished.emit(self.result)

    def _on_progress(self, info):
        self.progress.emit(info)


class UrlInstallDialog(QDialog):
    """Install from URL dialog: enter URL, download, review, install."""

    installed = Signal()  # emitted when a dependent installation finishes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install from URL")
        self.setMinimumWidth(620)
        self.resize(700, 520)
        self._download_result = None
        self.worker = None
        self.cancel = threading.Event()
        self._build_ui()
        self.setStyleSheet(ui_style.primary_button_stylesheet(self)
                           + ui_style.ghost_button_stylesheet(self))

    # ── layout ─────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 20)
        layout.setSpacing(14)

        title = QLabel("Install from URL")
        font = title.font(); font.setPointSize(20); font.setBold(True); title.setFont(font)
        title.setTextFormat(Qt.PlainText)
        layout.addWidget(title)

        subtitle = QLabel("Download an application package from a direct HTTPS link, "
                          "then review and install it through AppInstall.")
        subtitle.setTextFormat(Qt.PlainText)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: palette(window-text);")
        layout.addWidget(subtitle)

        # ── URL entry page ─────────────────────────────────────────────
        self.url_page = QFrame()
        upage = QVBoxLayout(self.url_page)
        upage.setSpacing(10)
        row = QHBoxLayout(); row.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com/releases/application.AppImage")
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.textChanged.connect(self._update_download_state)
        row.addWidget(self.url_edit, 1)
        paste_btn = QPushButton("&Paste")
        paste_btn.setObjectName("ghost")
        paste_btn.setCursor(Qt.PointingHandCursor)
        paste_btn.clicked.connect(self._paste)
        row.addWidget(paste_btn)
        upage.addLayout(row)
        self.download_btn = QPushButton("&Download")
        self.download_btn.setObjectName("primary")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._start_download)
        upage.addWidget(self.download_btn)
        self.url_error = QLabel("")
        self.url_error.setTextFormat(Qt.PlainText)
        self.url_error.setStyleSheet("color: #b3402e; font-size: 12px;")
        self.url_error.hide()
        upage.addWidget(self.url_error)
        layout.addWidget(self.url_page)

        # checksum row (optional)
        ck_row = QHBoxLayout(); ck_row.setSpacing(8)
        ck_label = QLabel("Expected SHA-256 (optional):")
        ck_label.setTextFormat(Qt.PlainText)
        ck_label.setStyleSheet("color: palette(window-text); font-size: 12px;")
        ck_row.addWidget(ck_label)
        self.checksum_edit = QLineEdit()
        self.checksum_edit.setPlaceholderText("sha256 digest to verify against")
        self.checksum_edit.setClearButtonEnabled(True)
        ck_row.addWidget(self.checksum_edit, 1)
        layout.addLayout(ck_row)

        # security note
        note = QLabel("Only install applications from sources you trust. HTTPS protects the "
                      "transfer, but it does not guarantee the downloaded application is "
                      "trustworthy. Local and private network addresses are blocked.")
        note.setTextFormat(Qt.PlainText)
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(window-text); font-size: 11.5px;")
        layout.addWidget(note)

        # ── download progress page ─────────────────────────────────────
        self.progress_page = QFrame()
        ppage = QVBoxLayout(self.progress_page)
        ppage.setSpacing(10)
        self.pg_name = QLabel("")
        self.pg_name.setTextFormat(Qt.PlainText)
        self.pg_name.setStyleSheet("font-weight: 600;")
        ppage.addWidget(self.pg_name)
        self.pg_stats = QLabel("")
        self.pg_stats.setTextFormat(Qt.PlainText)
        self.pg_stats.setStyleSheet("color: palette(window-text); font-size: 12px;")
        ppage.addWidget(self.pg_stats)
        self.pg_bar = QProgressBar()
        self.pg_bar.setRange(0, 100)
        self.pg_bar.setValue(0)
        self.pg_bar.setTextVisible(True)
        ppage.addWidget(self.pg_bar)
        self.pg_cancel = QPushButton("&Cancel Download")
        self.pg_cancel.setObjectName("ghost")
        self.pg_cancel.setCursor(Qt.PointingHandCursor)
        self.pg_cancel.clicked.connect(self._cancel_download)
        ppage.addWidget(self.pg_cancel)
        self.progress_page.hide()
        layout.addWidget(self.progress_page)

        # ── download complete page ─────────────────────────────────────
        self.complete_page = QFrame()
        cpage = QVBoxLayout(self.complete_page)
        cpage.setSpacing(10)
        self.cp_format = QLabel("")
        self.cp_format.setTextFormat(Qt.PlainText)
        self.cp_format.setStyleSheet("font-weight: 600;")
        cpage.addWidget(self.cp_format)
        self.cp_size = QLabel("")
        self.cp_size.setTextFormat(Qt.PlainText)
        self.cp_size.setStyleSheet("color: palette(window-text); font-size: 12px;")
        cpage.addWidget(self.cp_size)
        self.cp_sha = QLabel("")
        self.cp_sha.setTextFormat(Qt.PlainText)
        self.cp_sha.setStyleSheet("color: palette(window-text); font-size: 12px;")
        cpage.addWidget(self.cp_sha)
        self.review_btn = QPushButton("&Review and Install")
        self.review_btn.setObjectName("primary")
        self.review_btn.setCursor(Qt.PointingHandCursor)
        self.review_btn.clicked.connect(self._review_and_install)
        cpage.addWidget(self.review_btn)
        self.complete_page.hide()
        layout.addWidget(self.complete_page)

        layout.addStretch(1)

        # global close
        grow = QHBoxLayout(); grow.addStretch(1)
        self.close_btn = QPushButton("&Close")
        self.close_btn.setObjectName("ghost")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.reject)
        grow.addWidget(self.close_btn)
        layout.addLayout(grow)

    # ── URL page ───────────────────────────────────────────────────────

    def _update_download_state(self):
        self.url_error.hide()
        text = self.url_edit.text().strip()
        self.download_btn.setEnabled(bool(text) and text.lower().startswith("https://"))

    def _paste(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            self.url_edit.setText(text)
            self._update_download_state()

    # ── download ───────────────────────────────────────────────────────

    def _start_download(self):
        url = self.url_edit.text().strip()
        checksum = self.checksum_edit.text().strip() or None
        self.url_error.hide()
        try:
            url_install.validate_url(url)
        except url_install.DownloadError as error:
            self.url_error.setText(str(error))
            self.url_error.show()
            return
        self.cancel.clear()
        self.worker = DownloadWorker(url, checksum, self.cancel)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._download_finished)
        self.worker.failed.connect(self._download_failed)
        self.url_page.hide()
        self.progress_page.show()
        self.pg_bar.setValue(0)
        self.pg_name.setText("Starting download…")
        self.pg_stats.setText("")
        self.review_btn.setEnabled(False)
        self.worker.start()

    def _on_progress(self, info):
        bytes_downloaded = info["bytes_downloaded"]
        total_size = info["total_size"]
        percent = info["percent"]
        speed = info["bytes_per_second"]
        self.pg_name.setText("Downloading…")
        self.pg_bar.setValue(0 if percent is None else int(percent))
        parts = [url_install.human_size(bytes_downloaded)]
        if total_size:
            parts.append("of " + url_install.human_size(total_size))
        if percent is not None:
            parts.append("(" + f"{percent:.0f}%" + ")")
        parts.append("@ " + url_install.human_size(int(speed)) + "/s")
        self.pg_stats.setText("  ".join(parts))

    def _cancel_download(self):
        self.cancel.set()
        self.pg_cancel.setEnabled(False)
        self.pg_cancel.setText("Cancelling…")

    def _download_finished(self, result):
        self._download_result = result
        self.progress_page.hide()
        self.complete_page.show()
        self.cp_format.setText("Format: " + result.detected_format.upper())
        self.cp_size.setText("Size: " + url_install.human_size(result.size))
        self.cp_sha.setText("SHA-256: " + result.sha256)
        self.review_btn.setEnabled(True)

    def _download_failed(self, message):
        self.progress_page.hide()
        self.url_page.show()
        self.cancel.clear()
        self.worker = None
        # Show the failure as a URL-level error so the user can correct and retry.
        self.url_error.setText(message)
        self.url_error.show()
        self.download_btn.setEnabled(True)

    # ── review / install ───────────────────────────────────────────────

    def _review_and_install(self):
        if self._download_result is None:
            return
        result = self._download_result
        kind = result.detected_format

        # Run the existing package preview/confirmation. AppImage and Flatpak
        # kinds use confirm.py; DEB/RPM use container_ui.py which has its own
        # preview, mirroring install_one() in the appinstall entry point.
        if kind in CONFIRM_KINDS_WITH_PREVIEW:
            details = ("Source: " + result.final_url + "\n"
                       "Format: " + kind + "\n"
                       "Size: " + url_install.human_size(result.size) + "\n"
                       "SHA-256: " + result.sha256 + "\n"
                       "Downloaded file: " + str(result.path))
            ui = self._locate("confirm.py")
            if not ui:
                QMessageBox.warning(self, "AppInstall", "The package review module is missing.")
                return
            try:
                rc = subprocess.run([sys.executable, str(ui), str(result.path), kind, details],
                                    capture_output=True, text=True)
            except Exception as error:  # noqa: BLE001
                QMessageBox.warning(self, "AppInstall",
                                    "Could not open the package review: " + str(error))
                return
            if rc.returncode == 1:
                return  # user cancelled the review
            if rc.returncode not in (0, 3):
                QMessageBox.warning(self, "AppInstall", "The package review did not complete.")
                return

        # Hand the downloaded file to the existing installation dispatch, which
        # routes each format to its normal backend (AppImage, Flatpak, DEB/RPM).
        self._install_file(result.path)

    def _install_file(self, path):
        appinstall = self._locate("appinstall")
        if not appinstall:
            QMessageBox.warning(self, "AppInstall", "The AppInstall entry point is missing.")
            return
        try:
            rc = subprocess.run([str(appinstall), "--yes", str(path)],
                                capture_output=True, text=True)
        except Exception as error:  # noqa: BLE001
            QMessageBox.warning(self, "AppInstall", "Installation could not start: " + str(error))
            return
        if rc.returncode == 0:
            QMessageBox.information(self, "AppInstall", "Installation completed successfully.")
            self.installed.emit()
            self.accept()
        else:
            QMessageBox.warning(self, "AppInstall",
                                "Installation finished with an error. See the terminal output "
                                "for details.")

    @staticmethod
    def _locate(name):
        """Find a sibling AppInstall module (dev tree or deployed /usr/bin)."""
        here = Path(__file__).resolve().parent
        candidate = here / name
        if candidate.is_file():
            return candidate
        deployed = Path("/usr/bin") / name
        if deployed.is_file():
            return deployed
        return None

    # ── window closure ─────────────────────────────────────────────────

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            self.cancel.set()
            event.ignore()
            QTimer.singleShot(100, self._recheck_close)
        else:
            event.accept()

    def _recheck_close(self):
        if self.worker is not None and self.worker.isRunning():
            QTimer.singleShot(100, self._recheck_close)
        else:
            self.cancel.clear()
            self.close()

    def reject(self):
        if self.worker is not None and self.worker.isRunning():
            self._cancel_download()
            return
        super().reject()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    shot = None
    if "--screenshot" in argv:
        index = argv.index("--screenshot")
        if index + 1 < len(argv):
            shot = argv[index + 1]
            argv = argv[:index] + argv[index + 2:]
    app = QApplication(sys.argv[:1])
    import ui_style as _us
    _us.maybe_dark(app)
    dialog = UrlInstallDialog()
    if shot:
        def capture():
            dialog.grab().save(shot)
            QApplication.quit()
        QTimer.singleShot(500, capture)
        dialog.show()
        app.exec()
        return
    sys.exit(0 if dialog.exec() == QDialog.Accepted else 1)


if __name__ == "__main__":
    main()
