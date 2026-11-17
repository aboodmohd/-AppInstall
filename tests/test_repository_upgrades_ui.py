"""Qt Updates page integration for reviewed DEB/RPM Distrobox updates."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["APPINSTALL_DISABLE_UPDATE_TIMER"] = "1"
from qt_compat import QtCore, QtWidgets

import manager_qml
import update_engine
import repository_upgrades
import container_backend


def managed(kind="deb"):
    container, image = container_backend.SPECS[kind]
    raw = dict(kind=kind, name="gimp", version="3.0-1",
               container=container, image=image, install_method="repository",
               status="installed", architecture="amd64" if kind == "deb" else "x86_64")
    return dict(key=kind + ":gimp", format=kind, name="GIMP",
                source="container-registry", version="3.0-1",
                status="installed", raw=raw)


def candidate(kind="deb"):
    return update_engine.UpdateCandidate(
        key=kind + ":gimp", format=kind, state="available",
        installed_version="3.0-1", available_version="3.2-1",
        source="Debian 13" if kind == "deb" else "Fedora 44",
        mechanism="apt-repository" if kind == "deb" else "dnf-repository",
        requires_review=True)


def plan(kind="deb"):
    container, image = container_backend.SPECS[kind]
    return repository_upgrades.UpgradePlan(
        key=kind + ":gimp", kind=kind, name="gimp",
        container=container, image=image,
        installed_version="3.0-1", target_version="3.2-1",
        architecture="amd64" if kind == "deb" else "x86_64",
        preview="Inst gimp [3.0-1] (3.2-1)\n" if kind == "deb"
                else "Upgrading:\n gimp 3.2-1\nTransaction Summary\n",
        preview_sha256="not-executable-from-ui",
        package_spec="gimp=3.2-1" if kind == "deb" else "gimp-3.2-1.x86_64")


class ReviewPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {
            "XDG_DATA_HOME": str(Path(self.tmp.name)/"share"),
            "XDG_STATE_HOME": str(Path(self.tmp.name)/"state"),
            "APPINSTALL_DISABLE_UPDATE_TIMER": "1"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.anchor = QtWidgets.QWidget()
        self.bridge = manager_qml.Bridge(self.anchor)
        self.addCleanup(self.anchor.deleteLater)
        self.bridge.model.refresh_inventory([managed("deb")])

    def test_actionable_repo_only_when_exact_provenance_matches(self):
        model = self.bridge.updatesModel
        app = managed("deb")
        model.replace_results([app], [candidate("deb")])
        i = model.index(0, 0)
        self.assertTrue(model.data(i, model.ActionableRole))
        for c in (
            update_engine.UpdateCandidate(
                **{**candidate("deb").to_dict(), "mechanism": "manual"}),
            update_engine.UpdateCandidate(
                **{**candidate("deb").to_dict(), "state": "manual-required"}),
            update_engine.UpdateCandidate(
                **{**candidate("deb").to_dict(), "requires_review": False}),
        ):
            model.replace_results([app], [c])
            self.assertFalse(model.data(model.index(0, 0), model.ActionableRole))
        model.replace_results([managed("rpm")], [candidate("rpm")])
        self.assertTrue(model.data(model.index(0, 0), model.ActionableRole))

    def test_foreign_package_and_errors_cannot_open_review(self):
        for fmt in ("deb", "rpm"):
            app = managed(fmt)
            self.bridge.model.refresh_inventory([app])
            c = candidate(fmt)
            self.bridge.updatesModel.replace_results([app], [c])
            with patch.object(manager_qml, "RepositoryPreviewWorker") as worker:
                forged = dict(app, source="launch-monitor")
                self.bridge.model.refresh_inventory([forged])
                self.bridge.requestManagedUpdate(app["key"])
                worker.assert_not_called()
                self.assertIn("Repository origin changed", self.bridge.appUpdatesStatus)
            with patch.object(manager_qml, "RepositoryPreviewWorker") as worker:
                self.bridge.updatesModel.replace_results(
                    [app], [update_engine.UpdateCandidate(
                        **{**c.to_dict(), "state": "error"})])
                self.bridge.requestManagedUpdate(app["key"])
                worker.assert_not_called()

    def test_rejected_review_has_no_apply_worker(self):
        app = managed("deb")
        self.bridge._repository_pending_key = app["key"]
        self.bridge._repository_pending_app = app
        self.bridge._repository_pending_candidate = candidate("deb")
        with patch.object(QtWidgets.QDialog, "exec",
                          return_value=QtWidgets.QDialog.DialogCode.Rejected), \
             patch.object(manager_qml, "RepositoryApplyWorker") as worker:
            self.bridge._repository_preview_ready(plan("deb"))
            worker.assert_not_called()
        self.assertIn("declined", self.bridge.appUpdatesStatus)

    def test_changed_candidate_before_review_never_executes(self):
        app = managed("rpm")
        self.bridge._repository_pending_key = app["key"]
        self.bridge._repository_pending_app = app
        self.bridge._repository_pending_candidate = candidate("rpm")
        changed = repository_upgrades.UpgradePlan(
            **{**plan("rpm").__dict__, "target_version": "3.3-1"})
        with patch.object(QtWidgets.QDialog, "exec") as prompt, \
             patch.object(manager_qml, "RepositoryApplyWorker") as apply:
            self.bridge._repository_preview_ready(changed)
        prompt.assert_not_called()
        apply.assert_not_called()
        self.assertIn("changed", self.bridge.appUpdatesStatus)

    def test_confirmed_update_sends_single_app_to_background_worker(self):
        app = managed("deb")
        self.bridge._repository_pending_key = app["key"]
        self.bridge._repository_pending_app = app
        self.bridge._repository_pending_candidate = candidate("deb")
        with patch.object(QtWidgets.QDialog, "exec",
                          return_value=QtWidgets.QDialog.DialogCode.Accepted), \
             patch.object(manager_qml.RepositoryApplyWorker, "start") as start:
            self.bridge._repository_preview_ready(plan("deb"))
        start.assert_called_once_with()
        self.assertEqual(self.bridge._repository_apply_worker.plan.key, app["key"])
        self.assertEqual(self.bridge._repository_apply_worker.app["key"], app["key"])
        self.bridge._repository_apply_worker = None

    def test_repo_is_not_stoppable_via_flatpak_control(self):
        dummy = manager_qml.RepositoryApplyWorker(plan("deb"), managed("deb"))
        self.bridge._repository_apply_worker = dummy
        # Verify the Flatpak stop control is independently guarded.
        with patch.object(self.bridge._flatpak_process, "state",
                          return_value=QtCore.QProcess.ProcessState.NotRunning), \
             patch.object(QtWidgets.QMessageBox, "question") as ask:
            self.bridge.cancelRunningFlatpakUpdate()
            ask.assert_not_called()
        self.bridge._repository_apply_worker = None


if __name__ == "__main__":
    unittest.main()
