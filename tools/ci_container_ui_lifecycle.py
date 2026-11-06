#!/usr/bin/env python3
"""Exercise DEB/RPM GUI worker teardown without containers or package changes.

Run in a real desktop session, or inside Xvfb. A non-zero process exit (such
as SIGSEGV / 139) fails CI even if Qt's event loop returned 0.
"""
import gc
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
import container_ui as ui


class FakeEngine:
    def __init__(self):
        self.registry = {}

    def transaction(self, info):
        return "SIMULATED TRANSACTION: no containers or packages changed."

    def install(self, info, choose):
        return dict(info, status="installed",
                    candidates=["/usr/share/applications/mock.desktop"],
                    exports=[{"path": "SIMULATED-ONLY"}])

    def key(self, info):
        return "deb:appinstall-ui-test"

    def launch(self, key):
        raise RuntimeError("The test must never launch a real application.")


ui.Engine = FakeEngine
ui.inspect_package = lambda path: {
    "name": "appinstall-ui-test",
    "application_name": "AppInstall UI Test",
    "version": "1.0",
    "kind": "deb",
    "container": "debian-apps",
    "description": "Mock workflow only. No installation.",
    "architecture": "amd64",
    "dependencies": "",
    "maintainer": "",
    "icon": "",
    "icon_name": "applications-utilities",
}
ui.QMessageBox.question = staticmethod(
    lambda *args, **kwargs: QMessageBox.StandardButton.Yes
)

app = QApplication(sys.argv)
window = ui.Workflow(["SIMULATED-TEST.deb"])
window.show()
phase = 0
deadline = time.monotonic() + 40


def drive():
    global phase
    if time.monotonic() >= deadline:
        print("FAIL: UI workflow did not finish in 40 seconds", flush=True)
        app.exit(2)
        return
    if phase == 0 and window.stage == "preview" and window.action.isEnabled():
        phase = 1
        window.action.click()  # Prepare and review (fake transaction)
    elif phase == 1 and window.stage == "transaction" and window.action.isEnabled():
        phase = 2
        window.action.click()  # Install (fake)
    elif phase == 2:
        for dialog in app.topLevelWidgets():
            if isinstance(dialog, ui.result_ui.SuccessDialog) and dialog.isVisible():
                phase = 3
                dialog.accept()  # Done
                break
    elif phase == 3 and window.stage == "open":
        # The workflow can only close once its QThread has actually stopped.
        if all(not job.isRunning() for job in window.jobs):
            if window.close():
                phase = 4


    if phase != 4:
        QTimer.singleShot(20, drive)


QTimer.singleShot(20, drive)
rc = app.exec()
if rc != 0 or phase != 4:
    raise SystemExit(f"FAIL: event loop exit {rc}, phase {phase}")
# Discard Qt/Python wrappers and any cyclic signal callbacks while the
# QApplication instance still exists, rather than in interpreter finalization.
del window
gc.collect()
del app
gc.collect()
print("PASS: simulated Prepare -> Install -> Done -> Close, process exit zero", flush=True)
