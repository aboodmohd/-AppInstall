"""QML manager prototype tests.

Covers the redesigned My Applications screen in Qt Quick: the bridge loads
the inventory through the normal InventoryLoader entry point, every action
routes through the existing manager backend functions and dialogs, the
AppModel exposes the roles the QML reads, and main.qml instantiates without
QML errors. Registry, settings and package files live under a disposable
XDG tree; Flatpak inventory queries are patched so results never depend on
the host's Flatpak installation; the update helper runs through a patched
QProcess.
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6 import QtCore, QtQml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location('manager', ROOT / 'manager.py')
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)
sys.modules['manager'] = manager

spec = importlib.util.spec_from_file_location('manager_qml', ROOT / 'manager_qml.py')
manager_qml = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager_qml)
sys.modules['manager_qml'] = manager_qml


def write_registry(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2))


class QmlLoadCapture:
    """Collect Qt message-handler warnings for a QML load."""

    def __init__(self):
        self.messages = []

    def __enter__(self):
        self._previous = QtCore.qInstallMessageHandler(self._handle)
        return self

    def __exit__(self, *exc):
        QtCore.qInstallMessageHandler(self._previous)

    def _handle(self, mode, context, message):
        self.messages.append(message)


class QmlManagerBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.environment = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_STATE_HOME': str(self.root / 'state'),
            'QT_QPA_PLATFORM': 'offscreen',
        })
        self.environment.start()
        from qt_compat import QtWidgets
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        self.anchor = QtWidgets.QWidget()
        self.bridge = manager_qml.Bridge(self.anchor)
        self.model = self.bridge.model

    def tearDown(self):
        self.anchor.deleteLater()
        self.app.processEvents()
        self.environment.stop()
        self.temp.cleanup()

    def stage_installed_appimage(self, key, name, **overrides):
        """Real target and desktop files so the record validates as installed."""
        stem = key.split(':', 1)[-1]
        target = self.root / 'apps' / (stem + '.AppImage')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'\x7fELF-managed-appimage')
        desktop = self.root / 'entries' / (stem + '.desktop')
        desktop.parent.mkdir(parents=True, exist_ok=True)
        desktop.write_text('[Desktop Entry]\nType=Application\nName=' + name + '\n')
        record = dict(format='appimage', name=name, version='1.0',
                      desktop=str(desktop), icon='', icon_name=stem,
                      container=None, manifest=None, target=str(target),
                      description='An example application.', status='installed')
        record.update(overrides)
        return record

    def load_inventory(self, raw_records):
        """Push a hand-built inventory through the normal record builder."""
        apps = []
        for key, raw in raw_records:
            apps.append(manager.build_app_record(key, raw, 'test'))
        self.bridge.model.refresh_inventory(apps)
        return apps


class AppModelTests(QmlManagerBase):
    def test_roles_expose_record_shape(self):
        self.load_inventory([
            ('appimage:example', self.stage_installed_appimage('appimage:example', 'Example App')),
        ])
        index = self.model.index(0, 0)
        self.assertEqual(self.model.data(index, self.model.NameRole), 'Example App')
        self.assertEqual(self.model.data(index, self.model.FormatLabelRole), 'AppImage')
        self.assertEqual(self.model.data(index, self.model.StatusLabelRole), 'Installed')
        self.assertEqual(self.model.data(index, self.model.StatusToneRole), 'success')
        self.assertTrue(self.model.data(index, self.model.CanOpenRole))
        self.assertTrue(self.model.data(index, self.model.CanUninstallRole))
        self.assertFalse(self.model.data(index, self.model.IsContainerRole))
        self.assertEqual(self.model.data(index, self.model.InitialRole), 'E')
        self.assertEqual(self.model.data(index, self.model.ProblemsRole), '')

    def test_container_record_flags_and_tone(self):
        raw = dict(format='deb', name='Deb App', version='2.0',
                   desktop='/home/user/.local/share/applications/deb.desktop',
                   icon='', icon_name='deb', container='debian-apps',
                   manifest=None, target='/tmp/x.deb', description='',
                   status='needs-repair')
        self.load_inventory([('deb:deb-app', raw)])
        index = self.model.index(0, 0)
        self.assertTrue(self.model.data(index, self.model.IsContainerRole))
        self.assertEqual(self.model.data(index, self.model.StatusToneRole), 'warning')
        self.assertEqual(self.model.data(index, self.model.StatusLabelRole), 'Needs repair')

    def test_search_filters_name_and_key(self):
        self.load_inventory([
            ('appimage:example', self.stage_installed_appimage('appimage:example', 'Example App')),
            ('appimage:other', self.stage_installed_appimage('appimage:other', 'Other Tool')),
        ])
        self.model.setSearch('other')
        self.assertEqual(self.model.rowCount(), 1)
        self.model.setSearch('OTHER')
        self.assertEqual(self.model.rowCount(), 1)
        self.model.setSearch('')
        self.assertEqual(self.model.rowCount(), 2)

    def test_format_and_status_filters(self):
        self.load_inventory([
            ('appimage:example', self.stage_installed_appimage('appimage:example', 'Example App')),
            ('appimage:broken', self.stage_installed_appimage(
                'appimage:broken', 'Broken App', status='needs-repair')),
        ])
        self.model.setFormatFilter('appimage')
        self.model.setStatusFilter('needs-repair')
        self.assertEqual(self.model.rowCount(), 1)
        self.assertEqual(self.model.data(self.model.index(0, 0), self.model.NameRole),
                         'Broken App')
        self.model.setFormatFilter('all')
        self.model.setStatusFilter('all')
        self.assertEqual(self.model.rowCount(), 2)

    def test_sort_orders(self):
        self.load_inventory([
            ('appimage:beta', self.stage_installed_appimage('appimage:beta', 'Beta')),
            ('appimage:alpha', self.stage_installed_appimage('appimage:alpha', 'Alpha')),
        ])
        self.model.setSort('name-desc')
        names = [self.model.data(self.model.index(i, 0), self.model.NameRole)
                 for i in range(self.model.rowCount())]
        self.assertEqual(names, ['Beta', 'Alpha'])
        self.model.setSort('name-asc')
        names = [self.model.data(self.model.index(i, 0), self.model.NameRole)
                 for i in range(self.model.rowCount())]
        self.assertEqual(names, ['Alpha', 'Beta'])

    def test_favorites_sort_first(self):
        self.load_inventory([
            ('appimage:beta', self.stage_installed_appimage('appimage:beta', 'Beta')),
            ('appimage:alpha', self.stage_installed_appimage('appimage:alpha', 'Alpha')),
        ])
        self.model.set_favorites({'appimage:beta'})
        self.assertEqual(self.model.data(self.model.index(0, 0), self.model.KeyRole),
                         'appimage:beta')
        self.assertTrue(self.model.data(self.model.index(0, 0), self.model.PinnedRole))


class BridgeEntryPointsTests(QmlManagerBase):
    def setUp(self):
        super().setUp()
        self.apps = self.load_inventory([
            ('appimage:example', self.stage_installed_appimage('appimage:example', 'Example App')),
        ])

    def test_open_app_routes_through_manager(self):
        with patch.object(manager, 'open_app') as open_app:
            self.bridge.openApp('appimage:example')
        open_app.assert_called_once_with(self.apps[0])

    def test_reinstall_routes_through_manager(self):
        with patch.object(manager, 'reinstall_app', return_value='reinstalled') as reinstall, \
             patch.object(self.bridge, 'refresh') as refresh:
            self.bridge.reinstallApp('appimage:example')
        reinstall.assert_called_once_with(self.apps[0])
        refresh.assert_called_once()
        self.assertEqual(self.bridge._status_text, 'reinstalled')

    def test_update_app_gates_on_can_update(self):
        with patch.object(manager, 'can_update', return_value=False):
            self.bridge.updateApp('appimage:example')
        self.assertIn('not supported', self.bridge._status_text)

    def test_update_app_routes_through_manager(self):
        with patch.object(manager, 'can_update', return_value=True), \
             patch.object(manager, 'update_app', return_value='updated') as update, \
             patch.object(self.bridge, 'refresh'):
            self.bridge.updateApp('appimage:example')
        update.assert_called_once_with(self.apps[0])
        self.assertEqual(self.bridge._status_text, 'updated')

    def test_backend_failure_is_reported_not_raised(self):
        error = RuntimeError('target file vanished')
        with patch.object(manager, 'open_app', side_effect=error):
            self.bridge.openApp('appimage:example')
        self.assertIn('Could not launch', self.bridge._status_text)
        self.assertIn('target file vanished', self.bridge._status_text)

    def test_show_details_uses_existing_dialog(self):
        with patch.object(manager, 'AppDetailsDialog') as dialog:
            instance = dialog.return_value
            self.bridge.showDetails('appimage:example')
        dialog.assert_called_once_with(self.apps[0], self.anchor)
        instance.open.assert_called_once()

    def test_uninstall_opens_existing_dialog_and_passes_selection(self):
        cleanup = [Path('/tmp/keep-me')]
        with patch.object(manager, 'can_uninstall', return_value=True), \
             patch.object(manager, 'uninstall_cleanup_items', return_value=cleanup) as items, \
             patch.object(manager, 'UninstallDialog') as dialog, \
             patch.object(manager, 'uninstall_app', return_value='removed') as uninstall, \
             patch.object(self.bridge, 'refresh'):
            instance = dialog.return_value
            instance.selected_paths.return_value = ['/tmp/stale-file']
            self.bridge.uninstallApp('appimage:example')
            # The bridge wires itself to the dialog's accepted signal; fire it.
            accepted = instance.accepted.connect.call_args[0][0]
            accepted()
        items.assert_called_once_with(self.apps[0])
        dialog.assert_called_once_with(self.apps[0], cleanup, self.anchor)
        instance.open.assert_called_once()
        uninstall.assert_called_once_with(self.apps[0], cleanup=set(['/tmp/stale-file']))

    def test_uninstall_refused_when_backend_refuses(self):
        with patch.object(manager, 'can_uninstall', return_value=False), \
             patch.object(manager, 'UninstallDialog') as dialog:
            self.bridge.uninstallApp('appimage:example')
        dialog.assert_not_called()
        self.assertIn('not supported', self.bridge._status_text)

    def test_repair_routes_through_manager(self):
        with patch.object(manager, 'repair_launcher', return_value='repaired') as repair, \
             patch.object(self.bridge, 'refresh'):
            self.bridge.repairApp('appimage:example')
        repair.assert_called_once_with(self.apps[0])

    def test_logs_report_when_missing(self):
        with patch.object(manager, '_show_log') as show_log:
            self.bridge.showLogs('appimage:example')
        show_log.assert_not_called()
        self.assertIn('No launch log', self.bridge._status_text)

    def test_health_opens_existing_dialog(self):
        report = {'container': 'debian-apps', 'checks': []}
        with patch.object(manager, 'container_health_report', return_value=report) as health, \
             patch.object(manager, 'HealthDialog') as dialog:
            instance = dialog.return_value
            self.bridge.showHealth('appimage:example')
        health.assert_called_once_with(self.apps[0])
        dialog.assert_called_once_with(self.apps[0], report, self.anchor)
        instance.open.assert_called_once()

    def test_health_refused_for_non_container(self):
        with patch.object(manager, 'container_health_report', return_value=None), \
             patch.object(manager, 'HealthDialog') as dialog:
            self.bridge.showHealth('appimage:example')
        dialog.assert_not_called()
        self.assertIn('not tracked', self.bridge._status_text)

    def test_container_repair_routes_through_manager(self):
        with patch.object(manager, 'repair_container_app', return_value='ok') as repair, \
             patch.object(self.bridge, 'refresh'):
            self.bridge.repairContainer('appimage:example')
        repair.assert_called_once_with(self.apps[0])

    def test_reexport_routes_through_manager(self):
        with patch.object(manager, 'reexport_launcher', return_value='ok') as reexport, \
             patch.object(self.bridge, 'refresh'):
            self.bridge.reexportLauncher('appimage:example')
        reexport.assert_called_once_with(self.apps[0])


class BridgeDropTests(QmlManagerBase):
    def setUp(self):
        super().setUp()
        package = self.root / 'drops' / 'sample.deb'
        package.parent.mkdir(parents=True, exist_ok=True)
        package.write_bytes(b'\xde\xbb')
        self.package = str(package)
        self.not_package = str(self.root / 'drops' / 'note.txt')
        Path(self.not_package).write_text('hello')

    def test_drop_acceptable_uses_package_classification(self):
        self.assertTrue(self.bridge.dropAcceptable([self.package]))
        self.assertFalse(self.bridge.dropAcceptable([self.not_package]))
        self.assertFalse(self.bridge.dropAcceptable([]))

    def test_drop_opens_existing_batch_dialog(self):
        with patch.object(manager, 'BatchQueue') as queue, \
             patch.object(manager, 'BatchQueueDialog') as dialog:
            self.bridge.dropPackages([self.package, self.not_package])
        queue.assert_called_once_with([self.package])
        dialog.return_value.show.assert_called_once()

    def test_drop_appends_to_open_batch_dialog(self):
        existing = Mock()
        existing.isVisible.return_value = True
        self.bridge._batch_dialog = existing
        self.bridge.dropPackages([self.package])
        existing.append.assert_called_once_with([self.package])
        existing.raise_.assert_called_once()

    def test_drop_of_unsupported_files_reports(self):
        self.bridge.dropPackages([self.not_package])
        self.assertIn('No supported package files', self.bridge._status_text)


class BridgeUpdateTests(QmlManagerBase):
    def setUp(self):
        super().setUp()
        self.process = self.bridge._update_process
        self.process.start = Mock()
        self.process.readAll = Mock(return_value=QtCore.QByteArray(b''))

    def test_check_runs_the_desktop_helper(self):
        self.bridge.checkUpdates(True)
        args = self.process.start.call_args[0]
        self.assertEqual(args[1], [str(self.bridge._update_helper), '--desktop-check'])
        self.assertEqual(self.bridge._update_status, 'Checking for updates…')

    def test_available_tag_is_surfaced(self):
        self.process.readAll.return_value = QtCore.QByteArray(
            b'APPINSTALL_UPDATE=v1.4.1\n')
        self.bridge._update_operation = 'check'
        self.bridge._update_finished(0, QtCore.QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.bridge.updateTag, 'v1.4.1')
        self.assertIn('v1.4.1 is available', self.bridge._update_status)

    def test_up_to_date_reported(self):
        self.bridge._update_operation = 'check'
        self.bridge._update_finished(0, QtCore.QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.bridge._update_status, 'AppInstall is up to date')

    def test_install_runs_the_desktop_helper(self):
        self.bridge._update_tag = 'v1.4.1'
        self.process.readAll.return_value = QtCore.QByteArray(
            b'APPINSTALL_UPDATED=v1.4.1\n')
        self.bridge.installUpdate()
        args = self.process.start.call_args[0]
        self.assertEqual(args[1], [str(self.bridge._update_helper),
                                   '--desktop-update', 'v1.4.1'])
        self.bridge._update_finished(0, QtCore.QProcess.ExitStatus.NormalExit)
        self.assertIn('installed', self.bridge._update_status)
        self.assertEqual(self.bridge.updateTag, '')

    def test_install_failure_reported(self):
        self.bridge._update_tag = 'v1.4.1'
        self.process.readAll.return_value = QtCore.QByteArray(b'')
        self.bridge.installUpdate()
        self.bridge._update_finished(1, QtCore.QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.bridge._update_status, 'Update did not complete')
        # The banner stays visible so the action remains reachable.
        self.assertTrue(self.bridge.updateTag)


class ThemeTests(QmlManagerBase):
    def test_theme_setting_persists_and_flips_dark(self):
        with patch.dict(os.environ, {'QT_QPA_PLATFORM': 'offscreen'}):
            self.bridge.setTheme('dark')
        self.assertEqual(manager_qml.settings.read().get('theme'), 'dark')
        self.assertTrue(self.bridge.dark)
        self.bridge.setTheme('light')
        self.assertFalse(self.bridge.dark)


class InventoryLoadTests(QmlManagerBase):
    def test_refresh_uses_the_normal_loader(self):
        registry = self.root / 'data' / 'appinstall' / 'containers' / 'registry.json'
        write_registry(registry, {
            'appimage:example': self.stage_installed_appimage('appimage:example', 'Example App'),
        })
        with patch.object(manager, '_flatpak_installed', return_value=False):
            self.bridge.refresh()
            # InventoryLoader is a real QThread; pump until the done signal
            # lands on the main thread.
            import time
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                self.app.processEvents()
                if self.model.rowCount() == 1 and \
                        self.bridge._status_text != 'Loading…':
                    break
                time.sleep(0.02)
        self.assertEqual(self.model.rowCount(), 1)
        self.assertEqual(self.model.data(self.model.index(0, 0), self.model.NameRole),
                         'Example App')
        self.assertEqual(self.bridge._status_text,
                         '1 application managed by AppInstall')

    def test_load_failure_reports_in_status(self):
        self.bridge._load_failed('registry unreadable')
        self.assertIn('Could not load inventory', self.bridge._status_text)


class QmlInstantiationTests(QmlManagerBase):
    def test_main_qml_loads_without_errors(self):
        engine = QtQml.QQmlApplicationEngine()
        engine.rootContext().setContextProperty('bridge', self.bridge)
        engine.rootContext().setContextProperty('appsModel', self.model)
        engine.addImportPath(str(manager_qml.QML_DIR.parent))
        with QmlLoadCapture() as capture:
            engine.load(str(manager_qml.QML_DIR / 'main.qml'))
        try:
            self.assertTrue(engine.rootObjects(), 'main.qml failed to load')
            warnings = [m for m in capture.messages
                        if 'error' in m.lower() or 'invalid' in m.lower()
                        or 'unavailable' in m.lower() or 'Cannot assign' in m]
            self.assertEqual(warnings, [])
        finally:
            for root in engine.rootObjects():
                root.deleteLater()
            engine.deleteLater()


if __name__ == '__main__':
    unittest.main()
