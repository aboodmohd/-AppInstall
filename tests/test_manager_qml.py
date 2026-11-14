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
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6 import QtCore, QtQml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qt_compat import QtWidgets  # noqa: E402  (path first, then Qt modules)

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
            # Auto update checks are a production feature; tests drive the
            # slots directly and must never touch the real helper.
            'APPINSTALL_DISABLE_UPDATE_TIMER': '1',
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
        with patch.object(QtWidgets, 'QMessageBox'):
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

    def test_auto_check_respects_the_ttl(self):
        manager_qml.settings.update('last_update_check', int(time.time()))
        self.bridge.checkUpdates(False)
        self.process.start.assert_not_called()
        self.assertEqual(self.bridge.updateStatus, 'Update status has not been checked')
        self.assertTrue(self.bridge.actionVisible)

    def test_reopening_restores_successful_check_result(self):
        for output, tag, status in (
            (b'APPINSTALL_UPDATE=v1.4.1\n', 'v1.4.1', 'AppInstall v1.4.1 is available'),
            (b'', '', 'AppInstall is up to date'),
        ):
            with self.subTest(tag=tag):
                self.process.readAll.return_value = QtCore.QByteArray(output)
                self.bridge._update_operation = 'check'
                self.bridge._update_finished(0, QtCore.QProcess.ExitStatus.NormalExit)
                reopened = manager_qml.Bridge(self.anchor)
                with patch.object(reopened._update_process, 'start') as start, \
                     patch.object(reopened, '_notify_update') as notify:
                    reopened.checkUpdates(False)
                start.assert_not_called()
                notify.assert_not_called()
                self.assertEqual(reopened.updateTag, tag)
                self.assertEqual(reopened.updateStatus, status)
                self.assertTrue(reopened.actionVisible)

    def test_reopening_after_failed_check_is_neutral_and_manual_check_works(self):
        # A failure must also invalidate an earlier cached success.
        self.process.readAll.return_value = QtCore.QByteArray(
            b'APPINSTALL_UPDATE=v1.4.1\n')
        self.bridge._update_operation = 'check'
        self.bridge._update_finished(0, QtCore.QProcess.ExitStatus.NormalExit)
        self.bridge._update_operation = 'check'
        self.process.readAll.return_value = QtCore.QByteArray(b'network failure')
        self.bridge._update_finished(1, QtCore.QProcess.ExitStatus.NormalExit)
        reopened = manager_qml.Bridge(self.anchor)
        with patch.object(reopened._update_process, 'start') as start:
            reopened.checkUpdates(False)
            start.assert_not_called()
            self.assertEqual(reopened.updateTag, '')
            self.assertEqual(reopened.updateStatus, 'Update status has not been checked')
            self.assertTrue(reopened.actionVisible)
            reopened.checkUpdates(True)
            start.assert_called_once()

    def test_auto_check_runs_once_the_ttl_elapses(self):
        elapsed = int(manager.UPDATE_TTL_SECONDS) + 60
        manager_qml.settings.update('last_update_check', int(time.time()) - elapsed)
        self.bridge.checkUpdates(False)
        self.process.start.assert_called_once()

    def test_check_records_last_update_check_for_the_ttl(self):
        self.bridge._update_operation = 'check'
        self.bridge._update_finished(0, QtCore.QProcess.ExitStatus.NormalExit)
        self.assertGreater(manager_qml.settings.read().get('last_update_check', 0), 0)

    def test_available_update_notifies_per_user_settings(self):
        manager_qml.settings.update('notifications', True)
        self.process.readAll.return_value = QtCore.QByteArray(
            b'APPINSTALL_UPDATE=v1.4.1\n')
        self.bridge._update_operation = 'check'
        with patch.object(manager_qml.subprocess, 'run') as run:
            self.bridge._update_finished(0, QtCore.QProcess.ExitStatus.NormalExit)
        run.assert_called_once()
        self.assertIn('notify-send', run.call_args[0][0])

    def test_notifications_disabled_means_no_notify_send(self):
        manager_qml.settings.update('notifications', False)
        self.process.readAll.return_value = QtCore.QByteArray(
            b'APPINSTALL_UPDATE=v1.4.1\n')
        self.bridge._update_operation = 'check'
        with patch.object(manager_qml.subprocess, 'run') as run:
            self.bridge._update_finished(0, QtCore.QProcess.ExitStatus.NormalExit)
        run.assert_not_called()

    def test_install_success_shows_whats_new_from_packaged_notes(self):
        self.bridge._update_tag = 'v1.4.1'
        self.process.readAll.return_value = QtCore.QByteArray(
            b'APPINSTALL_UPDATED=v1.4.1\n')
        self.bridge.installUpdate()
        with patch.object(QtWidgets, 'QMessageBox') as box, \
             patch.object(manager_qml, 'release_notes', return_value='# Notes\n'):
            self.bridge._update_finished(0, QtCore.QProcess.ExitStatus.NormalExit)
        title = box.return_value.setText.call_args[0][0]
        self.assertTrue(title.startswith('What’s new in AppInstall v1.4.1'))
        box.return_value.setDetailedText.assert_called_once_with('# Notes\n')

    def test_install_success_without_packaged_notes_uses_release_url(self):
        self.bridge._update_tag = 'v1.4.1'
        self.process.readAll.return_value = QtCore.QByteArray(
            b'APPINSTALL_UPDATED=v1.4.1\n')
        self.bridge.installUpdate()
        with patch.object(QtWidgets, 'QMessageBox') as box, \
             patch.object(manager_qml, 'RELEASE_NOTES_PATH',
                          Path('/nonexistent/appinstall/RELEASE_NOTES.md')):
            self.bridge._update_finished(0, QtCore.QProcess.ExitStatus.NormalExit)
        detailed = box.return_value.setDetailedText.call_args[0][0]
        self.assertIn('releases/tag/v1.4.1', detailed)

    def test_manual_check_failure_shows_details(self):
        self.process.readAll.return_value = QtCore.QByteArray(b'boom\n')
        self.bridge.checkUpdates(True)
        with patch.object(QtWidgets, 'QMessageBox') as box:
            self.bridge._update_finished(1, QtCore.QProcess.ExitStatus.CrashExit)
        self.assertEqual(self.bridge._update_status, 'Could not check for updates')
        self.assertIn('boom', box.return_value.setDetailedText.call_args[0][0])


class ThemeTests(QmlManagerBase):
    def test_theme_setting_persists_and_flips_dark(self):
        with patch.dict(os.environ, {'QT_QPA_PLATFORM': 'offscreen'}):
            self.bridge.setTheme('dark')
        self.assertEqual(manager_qml.settings.read().get('theme'), 'dark')
        self.assertTrue(self.bridge.dark)
        self.bridge.setTheme('light')
        self.assertFalse(self.bridge.dark)


class HelperResolutionTests(unittest.TestCase):
    """The updater helper: packaged installer first, install.sh in a
    source checkout, PATH as the last resort."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def resolve(self):
        with patch.object(manager_qml, '__file__',
                          str(self.base / 'manager_qml.py')):
            return manager_qml.find_update_helper()

    def test_prefers_the_packaged_installer(self):
        (self.base / 'appinstall-installer').write_text('#!/bin/sh\n')
        helper = self.resolve()
        self.assertEqual(helper, self.base / 'appinstall-installer')
        self.assertTrue(helper.is_file())

    def test_source_checkout_falls_back_to_install_sh(self):
        (self.base / 'install.sh').write_text('#!/bin/sh\n')
        self.assertEqual(self.resolve(), self.base / 'install.sh')

    def test_path_lookup_is_the_last_resort(self):
        with patch.object(manager_qml.shutil, 'which',
                          return_value='/opt/bin/appinstall-installer'):
            self.assertEqual(self.resolve(),
                             Path('/opt/bin/appinstall-installer'))

    def test_missing_helper_returns_the_adjacent_candidate(self):
        # PATH may carry a real appinstall-installer (a system install);
        # isolate it so the 'nothing found' branch is what is tested.
        with patch.dict(os.environ, {'PATH': ''}):
            helper = self.resolve()
        self.assertEqual(helper.name, 'appinstall-installer')
        self.assertFalse(helper.is_file())


class CloseGuardTests(QmlManagerBase):
    def test_idle_close_is_allowed(self):
        self.assertTrue(self.bridge.allowClose())

    def test_install_update_blocks_closing(self):
        self.bridge._update_operation = 'install'
        self.assertFalse(self.bridge.allowClose())
        self.assertIn('updating', self.bridge._status_text)

    def test_running_check_is_killed_then_close_allowed(self):
        self.bridge._update_operation = 'check'
        self.bridge._update_process.kill = Mock()
        self.bridge._update_process.waitForFinished = Mock()
        self.assertTrue(self.bridge.allowClose())
        self.bridge._update_process.kill.assert_called_once_with()
        self.bridge._update_process.waitForFinished.assert_called_once_with(1000)

    def test_batch_with_running_pipeline_rejects_close_once(self):
        dialog = Mock()
        dialog.process = object()
        self.bridge._batch_dialog = dialog
        self.assertFalse(self.bridge.allowClose())
        dialog.reject.assert_called_once_with()

    def test_batch_without_pipeline_does_not_block(self):
        dialog = Mock()
        dialog.process = None
        self.bridge._batch_dialog = dialog
        self.assertTrue(self.bridge.allowClose())


class SmokeLaunchTests(unittest.TestCase):
    def test_smoke_flag_loads_the_window_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ)
            env.update({
                'QT_QPA_PLATFORM': 'offscreen',
                'XDG_DATA_HOME': str(Path(home) / 'data'),
                'XDG_STATE_HOME': str(Path(home) / 'state'),
                'APPINSTALL_DISABLE_UPDATE_TIMER': '1',
            })
            result = subprocess.run(
                [sys.executable, str(ROOT / 'manager_qml.py'), '--smoke'],
                capture_output=True, text=True, timeout=120, env=env,
                cwd=str(ROOT))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('QML smoke', result.stdout)


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
