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
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
import container_ui as ui


class FakeEngine:
    launches = 0

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
        assert key == "deb:appinstall-ui-test", key
        type(self).launches += 1


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
open_requested = "--open" in sys.argv
if open_requested:
    sys.argv.remove("--open")

no_open_action = "--no-open-action" in sys.argv
if no_open_action:
    sys.argv.remove("--no-open-action")

    OriginalSuccessDialog = ui.result_ui.SuccessDialog

    class NoOpenActionSuccessDialog(OriginalSuccessDialog):
        def __init__(self, name, description="", open_action=None, parent=None):
            # Diagnostic only: test the exact Done path without an unused
            # action callback that otherwise captures the Workflow instance.
            super().__init__(name, description, open_action=None, parent=parent)

    ui.result_ui.SuccessDialog = NoOpenActionSuccessDialog

sync_mode = "--sync" in sys.argv
if sync_mode:
    sys.argv.remove("--sync")

    def run_inline(self, callback, success, label=""):
        # Diagnostic A/B path: same real dialogs and fake transaction, but
        # no QThread objects at all. This never accesses the real backend.
        try:
            result = callback()
        except BaseException as exc:
            self.failure(str(exc))
        else:
            success(result)

    ui.Workflow.work = run_inline

app = QApplication(sys.argv)
window = ui.Workflow(["SIMULATED-TEST.deb"])
window.show()
phase = 0
deadline = time.monotonic() + 40


def drive():
    global phase
    # Use the real Qt question box; a timer clicks Yes while its modal
    # event loop is running. Do not monkey-patch the PySide6 C++ type.
    for dialog in app.topLevelWidgets():
        if isinstance(dialog, QMessageBox) and dialog.isVisible():
            yes_button = dialog.button(QMessageBox.StandardButton.Yes)
            if yes_button is None:
                raise RuntimeError("Confirmation does not contain a Yes button")
            yes_button.click()  # real button semantics; QMessageBox.question returns Yes
            QTimer.singleShot(20, drive)
            return
    if time.monotonic() >= deadline:
        print(f"FAIL: UI workflow timed out in phase={phase}, stage={window.stage}", flush=True)
        app.exit(2)
        return
    if phase == 0 and window.stage == "preview" and window.action.isEnabled():
        phase = 1
        # QMessageBox.question starts a nested event loop inside click().
        # Arm the next poll BEFORE opening that modal window.
        QTimer.singleShot(20, drive)
        window.action.click()  # Prepare and review (fake transaction)
        return
    elif phase == 1 and window.stage == "transaction" and window.action.isEnabled():
        phase = 2
        QTimer.singleShot(20, drive)
        window.action.click()  # Install (fake)
        return
    elif phase == 2:
        for dialog in app.topLevelWidgets():
            if isinstance(dialog, ui.result_ui.SuccessDialog) and dialog.isVisible():
                target = "Open Application" if open_requested else "Done"
                buttons = [button for button in dialog.findChildren(QPushButton)
                           if button.text().replace("&", "") == target]
                if len(buttons) != 1:
                    raise RuntimeError(f"Expected exactly one {target!r} button")
                phase = 3
                buttons[0].click()  # Exercise the production Qt button connection.
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
expected_launches = 1 if open_requested else 0
if FakeEngine.launches != expected_launches:
    raise SystemExit(f"FAIL: fake launches={FakeEngine.launches}, expected={expected_launches}")
# Discard Qt/Python wrappers and any cyclic signal callbacks while the
# QApplication instance still exists, rather than in interpreter finalization.
del window
gc.collect()
del app
gc.collect()
print("PASS: simulated Prepare -> Install -> "+
      ("Open Application" if open_requested else "Done")+
      " -> Close, process exit zero; sync="+str(sync_mode), flush=True)
