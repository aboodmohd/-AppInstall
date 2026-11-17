"""Qt UI tests for AppImage two-stage consent and review (no real downloads)."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["APPINSTALL_DISABLE_UPDATE_TIMER"] = "1"

from qt_compat import QtCore, QtWidgets
import appimage_updates
import manager_qml
import update_engine


INFO = "gh-releases-zsync|ExampleOrg|ExampleProject|latest|Example-*.AppImage.zsync"


def managed():
    raw = dict(
        format="appimage", name="Example", status="installed",
        desktop="/example/managed.desktop", manifest="/example/ab123.json")
    return {
        "key": "appimage:ab123", "name": "Example", "version": "unknown",
        "format": "appimage", "status": "installed",
        "source": "launch-monitor", "raw": raw,
        "target": "/example/.appinstall-123/Example.AppImage",
    }


def candidate():
    return update_engine.UpdateCandidate(
        key="appimage:ab123", format="appimage", state="available",
        mechanism="appimage-zsync", source="GitHub Releases zsync",
        reference=INFO, installed_revision="a" * 64,
        available_version="New upstream build", requires_review=True)


def plan():
    return appimage_updates.AppImagePlan(
        key="appimage:ab123", target="/example/.appinstall-123/Example.AppImage",
        staging="/example/.appinstall-123/.appinstall-update-abc",
        staged_file="/example/.appinstall-123/.appinstall-update-abc/Example.AppImage",
        original_sha256="a" * 64, candidate_sha256="b" * 64,
        original_size=5000, candidate_size=6200,
        update_information=INFO, source="GitHub Releases zsync")


class AppImageGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {
            "XDG_DATA_HOME": str(Path(self.tmp.name) / "share"),
            "XDG_STATE_HOME": str(Path(self.tmp.name) / "state"),
            "QT_QPA_PLATFORM": "offscreen",
            "APPINSTALL_DISABLE_UPDATE_TIMER": "1",
        })
        env.start()
        self.addCleanup(env.stop)
        self.anchor = QtWidgets.QWidget()
        self.bridge = manager_qml.Bridge(self.anchor)
        self.bridge.model.refresh_inventory([managed()])
        self.bridge.updatesModel.replace_results([managed()], [candidate()])
        self.addCleanup(self.anchor.deleteLater)

    def test_appimage_update_is_actionable_only_for_valid_verified_info(self):
        model = self.bridge.updatesModel
        i = model.index(0, 0)
        self.assertTrue(model.data(i, model.ActionableRole))
        for bad in (
            {"state": "manual-required"},
            {"requires_review": False},
            {"reference": ""},
            {"installed_revision": "not-a-sha"},
            {"mechanism": "appimage-upd-info"},
        ):
            item = update_engine.UpdateCandidate(
                **{**candidate().to_dict(), **bad})
            model.replace_results([managed()], [item])
            self.assertFalse(model.data(model.index(0, 0), model.ActionableRole),
                             str(bad))

    def test_declining_initial_download_does_not_start_worker(self):
        with patch.object(QtWidgets.QMessageBox, "question",
                          return_value=QtWidgets.QMessageBox.StandardButton.No), \
             patch.object(manager_qml, "AppImagePrepareWorker") as worker:
            self.bridge.requestManagedUpdate("appimage:ab123")
        worker.assert_not_called()
        self.assertIn("declined", self.bridge.appUpdatesStatus)

    def test_accepting_download_prepares_only_one_managed_appimage(self):
        with patch.object(QtWidgets.QMessageBox, "question",
                          return_value=QtWidgets.QMessageBox.StandardButton.Yes), \
             patch.object(manager_qml.AppImagePrepareWorker, "start") as start:
            self.bridge.requestManagedUpdate("appimage:ab123")
        start.assert_called_once_with()
        self.assertEqual(self.bridge._appimage_prepare_worker.app["key"],
                         "appimage:ab123")
        self.assertEqual(self.bridge._appimage_prepare_worker.candidate.reference, INFO)
        self.assertTrue(self.bridge.appImagePreparing)
        self.bridge._appimage_prepare_worker = None
        self.bridge._appimage_pending_key = None
        self.bridge._set_app_update_busy(False)

    def test_declining_staged_replacement_cleans_up_no_install(self):
        self.bridge._appimage_pending_key = "appimage:ab123"
        self.bridge._appimage_pending_app = managed()
        self.bridge._appimage_pending_candidate = candidate()
        with patch.object(QtWidgets.QDialog, "exec",
                          return_value=QtWidgets.QDialog.DialogCode.Rejected), \
             patch.object(appimage_updates, "cleanup_plan") as cleanup, \
             patch.object(manager_qml, "AppImageApplyWorker") as apply:
            self.bridge._appimage_prepare_ready(plan())
        cleanup.assert_called_once()
        apply.assert_not_called()
        self.assertIn("declined", self.bridge.appUpdatesStatus)

    def test_staged_hash_or_channel_changed_blocks_approval_dialog(self):
        self.bridge._appimage_pending_key = "appimage:ab123"
        self.bridge._appimage_pending_app = managed()
        self.bridge._appimage_pending_candidate = candidate()
        for invalid in (
            {"original_sha256": "b" * 64},
            {"update_information": "other-upstream-source"},
            {"key": "appimage:foreign"},
        ):
            with self.subTest(invalid=invalid), \
                 patch.object(QtWidgets.QDialog, "exec") as dialog, \
                 patch.object(appimage_updates, "cleanup_plan") as cleanup, \
                 patch.object(manager_qml, "AppImageApplyWorker") as apply:
                stage = appimage_updates.AppImagePlan(**{**plan().__dict__, **invalid})
                self.bridge._appimage_prepare_ready(stage)
                dialog.assert_not_called()
                apply.assert_not_called()
                cleanup.assert_called_once_with(stage)

    def test_final_approval_only_starts_staged_apply_worker(self):
        self.bridge._appimage_pending_key = "appimage:ab123"
        self.bridge._appimage_pending_app = managed()
        self.bridge._appimage_pending_candidate = candidate()
        with patch.object(QtWidgets.QDialog, "exec",
                          return_value=QtWidgets.QDialog.DialogCode.Accepted), \
             patch.object(manager_qml.AppImageApplyWorker, "start") as start:
            self.bridge._appimage_prepare_ready(plan())
        start.assert_called_once_with()
        self.assertEqual(self.bridge._appimage_apply_worker.plan.key,
                         "appimage:ab123")
        self.assertEqual(self.bridge._appimage_apply_worker.plan.original_sha256,
                         "a" * 64)
        self.bridge._appimage_apply_worker = None

    def test_staging_blocks_window_close_and_cancel_check_not_available(self):
        worker = manager_qml.AppImagePrepareWorker(managed(), candidate())
        self.bridge._appimage_prepare_worker = worker
        self.bridge._appimage_pending_key = "appimage:ab123"
        self.bridge._set_app_update_busy(True)
        with patch.object(worker, "isRunning", return_value=True):
            self.assertFalse(self.bridge.allowClose())
        self.assertIn("download is still staging", self.bridge.appUpdatesStatus)
        self.assertTrue(self.bridge.appImagePreparing)
        self.bridge._appimage_prepare_worker = None
        self.bridge._appimage_pending_key = None
        self.bridge._set_app_update_busy(False)


if __name__ == "__main__":
    unittest.main()
