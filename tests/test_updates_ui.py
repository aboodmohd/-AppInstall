"""v1.8 PR #2: Updates page and deliberately scoped Flatpak operations."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch, Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["APPINSTALL_DISABLE_UPDATE_TIMER"] = "1"

from qt_compat import QtCore, QtWidgets
from PySide6 import QtQml, QtTest
import manager_qml
import update_engine


def app(key="flatpak:org.example.App", fmt="flatpak"):
    return {
        "key": key, "format": fmt, "name": "Example App",
        "version": "1.0", "status": "installed",
        "raw": {"appid": key.split(":", 1)[-1]} if fmt == "flatpak" else {},
    }


def candidate(key="flatpak:org.example.App", state="available"):
    return update_engine.UpdateCandidate(
        key=key, format=key.split(":", 1)[0], state=state,
        installed_version="1.0", available_version="2.0",
        source="flathub", mechanism="flatpak-ref",
        reference="app/org.example.App/x86_64/stable",
        installed_revision="a" * 64, available_revision="b" * 64,
        requires_review=state == "available",
    )


class UpdateModelTests(unittest.TestCase):
    def test_filter_and_roles_and_review_flag(self):
        model = manager_qml.UpdateModel()
        data = [
            app(),
            app("appimage:example", "appimage"),
            app("deb:gimp", "deb"),
        ]
        results = [
            candidate(),
            update_engine.UpdateCandidate(
                "appimage:example", "appimage", "manual-required", reason="Replace manually"),
            update_engine.UpdateCandidate(
                "deb:gimp", "deb", "error", reason="No owned Distrobox"),
        ]
        model.replace_results(data, results)
        self.assertEqual(model.count, 3)
        self.assertEqual(model.availableCount, 1)
        self.assertEqual(model.data(model.index(0, 0), model.ActionableRole), True)
        self.assertEqual(model.data(model.index(1, 0), model.ActionableRole), False)
        model.setFilter("manual-required")
        self.assertEqual(model.count, 1)
        self.assertEqual(model.data(model.index(0, 0), model.StateRole), "manual-required")
        model.setFilter("invalid-filter")
        self.assertEqual(model.count, 1)
        model.setFilter("all")
        self.assertEqual(model.count, 3)

    def test_empty_inventory_returns_zero(self):
        model = manager_qml.UpdateModel()
        model.replace_results([], [candidate()])
        self.assertEqual(model.count, 0)


class UpdateBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "XDG_DATA_HOME": str(Path(self.tmp.name) / "share"),
            "XDG_STATE_HOME": str(Path(self.tmp.name) / "state"),
            "APPINSTALL_DISABLE_UPDATE_TIMER": "1",
            "QT_QPA_PLATFORM": "offscreen",
        })
        self.env.start()
        self.anchor = QtWidgets.QWidget()
        self.bridge = manager_qml.Bridge(self.anchor)
        self.bridge.model.refresh_inventory([app()])

    def tearDown(self):
        for worker in (self.bridge._app_update_worker,
                       self.bridge._flatpak_preflight_worker):
            if worker is not None and worker.isRunning():
                worker.requestInterruption()
                self.assertTrue(worker.wait(2000))
        self.anchor.deleteLater()
        self.qapp.processEvents()
        self.env.stop()
        self.tmp.cleanup()

    def wait_scan(self):
        until = time.monotonic() + 5
        while self.bridge.appUpdatesBusy and time.monotonic() < until:
            self.qapp.processEvents()
            QtCore.QThread.msleep(10)
        self.qapp.processEvents()
        self.assertFalse(self.bridge.appUpdatesBusy)

    def test_read_only_check_populates_grid_without_any_update(self):
        with patch.object(manager_qml.manager, "inspect_application_updates",
                          return_value=[candidate()]) as check, \
             patch.object(self.bridge._flatpak_process, "start") as start:
            self.bridge.checkApplicationUpdates(True)
            self.wait_scan()
        check.assert_called_once()
        start.assert_not_called()
        self.assertEqual(self.bridge.updatesModel.availableCount, 1)
        self.assertEqual(self.bridge.updatesModel.count, 1)
        self.assertIn("1 app update(s)", self.bridge.appUpdatesStatus)

    def test_manual_and_error_states_cannot_start_flatpak_update(self):
        self.bridge.updatesModel.replace_results(
            [app()], [candidate(state="manual-required")])
        with patch.object(self.bridge._flatpak_process, "start") as start:
            self.bridge.requestFlatpakUpdate("flatpak:org.example.App")
        start.assert_not_called()
        self.assertIn("No verified", self.bridge.appUpdatesStatus)

    def test_invalid_revision_is_rejected_before_preflight(self):
        wrong = update_engine.UpdateCandidate(
            **{**candidate().to_dict(), "available_revision": "evil"})
        self.bridge.updatesModel.replace_results([app()], [wrong])
        with patch.object(self.bridge._flatpak_process, "start") as start:
            self.bridge.requestFlatpakUpdate("flatpak:org.example.App")
        start.assert_not_called()
        self.assertIn("invalid", self.bridge.appUpdatesStatus)

    def test_declined_preflight_never_starts_flatpak(self):
        prior = candidate()
        self.bridge._flatpak_pending_candidate = prior
        self.bridge._flatpak_pending_key = prior.key
        with patch.object(QtWidgets.QMessageBox, "question",
                          return_value=QtWidgets.QMessageBox.StandardButton.No), \
             patch.object(self.bridge._flatpak_process, "start") as start:
            self.bridge._flatpak_preflight_ready([candidate()])
        start.assert_not_called()
        self.assertIn("declined", self.bridge.appUpdatesStatus)

    def test_confirmation_pins_full_commit_and_only_selected_user_ref(self):
        prior = candidate()
        self.bridge._flatpak_pending_candidate = prior
        self.bridge._flatpak_pending_key = prior.key
        with patch.object(QtWidgets.QMessageBox, "question",
                          return_value=QtWidgets.QMessageBox.StandardButton.Yes), \
             patch.object(self.bridge._flatpak_process, "start") as start, \
             patch.object(self.bridge._flatpak_process, "closeWriteChannel"):
            self.bridge._flatpak_preflight_ready([candidate()])
        start.assert_called_once()
        cmd, argv = start.call_args.args
        self.assertEqual(cmd, "flatpak")
        self.assertEqual(argv[0], "update")
        self.assertIn("--user", argv)
        self.assertIn("--no-deps", argv)
        self.assertIn("--no-related", argv)
        self.assertIn("--commit=" + "b" * 64, argv)
        self.assertEqual(argv[-1], prior.reference)
        self.assertEqual(argv.count(prior.reference), 1)
        self.assertNotIn("--system", argv)
        self.assertEqual(len([a for a in argv if a.startswith("app/")]), 1)

    def test_unexpected_origin_or_changed_revision_refuses_update(self):
        prior = candidate()
        variants = [
            update_engine.UpdateCandidate(**{**prior.to_dict(), "source": "different"}),
            update_engine.UpdateCandidate(**{**prior.to_dict(), "available_revision": "c" * 64}),
            update_engine.UpdateCandidate(**{**prior.to_dict(), "state": "up-to-date"}),
        ]
        for fresh in variants:
            with self.subTest(fresh=fresh):
                self.bridge._flatpak_pending_candidate = prior
                self.bridge._flatpak_pending_key = prior.key
                with patch.object(self.bridge._flatpak_process, "start") as start:
                    self.bridge._flatpak_preflight_ready([fresh])
                start.assert_not_called()
                self.assertIn("Check again", self.bridge.appUpdatesStatus)

    def test_close_denied_during_running_update(self):
        with patch.object(self.bridge._flatpak_process, "state",
                          return_value=QtCore.QProcess.ProcessState.Running):
            self.assertFalse(self.bridge.allowClose())
        self.assertIn("before closing", self.bridge.appUpdatesStatus)

    def test_updates_tab_qml_is_accessible_and_hides_other_pages(self):
        engine = QtQml.QQmlApplicationEngine()
        engine.rootContext().setContextProperty("bridge", self.bridge)
        engine.rootContext().setContextProperty("appsModel", self.bridge.model)
        engine.addImportPath(str(manager_qml.QML_DIR.parent))
        engine.load(str(manager_qml.QML_DIR / "main.qml"))
        roots = engine.rootObjects()
        self.assertTrue(roots, "Updates QML failed to load")
        window = roots[0]
        try:
            for name in ("updatesTab", "applicationUpdatesPage",
                         "appUpdatesList", "appUpdateCheckButton",
                         "appUpdateCancelCheck", "appUpdateCancelInstall"):
                self.assertIsNotNone(window.findChild(QtCore.QObject, name), name)
            expr = lambda text: QtQml.QQmlExpression(
                QtQml.qmlContext(window), window, text).evaluate()[0]
            self.assertFalse(expr("applicationUpdatesPage.visible"))
            window.setProperty("updatesSelected", True)
            self.qapp.processEvents()
            self.assertTrue(expr("applicationUpdatesPage.visible"))
            self.assertFalse(expr("contentArea.visible"))
            self.assertFalse(expr("discoverPanel.visible"))
            self.assertFalse(expr("filtersPanel.visible"))
            self.assertTrue(expr("appMenuBar.visible"))
        finally:
            window.close()
            engine.deleteLater()
            self.qapp.processEvents()

    def test_rendered_update_cards_show_real_text_and_guard_review(self):
        """Regression: Qt6 required index suppressed old contextual model roles.

        The screenshot showed six empty rows with Review update buttons while
        the model reported zero updates. Inspect actual QML delegates, not just
        Python role values or static QML loading.
        """
        engine = QtQml.QQmlApplicationEngine()
        engine.rootContext().setContextProperty("bridge", self.bridge)
        engine.rootContext().setContextProperty("appsModel", self.bridge.model)
        engine.addImportPath(str(manager_qml.QML_DIR.parent))
        engine.load(str(manager_qml.QML_DIR / "main.qml"))
        self.assertTrue(engine.rootObjects(), "Updates page QML failed to load")
        window = engine.rootObjects()[0]
        window.show()
        window.setProperty("updatesSelected", True)

        def row_objects():
            QtTest.QTest.qWait(80)
            self.qapp.processEvents()
            return window.findChildren(QtCore.QObject, "updateAppRow")

        def visible_review_buttons():
            return [
                obj for obj in window.findChildren(
                    QtCore.QObject, "reviewFlatpakUpdateButton")
                if obj.property("visible")
            ]

        try:
            manual = update_engine.UpdateCandidate(
                key="flatpak:org.example.App", format="flatpak",
                state="manual-required", installed_version="1.0",
                reason="Manually replace the application.")
            self.bridge.updatesModel.replace_results([app()], [manual])
            self.assertEqual(self.bridge.updatesModel.availableCount, 0)
            self.assertTrue(row_objects(), "Update model failed to create a delegate")
            title = window.findChild(QtCore.QObject, "updateAppTitle")
            version = window.findChild(QtCore.QObject, "updateAppVersion")
            state = window.findChild(QtCore.QObject, "updateAppState")
            self.assertEqual(title.property("text"), "Example App · FLATPAK")
            self.assertEqual(version.property("text"), "1.0  →  —")
            self.assertEqual(state.property("text"), "manual-required")
            self.assertFalse(visible_review_buttons(),
                             "Review action exposed despite zero available updates")

            self.bridge.updatesModel.replace_results([app()], [candidate()])
            self.assertEqual(self.bridge.updatesModel.availableCount, 1)
            self.assertTrue(row_objects(), "Available update lost its delegate")
            self.assertEqual(
                window.findChild(QtCore.QObject, "updateAppTitle").property("text"),
                "Example App · FLATPAK")
            self.assertEqual(
                window.findChild(QtCore.QObject, "updateAppState").property("text"),
                "available")
            self.assertEqual(len(visible_review_buttons()), 1)
        finally:
            window.close()
            engine.deleteLater()
            self.qapp.processEvents()

    def test_no_action_on_unavailable_nonflatpak_row(self):
        """A DEB/RPM entry must never gain a Flatpak Review button."""
        for fmt, key in (("deb", "deb:gimp"), ("rpm", "rpm:gimp"),
                         ("appimage", "appimage:example")):
            with self.subTest(fmt=fmt):
                obj = update_engine.UpdateCandidate(
                    key=key, format=fmt, state="available",
                    installed_version="1.0", available_version="2.0",
                    requires_review=True)
                row = app(key, fmt)
                self.bridge.updatesModel.replace_results([row], [obj])
                index = self.bridge.updatesModel.index(0, 0)
                self.assertFalse(self.bridge.updatesModel.data(
                    index, self.bridge.updatesModel.ActionableRole))

    def test_legacy_update_menu_only_requests_review(self):
        # A v1.7 My Applications action must not bypass v1.8 approval.
        with patch.object(manager_qml.manager, "can_update", return_value=True), \
             patch.object(manager_qml.manager, "update_app") as direct, \
             patch.object(self.bridge, "requestFlatpakUpdate") as reviewed:
            self.bridge.updateApp("flatpak:org.example.App")
            direct.assert_not_called()
            reviewed.assert_not_called()
            self.assertIn("Updates tab", self.bridge.statusText)

        self.bridge.updatesModel.replace_results([app()], [candidate()])
        with patch.object(manager_qml.manager, "can_update", return_value=True), \
             patch.object(manager_qml.manager, "update_app") as direct, \
             patch.object(self.bridge, "requestFlatpakUpdate") as reviewed:
            self.bridge.updateApp("flatpak:org.example.App")
        reviewed.assert_called_once_with("flatpak:org.example.App")
        direct.assert_not_called()

    def test_self_update_state_is_independent_of_application_updates(self):
        self.bridge._update_tag = "v1.7.1"
        self.bridge.updatesModel.replace_results([app()], [candidate()])
        self.assertEqual(self.bridge.updateTag, "v1.7.1")
        self.assertEqual(self.bridge.updatesModel.availableCount, 1)


if __name__ == "__main__":
    unittest.main()
