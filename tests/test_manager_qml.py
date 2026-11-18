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

from PySide6 import QtCore, QtGui, QtQml, QtQuick, QtTest

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

    def test_library_groups_attention_without_changing_explicit_status_filters(self):
        records = []
        for label, status in (('Alpha', 'installed'), ('Beta', 'needs-repair'),
                              ('Gamma', 'installed')):
            key = f'appimage:{label.lower()}'
            records.append((key, self.stage_installed_appimage(key, label, status=status)))
        self.load_inventory(records)
        self.model.groupLibrary()
        self.model.setSort('name-desc')
        names = lambda: [self.model.data(self.model.index(i, 0), self.model.NameRole)
                         for i in range(self.model.rowCount())]
        self.assertEqual(names(), ['Gamma', 'Alpha', 'Beta'])
        self.assertEqual(self.model.attentionCount, 1)
        self.assertEqual(self.model.data(self.model.index(2, 0), self.model.LibrarySectionRole),
                         'attention')
        self.model.setStatusFilter('needs-repair')
        self.assertEqual(names(), ['Beta'])
        self.assertEqual(self.model.data(self.model.index(0, 0), self.model.LibrarySectionRole), '')

    def test_favorites_sort_first(self):
        self.load_inventory([
            ('appimage:beta', self.stage_installed_appimage('appimage:beta', 'Beta')),
            ('appimage:alpha', self.stage_installed_appimage('appimage:alpha', 'Alpha')),
        ])
        self.model.set_favorites({'appimage:beta'})
        self.assertEqual(self.model.data(self.model.index(0, 0), self.model.KeyRole),
                         'appimage:beta')
        self.assertTrue(self.model.data(self.model.index(0, 0), self.model.PinnedRole))

    def test_icon_url_returns_empty_for_theme_icon_name(self):
        """Theme icon names (e.g. 'com.stremio.Stremio') are not file URLs
        and should return empty string so QML uses letter-avatar fallback."""
        raw = dict(format='appimage', name='Themed App', version='1.0',
                   desktop='', icon='com.stremio.Stremio', icon_name='',
                   container=None, manifest=None, target='/nonexistent/app.AppImage',
                   description='', status='installed')
        self.load_inventory([('flatpak:com.stremio.Stremio', raw)])
        index = self.model.index(0, 0)
        self.assertEqual(self.model.data(index, self.model.IconUrlRole), '')

    def test_icon_url_returns_empty_for_nonexistent_path(self):
        """A non-existent absolute path should return empty string."""
        raw = dict(format='appimage', name='Missing App', version='1.0',
                   desktop='/nonexistent/missing.desktop', icon='/nonexistent/icon.png',
                   icon_name='', container=None, manifest=None,
                   target='/nonexistent/app.AppImage', description='',
                   status='installed')
        self.load_inventory([('appimage:missing', raw)])
        index = self.model.index(0, 0)
        self.assertEqual(self.model.data(index, self.model.IconUrlRole), '')

    def test_icon_url_returns_file_uri_for_existing_path(self):
        """An absolute path to an existing file should return a file:// URL."""
        desktop = self.root / 'entries' / 'existing.desktop'
        desktop.parent.mkdir(parents=True, exist_ok=True)
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Existing\n')
        raw = dict(format='appimage', name='Existing App', version='1.0',
                   desktop=str(desktop), icon=str(desktop), icon_name='',
                   container=None, manifest=None,
                   target='/nonexistent/app.AppImage', description='',
                   status='installed')
        self.load_inventory([('appimage:existing', raw)])
        index = self.model.index(0, 0)
        self.assertEqual(self.model.data(index, self.model.IconUrlRole),
                         'file://' + str(desktop))

    def test_can_open_true_when_launcher_exists(self):
        """Record with a real desktop file: Open enabled."""
        self.load_inventory([
            ('appimage:example', self.stage_installed_appimage('appimage:example', 'Example App')),
        ])
        index = self.model.index(0, 0)
        self.assertTrue(self.model.data(index, self.model.CanOpenRole))

    def test_can_open_true_for_stale_record_with_usable_launcher(self):
        """Stale status but a real launcher: Open still enabled."""
        raw = self.stage_installed_appimage(
            'appimage:stale-launchable', 'Stale Launchable')
        raw['status'] = 'stale'
        self.load_inventory([('appimage:stale-launchable', raw)])
        index = self.model.index(0, 0)
        self.assertEqual(self.model.data(index, self.model.StatusRole), 'stale')
        self.assertTrue(self.model.data(index, self.model.CanOpenRole))

    def test_can_open_false_for_stale_record_without_launcher(self):
        """Stale record with no usable launcher: Open disabled, Details available."""
        raw = dict(format='appimage', name='Stale App', version='1.0',
                   desktop='/nonexistent/stale.desktop',
                   icon='', icon_name='stale', container=None,
                   manifest=None, target='/nonexistent/stale.AppImage',
                   description='', status='stale')
        self.load_inventory([('appimage:stale', raw)])
        index = self.model.index(0, 0)
        self.assertFalse(self.model.data(index, self.model.CanOpenRole))


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

    def test_update_app_requires_new_review_gate_not_legacy_direct_update(self):
        with patch.object(manager, 'can_update', return_value=True), \
             patch.object(manager, 'update_app') as legacy_update, \
             patch.object(self.bridge, 'requestFlatpakUpdate') as reviewed_update:
            self.bridge.updateApp('appimage:example')
        legacy_update.assert_not_called()
        reviewed_update.assert_not_called()
        self.assertIn('Open the Updates tab', self.bridge._status_text)

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

    def test_toggle_pin_writes_settings_and_updates_the_model(self):
        index = self.model.index(0, 0)
        self.assertFalse(self.model.data(index, self.model.PinnedRole))
        self.bridge.togglePin('appimage:example')
        self.assertTrue(self.model.data(index, self.model.PinnedRole))
        self.assertEqual(manager_qml.settings.read().get('favorites'),
                         ['appimage:example'])
        self.bridge.togglePin('appimage:example')
        self.assertFalse(self.model.data(index, self.model.PinnedRole))
        self.assertEqual(manager_qml.settings.read().get('favorites'), [])


class BridgePreferenceTests(QmlManagerBase):
    def test_notifications_saved_to_persistent_settings(self):
        self.assertFalse(self.bridge.notificationsEnabled)
        self.bridge.setNotificationsEnabled(True)
        self.assertTrue(self.bridge.notificationsEnabled)
        self.assertTrue(manager_qml.settings.read()['notifications'])
        self.bridge.setNotificationsEnabled(False)
        self.assertFalse(manager_qml.settings.read()['notifications'])

    def test_uninstall_mode_is_saved_and_invalid_input_rejected(self):
        self.assertEqual(self.bridge.uninstallMode, 'ask')
        self.bridge.setUninstallMode('with_managed_data')
        self.assertEqual(self.bridge.uninstallMode, 'with_managed_data')
        self.bridge.setUninstallMode('app_only')
        self.assertEqual(manager_qml.settings.read()['uninstall_mode'], 'app_only')
        self.bridge.setUninstallMode('/tmp/unsafe')
        self.assertEqual(self.bridge.uninstallMode, 'app_only')
        self.assertIn('Invalid uninstall preference', self.bridge._status_text)


class CatalogModelTests(QmlManagerBase):
    """Discover results and installed app records stay separate."""

    def setUp(self):
        super().setUp()
        # Metadata and artwork are optional worker-phase providers. Tests of
        # catalog pagination/search must not access the live network or a
        # rootless Distrobox container in the CI runner.
        for obj, member in (
            (manager_qml.catalog_artwork, "cache_results"),
            (manager_qml.catalog_metadata, "repo_enrichment"),
        ):
            mock = patch.object(obj, member, return_value={})
            mock.start()
            self.addCleanup(mock.stop)

    def sample(self):
        return [{
            'appId': 'org.gimp.GIMP', 'name': 'GIMP',
            'summary': 'Image editor',
            'iconUrl': '', 'category': 'Graphics',
        }]

    def test_source_qualified_details_are_model_roles_not_install_ids(self):
        model = self.bridge.catalogModel
        model.replace([{
            **self.sample()[0], 'providerKey': 'flatpak:org.gimp.GIMP',
            'developer': 'GIMP Team', 'version': '3.0',
            'license': 'GPL-3.0-or-later',
            'homepage': 'https://www.gimp.org/',
            'componentId': 'org.gimp.GIMP',
            'cachedIconUrl': 'file:///tmp/validated-gimp.png',
        }])
        i = model.index(0, 0)
        self.assertEqual(model.data(i, model.ProviderKeyRole),
                         'flatpak:org.gimp.GIMP')
        self.assertEqual(model.data(i, model.DeveloperRole), 'GIMP Team')
        self.assertEqual(model.data(i, model.VersionRole), '3.0')
        self.assertEqual(model.data(i, model.LicenseRole), 'GPL-3.0-or-later')
        self.assertEqual(model.data(i, model.HomepageRole), 'https://www.gimp.org/')
        self.assertEqual(model.data(i, model.ComponentRole), 'org.gimp.GIMP')
        self.assertEqual(model.data(i, model.IconRole),
                         'file:///tmp/validated-gimp.png')
        # Source and install identity remain unchanged after enrichment.
        model.apply_metadata({'org.gimp.GIMP': {
            'name': 'The GIMP', 'developer': 'Another publisher',
            'appId': 'evil.package', 'source': 'RPM',
        }})
        self.assertEqual(model.data(i, model.AppIdRole), 'org.gimp.GIMP')
        self.assertEqual(model.data(i, model.SourceRole), 'Flatpak')
        self.assertEqual(model.data(i, model.NameRole), 'The GIMP')

    def test_featured_flathub_browse_uses_unmodified_install_ids(self):
        rows = manager_qml.catalog_metadata.normalize_rows([
            {"source": "Flatpak", "appId": f"org.example.App{i}",
             "name": f"App{i}", "category": "Graphics"} for i in range(9)])
        self.bridge._catalog_source = "Flatpak"
        self.bridge._catalog_query = ""
        self.bridge._catalog_all = rows
        self.bridge._rebuild_catalog_view()
        self.assertTrue(self.bridge.catalogHasFeatured)
        self.assertEqual(self.bridge.featuredCatalogModel.count, 6)
        self.assertIn("Graphics", self.bridge.catalogCategories)
        self.assertEqual(self.bridge.featuredCatalogModel.data(
            self.bridge.featuredCatalogModel.index(0, 0),
            self.bridge.featuredCatalogModel.AppIdRole), "org.example.App0")
        self.bridge._catalog_query = "gimp"
        self.bridge._rebuild_catalog_view()
        self.assertFalse(self.bridge.catalogHasFeatured)

    def test_category_selection_paginates_locally(self):
        rows = manager_qml.catalog_metadata.normalize_rows([
            {"source": "DEB", "appId": f"graphics{i}", "name": f"G{i}",
             "category": "Graphics"} for i in range(60)] + [
            {"source": "DEB", "appId": f"office{i}", "name": f"O{i}",
             "category": "Office"} for i in range(20)])
        self.bridge._catalog_source = "DEB"
        self.bridge._catalog_all = rows
        self.bridge._rebuild_catalog_view()
        self.assertEqual(self.bridge.catalogModel.count, 24)
        self.assertTrue(self.bridge.catalogHasMore)
        self.assertFalse(self.bridge.catalogHasFeatured)
        self.bridge.chooseCatalogCategory("Graphics")
        self.bridge.loadMoreCatalog()
        self.assertEqual(self.bridge.catalogModel.count, 48)
        self.bridge.chooseCatalogCategory("Office")
        self.assertEqual(self.bridge.catalogModel.count, 20)
        self.assertFalse(self.bridge.catalogHasMore)
        self.assertEqual(self.bridge.catalogModel.data(
            self.bridge.catalogModel.index(0, 0),
            self.bridge.catalogModel.AppIdRole), "office0")
        self.assertEqual(len(self.bridge._catalog_all), 80)

    def test_late_metadata_rebuilds_categories_safely(self):
        rows = manager_qml.catalog_metadata.normalize_rows([
            {"source": "RPM", "appId": "gimp", "category": "Fedora 44"}])
        self.bridge._catalog_source = "RPM"
        self.bridge._catalog_all = rows
        self.bridge._rebuild_catalog_view()
        self.assertEqual(self.bridge.catalogCategories, ["All", "Other"])
        rows[0]["category"] = "Graphics"
        self.bridge._rebuild_catalog_view(preserve_page=True)
        self.assertEqual(self.bridge.catalogCategories, ["All", "Graphics"])
        self.bridge.chooseCatalogCategory("Graphics")
        self.assertEqual(self.bridge.catalogModel.count, 1)
        self.assertEqual(rows[0]["providerKey"], "rpm:gimp")

    def test_featured_model_reacts_to_cached_artwork(self):
        row = manager_qml.catalog_metadata.normalize_rows([{
            "source": "Flatpak", "appId": "org.example.App",
            "category": "Games"}])[0]
        self.bridge._catalog_source = "Flatpak"
        self.bridge._catalog_query = ""
        self.bridge._catalog_all = [row]
        self.bridge._rebuild_catalog_view()
        cached = {"org.example.App": "file:///tmp/verified.png"}
        self.bridge.catalogModel.apply_artwork(cached)
        self.bridge.featuredCatalogModel.apply_artwork(cached)
        for model in (self.bridge.catalogModel, self.bridge.featuredCatalogModel):
            self.assertEqual(model.data(model.index(0, 0), model.IconRole),
                             cached["org.example.App"])

    def test_details_require_current_exact_source_identity(self):
        rows = manager_qml.catalog_metadata.normalize_rows([{
            "source": "DEB", "appId": "gimp", "name": "GNU Image Editor",
            "summary": "Paint and edit images", "category": "Graphics",
            "developer": "GIMP Team", "license": "GPL-3.0",
            "homepage": "https://www.gimp.org/", "componentId": "org.gimp.GIMP",
            "version": "3.0", "cachedIconUrl": "file:///tmp/validated.png",
        }])
        self.bridge._catalog_source = "DEB"
        self.bridge._catalog_all = rows
        self.bridge._rebuild_catalog_view()
        self.bridge.openCatalogDetails("gimp", "DEB")
        details = self.bridge.catalogDetails
        self.assertTrue(self.bridge.catalogDetailsAvailable)
        self.assertEqual(details["providerKey"], "deb:gimp")
        self.assertEqual(details["appId"], "gimp")
        self.assertEqual(details["source"], "DEB")
        self.assertEqual(details["categoryGroup"], "Graphics")
        self.assertEqual(details["iconUrl"], "file:///tmp/validated.png")
        self.assertEqual(details["homepage"], "https://www.gimp.org/")
        self.bridge.openCatalogDetails("gimp", "RPM")
        self.bridge.openCatalogDetails("nonexistent", "DEB")
        self.assertEqual(self.bridge.catalogDetails["providerKey"], "deb:gimp")
        self.bridge.closeCatalogDetails()
        self.assertFalse(self.bridge.catalogDetailsAvailable)
        self.assertEqual(self.bridge.catalogDetails, {})

    def test_details_refuse_untrusted_homepages_and_uncached_artwork(self):
        rows = manager_qml.catalog_metadata.normalize_rows([{
            "source": "Flatpak", "appId": "org.example.Test", "name": "Test",
            "summary": "", "iconUrl": "https://example.invalid/unsafe.svg",
            "homepage": "javascript:alert(1)", "category": "",
        }])
        self.bridge._catalog_source = "Flatpak"
        self.bridge._catalog_all = rows
        self.bridge._rebuild_catalog_view()
        self.bridge.openCatalogDetails("org.example.Test", "Flatpak")
        self.assertEqual(self.bridge.catalogDetails["iconUrl"], "")
        self.assertEqual(self.bridge.catalogDetails["homepage"], "")
        self.assertEqual(self.bridge.catalogDetails["version"], "")
        self.assertEqual(self.bridge.catalogDetails["categoryGroup"], "Other")
        with patch.object(manager_qml.QtGui.QDesktopServices, "openUrl") as open_url:
            self.bridge.openSelectedCatalogHomepage()
        open_url.assert_not_called()

    def test_proprietary_license_keeps_exact_metadata_with_clean_label(self):
        raw = "LicenseRef-proprietary=https://example.org/notice.txt"
        rows = manager_qml.catalog_metadata.normalize_rows([{
            "source": "Flatpak", "appId": "org.example.App", "name": "Example",
            "license": raw,
        }])
        self.bridge._catalog_source = "Flatpak"
        self.bridge._catalog_all = rows
        self.bridge._rebuild_catalog_view()
        self.bridge.openCatalogDetails("org.example.App", "Flatpak")
        self.assertEqual(self.bridge.catalogDetails["license"], raw)
        self.assertEqual(self.bridge.catalogDetails["licenseDisplay"], "Proprietary")
        rows[0]["license"] = "GPL-3.0-or-later"
        self.bridge._sync_catalog_details()
        self.assertEqual(self.bridge.catalogDetails["licenseDisplay"],
                         "GPL-3.0-or-later")

    def test_details_install_goes_through_existing_flow(self):
        rows = manager_qml.catalog_metadata.normalize_rows([{
            "source": "Flatpak", "appId": "org.gimp.GIMP", "name": "GIMP"
        }])
        self.bridge._catalog_source = "Flatpak"
        self.bridge._catalog_all = rows
        self.bridge._rebuild_catalog_view()
        self.bridge.openCatalogDetails("org.gimp.GIMP", "Flatpak")
        with patch.object(self.bridge, "installCatalogEntry") as installer:
            self.bridge.installSelectedCatalogEntry()
        installer.assert_called_once_with("org.gimp.GIMP", "Flatpak")
        self.bridge.catalogModel.set_managed([
            {"key": "flatpak:org.gimp.GIMP", "format": "flatpak"}])
        self.bridge._sync_catalog_details()
        self.assertTrue(self.bridge.catalogDetails["managed"])
        self.assertEqual(self.bridge.catalogDetails["actionLabel"], "Managed")
        with patch.object(self.bridge, "installCatalogEntry") as installer:
            self.bridge.installSelectedCatalogEntry()
        installer.assert_not_called()

    def test_details_metadata_updates_and_search_switch_invalidates(self):
        rows = manager_qml.catalog_metadata.normalize_rows([{
            "source": "AppImage", "appId": "A_Test_App", "name": "App",
            "sourceUrl": "https://appimage.github.io/apps/A_Test_App",
            "installUrl": "",
        }])
        self.bridge._catalog_source = "AppImage"
        self.bridge._catalog_all = rows
        self.bridge._rebuild_catalog_view()
        self.bridge.openCatalogDetails("A_Test_App", "AppImage")
        self.assertEqual(self.bridge.catalogDetails["actionLabel"], "Downloads")
        rows[0]["developer"] = "Community Maintainer"
        rows[0]["cachedIconUrl"] = "file:///tmp/verified.png"
        self.bridge._sync_catalog_details()
        self.assertEqual(self.bridge.catalogDetails["developer"], "Community Maintainer")
        self.assertEqual(self.bridge.catalogDetails["iconUrl"], "file:///tmp/verified.png")
        self.bridge.searchCatalog("g", "RPM")
        self.assertFalse(self.bridge.catalogDetailsAvailable)
        self.assertEqual(self.bridge.catalogDetails, {})

    def test_details_only_open_selected_verified_homepage(self):
        rows = manager_qml.catalog_metadata.normalize_rows([{
            "source": "Flatpak", "appId": "org.example.Test", "name": "Test",
            "homepage": "https://example.org/product",
        }])
        self.bridge._catalog_source = "Flatpak"
        self.bridge._catalog_all = rows
        self.bridge._rebuild_catalog_view()
        self.bridge.openCatalogDetails("org.example.Test", "Flatpak")
        with patch.object(manager_qml.QtGui.QDesktopServices, "openUrl") as opener:
            self.bridge.openSelectedCatalogHomepage()
            opener.assert_called_once()
            url = opener.call_args.args[0]
            self.assertEqual(url.toString(), "https://example.org/product")
        self.bridge.closeCatalogDetails()
        with patch.object(manager_qml.QtGui.QDesktopServices, "openUrl") as opener:
            self.bridge.openSelectedCatalogHomepage()
        opener.assert_not_called()

    def test_model_roles_and_managed_detection(self):
        model = self.bridge.catalogModel
        model.replace(self.sample())
        self.assertEqual(model.count, 1)
        index = model.index(0, 0)
        self.assertEqual(model.data(index, model.AppIdRole), 'org.gimp.GIMP')
        self.assertFalse(model.data(index, model.ManagedRole))
        model.set_managed([{'key': 'flatpak:org.gimp.GIMP', 'format': 'flatpak'}])
        self.assertTrue(model.data(index, model.ManagedRole))
        model.set_managed([{'key': 'appimage:org.gimp.GIMP', 'format': 'appimage'}])
        self.assertFalse(model.data(index, model.ManagedRole))

    def test_async_search_queries_flathub_without_blocking_ui(self):
        self.assertFalse(self.bridge.catalogLoading)
        with patch.object(manager_qml.flathub_catalog, 'search',
                          return_value=self.sample()) as lookup:
            self.bridge.searchCatalog('gimp')
            self.assertTrue(self.bridge.catalogLoading)
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                self.app.processEvents()
                if not self.bridge.catalogLoading:
                    break
                time.sleep(0.01)
        lookup.assert_called_once_with('gimp')
        self.assertFalse(self.bridge.catalogLoading)
        self.assertEqual(self.bridge.catalogModel.count, 1)
        self.assertIn('1 application found', self.bridge.catalogStatus)

    def test_discover_initial_browse_uses_live_popular_provider(self):
        with patch.object(manager_qml.flathub_catalog, 'popular',
                          return_value=self.sample()) as popular:
            self.bridge.searchCatalog('')
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline and self.bridge.catalogLoading:
                self.app.processEvents()
                time.sleep(0.01)
        popular.assert_called_once()
        self.assertEqual(self.bridge.catalogModel.count, 1)

    def test_short_search_stops_before_network(self):
        with patch.object(manager_qml.flathub_catalog, 'search') as lookup, \
             patch.object(manager_qml.flathub_catalog, 'popular') as popular:
            self.bridge.searchCatalog('g')
        self.assertEqual(self.bridge.catalogModel.count, 0)
        lookup.assert_not_called()
        popular.assert_not_called()

    def test_install_from_flathub_uses_existing_confirmation_dialog(self):
        with patch.object(manager, 'UrlInstallDialog') as dialog, \
             patch.object(self.bridge, 'refresh') as refresh:
            self.bridge.installFromFlathub('org.gimp.GIMP')
        dialog.assert_called_once_with(self.anchor)
        widget = dialog.return_value
        widget.url_edit.setText.assert_called_once_with(
            'https://dl.flathub.org/repo/appstream/org.gimp.GIMP.flatpakref')
        widget.installed.connect.assert_called_once_with(refresh)
        widget.exec.assert_called_once()

    def test_invalid_catalog_id_cannot_open_install_dialog(self):
        with patch.object(manager, 'UrlInstallDialog') as dialog:
            self.bridge.installFromFlathub('https://evil.invalid/a.flatpakref')
        dialog.assert_not_called()
        self.assertIn('Invalid', self.bridge.catalogStatus)

    def test_managed_app_does_not_start_duplicate_install(self):
        self.bridge.catalogModel.set_managed([
            {'format': 'flatpak', 'key': 'flatpak:org.gimp.GIMP'}])
        with patch.object(manager, 'UrlInstallDialog') as dialog:
            self.bridge.installFromFlathub('org.gimp.GIMP')
        dialog.assert_not_called()
        self.assertIn('already managed', self.bridge.catalogStatus)

    def test_load_more_reveals_next_batch_without_replacing_installed_apps(self):
        apps = [{**self.sample()[0], 'appId': f'org.example.App{i}'}
                for i in range(59)]
        self.bridge._catalog_source = 'Flatpak'
        self.bridge._catalog_all = apps
        self.bridge.catalogModel.replace(apps[:24])
        self.assertTrue(self.bridge.catalogHasMore)
        self.bridge.loadMoreCatalog()
        self.assertEqual(self.bridge.catalogModel.count, 48)
        self.assertTrue(self.bridge.catalogHasMore)
        self.bridge.loadMoreCatalog()
        self.assertEqual(self.bridge.catalogModel.count, 59)
        self.assertFalse(self.bridge.catalogHasMore)
        self.assertIn('59 applications found', self.bridge.catalogStatus)

    def test_appimage_browse_uses_independent_feed(self):
        items = [{**self.sample()[0], 'appId': 'Example_App',
                  'source': 'AppImage', 'sourceUrl': 'https://appimage.github.io/apps/Example_App',
                  'installUrl': ''}]
        with patch.object(manager_qml.flathub_catalog, 'appimage_browse',
                          return_value=items) as provider:
            self.bridge.searchCatalog('', 'AppImage')
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline and self.bridge.catalogLoading:
                self.app.processEvents()
                time.sleep(0.01)
        provider.assert_called_once_with()
        self.assertEqual(self.bridge.catalogModel.count, 1)
        self.assertEqual(self.bridge.catalogModel.data(
            self.bridge.catalogModel.index(0, 0),
            self.bridge.catalogModel.SourceRole), 'AppImage')

    def repository_rows(self, source):
        return [{
            'appId': 'gimp', 'name': 'gimp',
            'summary': 'Image editor', 'iconUrl': '',
            'category': 'Debian 13' if source == 'DEB' else 'Fedora 44',
            'source': source, 'installUrl': '', 'version': '3.0',
        }]

    def wait_for_catalog(self):
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            self.app.processEvents()
            if not self.bridge.catalogLoading:
                break
            time.sleep(0.01)

    def test_deb_and_rpm_show_real_repository_results(self):
        for source, kind in (('DEB', 'deb'), ('RPM', 'rpm')):
            with self.subTest(source=source), \
                 patch.object(manager_qml.repository_catalog, 'ready',
                              return_value=True), \
                 patch.object(manager_qml.repository_catalog, 'icons_for_results',
                              return_value={}), \
                 patch.object(manager_qml.repository_catalog, 'search',
                              return_value=self.repository_rows(source)) as lookup:
                self.bridge.searchCatalog('gimp', source)
                self.wait_for_catalog()
            lookup.assert_called_once_with(kind, 'gimp')
            self.assertFalse(self.bridge.catalogLoading)
            self.assertEqual(self.bridge.catalogModel.count, 1)
            self.assertEqual(self.bridge.catalogModel.data(
                self.bridge.catalogModel.index(0, 0),
                self.bridge.catalogModel.SourceRole), source)

    def test_deb_and_rpm_browse_when_tab_opens_without_typing(self):
        for source, kind in (('DEB', 'deb'), ('RPM', 'rpm')):
            rows = [{**self.repository_rows(source)[0],
                     'appId': f'example-app-{i:02d}',
                     'name': f'Example app {i}'}
                    for i in range(31)]
            with self.subTest(source=source), \
                 patch.object(manager_qml.repository_catalog, 'ready',
                              return_value=True), \
                 patch.object(manager_qml.repository_catalog, 'browse',
                              return_value=rows) as browse, \
                 patch.object(manager_qml.repository_catalog, 'icons_for_results',
                              return_value={}):
                self.bridge.searchCatalog('', source)
                self.wait_for_catalog()
            browse.assert_called_once_with(kind)
            self.assertEqual(self.bridge.catalogModel.count, 24)
            self.assertTrue(self.bridge.catalogHasMore)
            self.bridge.loadMoreCatalog()
            self.assertEqual(self.bridge.catalogModel.count, 31)
            self.assertFalse(self.bridge.catalogHasMore)
            self.assertIn('31 applications found', self.bridge.catalogStatus)

    def test_clearing_a_repository_query_restores_browse_cards(self):
        source = 'DEB'
        with patch.object(manager_qml.repository_catalog, 'ready',
                          return_value=True), \
             patch.object(manager_qml.repository_catalog, 'search',
                          return_value=self.repository_rows(source)) as typed, \
             patch.object(manager_qml.repository_catalog, 'browse',
                          return_value=self.repository_rows(source)), \
             patch.object(manager_qml.repository_catalog, 'icons_for_results',
                          return_value={}):
            self.bridge.searchCatalog('gimp', source)
            self.wait_for_catalog()
            typed.assert_called_once_with('deb', 'gimp')
            self.bridge.searchCatalog('', source)
            self.wait_for_catalog()
        self.assertFalse(self.bridge.catalogLoading)
        self.assertEqual(self.bridge.catalogModel.count, 1)

    def test_repository_icons_update_cards_without_losing_results(self):
        icon_url = ('https://appstream.debian.org/media/pool/org/gimp/GIMP/'
                    'abcd/icons/128x128/gimp_gimp.png')
        with patch.object(manager_qml.repository_catalog, 'ready',
                          return_value=True), \
             patch.object(manager_qml.repository_catalog, 'search',
                          return_value=self.repository_rows('DEB')), \
             patch.object(manager_qml.repository_catalog, 'icons_for_results',
                          return_value={'gimp': icon_url}) as lookup:
            self.bridge.searchCatalog('gimp', 'DEB')
            self.wait_for_catalog()
        lookup.assert_called_once()
        self.assertEqual(self.bridge.catalogModel.count, 1)
        index = self.bridge.catalogModel.index(0, 0)
        # Provider URL stays as *metadata*, but the QML Image never receives
        # it until the image was downloaded/validated into the local cache.
        self.assertEqual(self.bridge.catalogModel.data(
            index, self.bridge.catalogModel.IconRole), "")
        self.assertEqual(self.bridge._catalog_all[0]['iconUrl'], icon_url)
        self.bridge.catalogModel.apply_artwork({'gimp': 'file:///tmp/verified-icon.png'})
        self.assertEqual(self.bridge.catalogModel.data(
            index, self.bridge.catalogModel.IconRole),
            'file:///tmp/verified-icon.png')
        self.assertFalse(self.bridge.catalogHasMore)

    def test_stale_icon_updates_cannot_replace_another_source(self):
        old = self.repository_rows('DEB')
        self.bridge._catalog_all = old
        self.bridge._catalog.replace(old)
        self.bridge._catalog_source = 'RPM'
        self.bridge._catalog_icons_ready('gimp', 'DEB',
                                         {'gimp': 'https://example.invalid/fake.png'})
        self.assertEqual(self.bridge._catalog_all[0]['iconUrl'], '')
        self.assertEqual(self.bridge.catalogModel.data(
            self.bridge.catalogModel.index(0, 0),
            self.bridge.catalogModel.IconRole), '')

    def test_missing_repository_requires_explicit_enable(self):
        with patch.object(manager_qml.repository_catalog, 'ready',
                          return_value=False):
            self.bridge.searchCatalog('', 'DEB')
            self.wait_for_catalog()
        self.assertTrue(self.bridge.catalogSetupRequired)
        self.assertEqual(self.bridge.catalogModel.count, 0)
        self.assertIn('Enable', self.bridge.catalogStatus)

    def test_repository_setup_requests_permission_before_pulling(self):
        import container_ui
        with patch.object(manager_qml.repository_catalog, 'prepare') as prepare, \
             patch.object(manager_qml.repository_catalog, 'search',
                          return_value=[]), \
             patch.object(QtWidgets.QMessageBox, 'question',
                          return_value=QtWidgets.QMessageBox.StandardButton.No):
            self.bridge._catalog_source = 'DEB'
            self.bridge.prepareCatalogSource('DEB')
        prepare.assert_not_called()
        with patch.object(manager_qml.repository_catalog, 'prepare') as prepare, \
             patch.object(manager_qml.repository_catalog, 'ready',
                          return_value=True), \
             patch.object(manager_qml.repository_catalog, 'browse',
                          return_value=[]), \
             patch.object(QtWidgets.QMessageBox, 'question',
                          return_value=QtWidgets.QMessageBox.StandardButton.Yes):
            self.bridge.prepareCatalogSource('DEB')
            self.wait_for_catalog()
        prepare.assert_called_once_with('deb')
        self.assertFalse(self.bridge.catalogSetupRequired)

    def test_repository_install_requires_catalog_membership_and_workflow(self):
        import container_ui
        self.bridge._catalog_source = 'RPM'
        self.bridge._catalog_all = self.repository_rows('RPM')
        with patch.object(container_ui, 'Workflow') as workflow, \
             patch.object(self.bridge, 'refresh') as refresh:
            workflow.return_value.batch_result = 75
            self.bridge.installCatalogEntry('gimp', 'RPM')
            workflow.assert_called_once_with(['--repo', 'rpm', 'gimp'])
            workflow.return_value.exec.assert_called_once()
            refresh.assert_not_called()
            self.bridge.installCatalogEntry('unlisted', 'RPM')
        self.assertEqual(workflow.call_count, 1)

    def test_managed_repository_package_disables_duplicate_installs(self):
        import container_ui
        self.bridge._catalog_source = 'DEB'
        self.bridge._catalog_all = self.repository_rows('DEB')
        self.bridge.catalogModel.set_managed([
            {'format': 'deb', 'key': 'deb:gimp'}])
        self.bridge.catalogModel.replace(self.bridge._catalog_all)
        self.assertTrue(self.bridge.catalogModel.data(
            self.bridge.catalogModel.index(0, 0),
            self.bridge.catalogModel.ManagedRole))
        with patch.object(container_ui, 'Workflow') as workflow:
            self.bridge.installCatalogEntry('gimp', 'DEB')
        workflow.assert_not_called()
        self.assertIn('already managed', self.bridge.catalogStatus)

    def test_appimage_entry_opens_official_page_when_no_direct_artifact(self):
        self.bridge._catalog_source = 'AppImage'
        self.bridge._catalog_all = [{
            'appId': 'Example_App', 'source': 'AppImage',
            'sourceUrl': 'https://appimage.github.io/apps/Example_App',
            'installUrl': '',
        }]
        with patch.object(QtGui.QDesktopServices, 'openUrl') as open_url, \
             patch.object(manager, 'UrlInstallDialog') as dialog:
            self.bridge.installCatalogEntry('Example_App', 'AppImage')
        dialog.assert_not_called()
        self.assertEqual(open_url.call_args.args[0].host(), 'appimage.github.io')



class BridgeInstallTests(QmlManagerBase):
    """Header install actions reuse the widgets window's exact flows."""

    def setUp(self):
        super().setUp()
        self.apps = self.load_inventory([
            ('appimage:example', self.stage_installed_appimage('appimage:example', 'Example App')),
        ])

    def test_install_from_file_opens_the_existing_picker(self):
        with patch.object(manager.ui_style, 'open_package') as open_package:
            self.bridge.installFromFile()
        open_package.assert_called_once_with(self.anchor)

    def test_install_from_url_uses_the_existing_url_dialog(self):
        with patch.object(manager, 'UrlInstallDialog') as dialog:
            instance = dialog.return_value
            self.bridge.installFromUrl()
        dialog.assert_called_once_with(self.anchor)
        instance.exec.assert_called_once()
        # installed → the normal inventory refresh, as in the widgets window.
        instance.installed.connect.assert_called_once_with(self.bridge.refresh)


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

    def test_portable_update_check_runs_python_not_bash(self):
        self.bridge._update_helper = self.root / 'portable_update.py'
        self.bridge._update_helper.write_text('# test portable updater\n')
        self.bridge.checkUpdates(True)
        args = self.process.start.call_args.args
        self.assertEqual(args[0], sys.executable)
        self.assertEqual(args[1], [str(self.bridge._update_helper), '--desktop-check'])

    def test_portable_update_requires_explicit_confirmation(self):
        self.bridge._update_helper = self.root / 'portable_update.py'
        self.bridge._update_helper.write_text('# test portable updater\n')
        self.bridge._update_tag = 'v1.8.1'
        with patch.object(QtWidgets.QMessageBox, 'question',
                          return_value=QtWidgets.QMessageBox.StandardButton.No) as prompt:
            self.bridge.installUpdate()
        prompt.assert_called_once()
        self.process.start.assert_not_called()
        self.assertFalse(self.bridge._update_operation)
        with patch.object(QtWidgets.QMessageBox, 'question',
                          return_value=QtWidgets.QMessageBox.StandardButton.Yes):
            self.bridge.installUpdate()
        args = self.process.start.call_args.args
        self.assertEqual(args[0], sys.executable)
        self.assertEqual(args[1], [str(self.bridge._update_helper),
                                   '--desktop-update', 'v1.8.1'])

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

    def test_user_source_install_picks_portable_helper_before_path(self):
        data = self.base / 'data'
        state = data / 'appinstall'
        state.mkdir(parents=True)
        (state / 'portable_update.py').write_text('# portable updater\n')
        (state / 'install.sh').write_text('# old checked-out script\n')
        with patch.dict(os.environ, {'XDG_DATA_HOME': str(data)}), \
             patch.object(manager_qml, '__file__', str(state / 'manager_qml.py')):
            self.assertEqual(manager_qml.find_update_helper(),
                             state / 'portable_update.py')

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


class QmlDropdownRegressionTests(QmlManagerBase):
    """The controls must render real options without KDE ComboBox styling."""

    def test_dropdown_buttons_and_popup_options_exist(self):
        self.load_inventory([
            ('appimage:example', self.stage_installed_appimage('appimage:example', 'Example App')),
        ])
        self.engine = QtQml.QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('bridge', self.bridge)
        self.engine.rootContext().setContextProperty('appsModel', self.model)
        self.engine.addImportPath(str(manager_qml.QML_DIR.parent))
        with QmlLoadCapture() as capture:
            self.engine.load(str(manager_qml.QML_DIR / 'main.qml'))
        self.window = self.engine.rootObjects()[0]
        self.assertIsNotNone(self.window, 'main.qml failed to load')
        self.assertEqual([m for m in capture.messages if 'Error' in m], [])
        for name, expected in (('statusFilter', 6), ('sortCombo', 4)):
            expr = QtQml.QQmlExpression(QtQml.qmlContext(self.window),
                                         self.window, f'{name}.options.length')
            value, _ = expr.evaluate()
            self.assertFalse(expr.hasError(), expr.error().toString())
            self.assertEqual(value, expected)

    def test_card_hover_has_defined_boolean(self):
        self.load_inventory([
            ('appimage:example', self.stage_installed_appimage('appimage:example', 'Example App')),
        ])
        self.engine = QtQml.QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('bridge', self.bridge)
        self.engine.rootContext().setContextProperty('appsModel', self.model)
        self.engine.addImportPath(str(manager_qml.QML_DIR.parent))
        with QmlLoadCapture() as capture:
            self.engine.load(str(manager_qml.QML_DIR / 'main.qml'))
        self.window = self.engine.rootObjects()[0]
        self.assertIsNotNone(self.window)
        self.assertFalse(any('Unable to assign [undefined] to bool' in m
                             for m in capture.messages))


class QmlMenuBarTests(QmlManagerBase):
    """Compact header keeps real menu actions and independent hide/show."""

    def test_header_menu_and_settings_dialog_render(self):
        self.engine = QtQml.QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('bridge', self.bridge)
        self.engine.rootContext().setContextProperty('appsModel', self.model)
        self.engine.addImportPath(str(manager_qml.QML_DIR.parent))
        with QmlLoadCapture() as capture:
            self.engine.load(str(manager_qml.QML_DIR / 'main.qml'))
        self.assertTrue(self.engine.rootObjects(), capture.messages)
        window = self.engine.rootObjects()[0]
        window.show()
        QtTest.QTest.qWait(75)
        try:
            for name in ('appMenuBar', 'menuToggle',
                         'viewMenuButton', 'toolsMenuButton',
                         'settingsMenuButton', 'helpMenuButton',
                         'filtersPanel', 'installDropdown', 'menuInstallFile',
                         'menuInstallUrl', 'menuRefresh', 'menuFocusSearch',
                         'menuAbout', 'settingsDialog', 'notificationCheck',
                         'uninstallAsk', 'uninstallAppOnly', 'uninstallWithData'):
                self.assertIsNotNone(window.findChild(QtCore.QObject, name), name)
            self.assertFalse(any('Error' in m or 'Unable to assign' in m
                                 for m in capture.messages), capture.messages)
        finally:
            window.close()
            self.engine.deleteLater()
            self.app.processEvents()

    def test_primary_navigation_and_actions_share_one_header(self):
        self.engine = QtQml.QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('bridge', self.bridge)
        self.engine.rootContext().setContextProperty('appsModel', self.model)
        self.engine.addImportPath(str(manager_qml.QML_DIR.parent))
        self.engine.load(str(manager_qml.QML_DIR / 'main.qml'))
        self.assertTrue(self.engine.rootObjects())
        window = self.engine.rootObjects()[0]
        window.setWidth(940)
        window.show()
        QtTest.QTest.qWait(100)
        try:
            names = ('managedTab', 'discoverTab', 'updatesTab',
                     'menuToggle', 'installDropdown')
            buttons = [window.findChild(QtCore.QObject, name)
                       for name in names]
            self.assertTrue(all(buttons))
            positions = [button.mapToScene(QtCore.QPointF(
                0, button.height() / 2)).toTuple() for button in buttons]
            self.assertTrue(all(positions[i][0] < positions[i + 1][0]
                                for i in range(len(positions) - 1)), positions)
            self.assertLessEqual(max(y for x, y in positions) -
                                 min(y for x, y in positions), 1, positions)
        finally:
            window.close()
            self.engine.deleteLater()
            self.app.processEvents()

    def test_header_menu_opens_without_replacing_app_list(self):
        self.engine = QtQml.QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('bridge', self.bridge)
        self.engine.rootContext().setContextProperty('appsModel', self.model)
        self.engine.addImportPath(str(manager_qml.QML_DIR.parent))
        self.engine.load(str(manager_qml.QML_DIR / 'main.qml'))
        window = self.engine.rootObjects()[0]
        expr = lambda v: QtQml.QQmlExpression(QtQml.qmlContext(window),
                                               window, v).evaluate()[0]
        try:
            self.assertFalse(expr('appMenuBar.visible'))
            self.assertTrue(expr('filtersPanel.visible'))
            self.assertTrue(expr('appList.visible'))
            expr('menuToggle.clicked()')
            self.assertTrue(expr('appMenuBar.visible'))
            self.assertTrue(expr('appList.visible'))
            expr('appMenuBar.close()')
            self.assertFalse(expr('appMenuBar.visible'))
            self.assertTrue(expr('filtersPanel.visible'))
        finally:
            window.close()
            self.engine.deleteLater()

    def test_buttons_route_to_existing_bridge_and_real_settings(self):
        qml = (manager_qml.QML_DIR / 'main.qml').read_text()
        for action in ('bridge.installFromFile()', 'bridge.installFromUrl()',
                       'bridge.refresh()', 'searchField.forceActiveFocus()',
                       'bridge.checkUpdates(true)', 'bridge.openDiagnostics("")',
                       'bridge.setTheme("auto")', 'bridge.setTheme("light")',
                       'bridge.setTheme("dark")', 'bridge.setNotificationsEnabled(checked)',
                       'bridge.setUninstallMode("ask")',
                       'bridge.setUninstallMode("app_only")',
                       'bridge.setUninstallMode("with_managed_data")'):
            self.assertIn(action, qml)
        self.assertIn('onTriggered: settingsDialog.open()', qml)
        self.assertIn('onTriggered: aboutDialog.open()', qml)
        self.assertIn('Qt.openUrlExternally(', qml)
        self.assertNotIn('title: qsTr("File")', qml)


class QmlDiscoverTests(QmlManagerBase):
    """New tab must not disturb My Applications, header or startup."""

    def test_banner_and_scrolling_cards_fit_at_supported_widths(self):
        records = []
        for i in range(18):
            key = f'appimage:geometry{i}'
            records.append((key, self.stage_installed_appimage(key, f'App {i}')))
        inventory = self.load_inventory(records)
        self.bridge._update_tag = 'v99.0.0'
        self.bridge._update_status = 'AppInstall update available'
        self.bridge.updatesModel.replace_results(inventory, [
            manager_qml.update_engine.UpdateCandidate(
                key=app['key'], format='appimage', state='manual-required',
                reason='Long diagnostic text ' * 25) for app in inventory
        ])
        self.engine = QtQml.QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('bridge', self.bridge)
        self.engine.rootContext().setContextProperty('appsModel', self.model)
        self.engine.addImportPath(str(manager_qml.QML_DIR.parent))
        self.engine.load(str(manager_qml.QML_DIR / 'main.qml'))
        window = self.engine.rootObjects()[0]

        def expr(code):
            expression = QtQml.QQmlExpression(QtQml.qmlContext(window), window, code)
            value, _ = expression.evaluate()
            self.assertFalse(expression.hasError(), expression.error().toString())
            return value

        try:
            for width in (720, 800, 1024, 1440):
                with self.subTest(width=width):
                    window.resize(width, 650)
                    window.setProperty('updatesSelected', False)
                    QtTest.QTest.qWait(45)
                    self.assertTrue(expr('updateBanner.visible'))
                    self.assertAlmostEqual(expr('updateBanner.x'), expr('contentArea.x'), delta=1)
                    self.assertAlmostEqual(expr('updateBanner.x'),
                                           expr('searchField.mapToItem(grabRoot, 0, 0).x'), delta=1)
                    self.assertLess(expr('appList.itemAtIndex(0).width'), expr('libraryScrollBar.x'))
                    window.setProperty('updatesSelected', True)
                    QtTest.QTest.qWait(45)
                    self.assertLess(expr('appUpdatesList.itemAtIndex(0).width'),
                                    expr('updatesScrollBar.x'))
        finally:
            window.close()
            self.engine.deleteLater()
            self.app.processEvents()

    def test_missing_store_icon_draws_letter_without_reference_error(self):
        self.bridge.catalogModel.replace([{
            'source': 'Flatpak', 'appId': 'org.example.Gimp',
            'providerKey': 'flatpak:org.example.Gimp',
            'name': 'GIMP', 'summary': 'Test image editor',
            'category': 'Graphics', 'iconUrl': '', 'developer': '',
            'version': '', 'license': '', 'homepage': '', 'componentId': '',
        }])
        self.engine = QtQml.QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('bridge', self.bridge)
        self.engine.rootContext().setContextProperty('appsModel', self.model)
        self.engine.addImportPath(str(manager_qml.QML_DIR.parent))
        with QmlLoadCapture() as capture:
            self.engine.load(str(manager_qml.QML_DIR / 'main.qml'))
            self.assertTrue(self.engine.rootObjects(), capture.messages)
            window = self.engine.rootObjects()[0]
            window.setProperty('discoverSelected', True)
            window.show()
            QtTest.QTest.qWait(140)
            self.app.processEvents()
            expr = lambda code: QtQml.QQmlExpression(
                QtQml.qmlContext(window), window, code).evaluate()[0]
            try:
                self.assertEqual(expr('catalogList.count'), 1)
                self.assertTrue(expr('catalogList.itemAtIndex(0) !== null'))
                self.assertTrue(expr('catalogList.itemAtIndex(0).usingFallback'))
                self.assertEqual(expr('catalogList.itemAtIndex(0).renderedInitial'), 'G')
                self.assertFalse(any('ReferenceError' in m for m in capture.messages),
                                 capture.messages)
            finally:
                window.close()
                self.engine.deleteLater()
                self.app.processEvents()

    def test_featured_overflow_pages_three_cards_without_a_scrollbar(self):
        self.bridge._catalog_source = "Flatpak"
        self.bridge._catalog_query = ""
        self.bridge._catalog_all = manager_qml.catalog_metadata.normalize_rows([{
            "source": "Flatpak", "appId": f"org.example.Featured{i}",
            "name": f"Featured Example {i}", "summary": "Sample",
            "category": "Graphics",
        } for i in range(6)])
        self.bridge._rebuild_catalog_view()
        self.engine = QtQml.QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('bridge', self.bridge)
        self.engine.rootContext().setContextProperty('appsModel', self.model)
        self.engine.addImportPath(str(manager_qml.QML_DIR.parent))
        with QmlLoadCapture() as capture:
            self.engine.load(str(manager_qml.QML_DIR / 'main.qml'))
            self.assertTrue(self.engine.rootObjects(), capture.messages)
            window = self.engine.rootObjects()[0]
            window.setProperty('discoverSelected', True)
            window.show()
            QtTest.QTest.qWait(120)
            self.app.processEvents()
            expr = lambda v: QtQml.QQmlExpression(
                QtQml.qmlContext(window), window, v).evaluate()[0]
            try:
                self.assertTrue(expr('featuredStrip.visible'))
                self.assertTrue(expr('featuredRepeater.itemAt(0) !== null'))
                self.assertEqual(expr('featuredStrip.pageCount'), 2)
                for width in (720, 800, 1024, 1440):
                    window.resize(width, 700)
                    self.app.processEvents()
                    self.assertAlmostEqual(expr(
                        'featuredRepeater.itemAt(2).mapToItem(featuredStrip, '
                        'featuredRepeater.itemAt(2).width, 0).x'), expr('featuredStrip.width'), delta=1)
                    self.assertLess(expr('catalogList.cellWidth * catalogList.columns'),
                                    expr('catalogScrollBar.x'))
                    expr('featuredStrip.page = 1')
                    self.assertAlmostEqual(expr(
                        'featuredRepeater.itemAt(3).mapToItem(featuredStrip, 0, 0).x'), 0, delta=1)
                    expr('featuredStrip.page = 0')
                self.assertGreaterEqual(
                    expr('catalogHeading.y - (featuredStrip.y + featuredStrip.height)'),
                    0)
                self.assertFalse(any('ReferenceError' in m for m in capture.messages),
                                 capture.messages)
            finally:
                window.close()
                self.engine.deleteLater()
                self.app.processEvents()

    def test_catalog_resets_new_results_and_preserves_pagination_and_metadata(self):
        def records(source):
            return [
                dict(source=source, appId=f'org.example.App{i}', name=f'App {i}',
                     providerKey=f'flatpak:org.example.App{i}', summary='Fixture',
                     category='Graphics' if i < 30 else 'Utility')
                for i in range(50)
            ]

        self.bridge._catalog_all = records('Flatpak')
        self.bridge._rebuild_catalog_view()
        self.engine = QtQml.QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('bridge', self.bridge)
        self.engine.rootContext().setContextProperty('appsModel', self.model)
        self.engine.addImportPath(str(manager_qml.QML_DIR.parent))
        self.engine.load(str(manager_qml.QML_DIR / 'main.qml'))
        window = self.engine.rootObjects()[0]
        window.resize(800, 700)
        window.setProperty('discoverSelected', True)

        def expr(code):
            expression = QtQml.QQmlExpression(QtQml.qmlContext(window), window, code)
            value, _ = expression.evaluate()
            self.assertFalse(expression.hasError(), expression.error().toString())
            return value

        def offset():
            QtTest.QTest.qWait(30)
            return expr('catalogList.contentY - catalogList.originY')

        def scroll():
            expr('catalogList.contentY = catalogList.originY + catalogList.cellHeight * 1.5')
            self.assertGreater(offset(), 0)

        try:
            self.assertAlmostEqual(offset(), 0, delta=1)
            self.assertAlmostEqual(expr('catalogList.itemAtIndex(0).mapToItem(catalogList, 0, 0).y'),
                                   0, delta=1)
            scroll()
            before = offset()
            expr('catalogViewMore.clicked()')
            self.assertEqual(self.bridge.catalogModel.count, 48)
            self.assertAlmostEqual(offset(), before, delta=1)
            expr('catalogViewMore.clicked()')
            self.assertEqual(self.bridge.catalogModel.count, 50)
            self.assertFalse(expr('catalogViewMore.visible'))
            self.assertAlmostEqual(offset(), before, delta=1)
            self.bridge._rebuild_catalog_view(preserve_page=True, reset_viewport=False)
            self.assertAlmostEqual(offset(), before, delta=1)
            category = next(value for value in self.bridge.catalogCategories if value != 'All')
            self.bridge.chooseCatalogCategory(category)
            self.assertAlmostEqual(offset(), 0, delta=1)
            self.bridge.chooseCatalogCategory('All')
            self.assertAlmostEqual(offset(), 0, delta=1)
            for query, source in (('example', 'Flatpak'), ('example', 'AppImage')):
                scroll()
                with patch.object(self.bridge, '_start_catalog_worker'):
                    self.bridge.searchCatalog(query, source)
                self.assertAlmostEqual(offset(), 0, delta=1)
                self.bridge._catalog_all = records(source)
                self.bridge._rebuild_catalog_view()
                self.assertAlmostEqual(offset(), 0, delta=1)
        finally:
            window.close()
            self.engine.deleteLater()
            self.app.processEvents()

    def test_full_details_page_hides_browse_and_restores_on_back(self):
        self.bridge._catalog_source = "Flatpak"
        self.bridge._catalog_all = manager_qml.catalog_metadata.normalize_rows([{
            "source": "Flatpak", "appId": "org.example.Test",
            "name": "Example App", "summary": "Example description",
            "developer": "Example Team", "version": "1.0",
            "license": "MIT", "category": "Utility",
        }])
        self.bridge._rebuild_catalog_view()
        self.engine = QtQml.QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("bridge", self.bridge)
        self.engine.rootContext().setContextProperty("appsModel", self.model)
        self.engine.addImportPath(str(manager_qml.QML_DIR.parent))
        with QmlLoadCapture() as capture:
            self.engine.load(str(manager_qml.QML_DIR / "main.qml"))
            self.assertTrue(self.engine.rootObjects(), capture.messages)
            window = self.engine.rootObjects()[0]
            window.setProperty("discoverSelected", True)
            window.show()
            QtTest.QTest.qWait(100)
            try:
                for name in ("catalogDetailsPage", "catalogDetailsBack",
                             "catalogDetailsInstall", "catalogHomepageButton",
                             "catalogDetailsName", "catalogDetailsDescription"):
                    self.assertIsNotNone(window.findChild(QtCore.QObject, name), name)
                evaluate = lambda v: QtQml.QQmlExpression(
                    QtQml.qmlContext(window), window, v).evaluate()[0]
                self.bridge.openCatalogDetails("org.example.Test", "Flatpak")
                self.app.processEvents()
                self.assertTrue(evaluate("catalogDetailsPage.visible"))
                self.assertFalse(evaluate("catalogList.visible"))
                self.assertEqual(evaluate("catalogDetailsName.text"), "Example App")
                self.assertEqual(evaluate("catalogDetailsDescription.text"),
                                 "Example description")
                self.assertTrue(evaluate("catalogDetailsInstall.enabled"))
                self.assertFalse(evaluate("catalogHomepageButton.visible"))
                self.bridge.closeCatalogDetails()
                self.app.processEvents()
                self.assertFalse(evaluate("catalogDetailsPage.visible"))
                self.assertTrue(evaluate("catalogList.visible"))
                self.assertFalse(any("ReferenceError" in m for m in capture.messages),
                                 capture.messages)
            finally:
                window.close()
                self.engine.deleteLater()
                self.app.processEvents()

    def test_details_responsive_compact_layout_without_duplicate_appstream(self):
        self.bridge._catalog_source = "Flatpak"
        self.bridge._catalog_all = manager_qml.catalog_metadata.normalize_rows([{
            "source": "Flatpak", "appId": "org.example.Test",
            "name": "Example App", "summary": "Short description",
            "developer": "Example Team", "license": "LicenseRef-proprietary",
            "category": "Graphics", "componentId": "org.example.Test",
        }])
        self.bridge._rebuild_catalog_view()
        self.engine = QtQml.QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("bridge", self.bridge)
        self.engine.rootContext().setContextProperty("appsModel", self.model)
        self.engine.addImportPath(str(manager_qml.QML_DIR.parent))
        with QmlLoadCapture() as capture:
            self.engine.load(str(manager_qml.QML_DIR / "main.qml"))
            self.assertTrue(self.engine.rootObjects(), capture.messages)
            window = self.engine.rootObjects()[0]
            window.setProperty("discoverSelected", True)
            window.show()
            self.bridge.openCatalogDetails("org.example.Test", "Flatpak")
            QtTest.QTest.qWait(90)
            self.app.processEvents()
            evaluate = lambda value: QtQml.QQmlExpression(
                QtQml.qmlContext(window), window, value).evaluate()[0]
            try:
                self.assertTrue(evaluate("catalogDetailsPage.visible"))
                self.assertLessEqual(evaluate("detailsContent.width"), 1050)
                self.assertLess(evaluate("catalogDetailsHero.height"), 170)
                self.assertLess(evaluate("detailsAboutCard.height"), 200)
                self.assertEqual(evaluate("catalogDetailsName.text"), "Example App")
                self.assertEqual(evaluate("detailsIdentityCard.height"), 119)
                self.assertEqual(evaluate("detailsColumns.columns"), 2)
                window.setWidth(740)
                QtTest.QTest.qWait(100)
                self.app.processEvents()
                self.assertEqual(evaluate("detailsColumns.columns"), 1)
                self.assertGreater(evaluate("catalogDetailsHero.width"), 0)
                window.setWidth(1250)
                QtTest.QTest.qWait(100)
                self.app.processEvents()
                self.assertEqual(evaluate("detailsColumns.columns"), 2)
                self.assertLessEqual(evaluate("detailsContent.width"), 1050)
                self.assertFalse(any("ReferenceError" in m or "Binding loop" in m
                                     for m in capture.messages), capture.messages)
            finally:
                window.close()
                self.engine.deleteLater()
                self.app.processEvents()

    def test_discover_switches_pages_and_keeps_header(self):
        self.engine = QtQml.QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('bridge', self.bridge)
        self.engine.rootContext().setContextProperty('appsModel', self.model)
        self.engine.addImportPath(str(manager_qml.QML_DIR.parent))
        with QmlLoadCapture() as capture:
            self.engine.load(str(manager_qml.QML_DIR / 'main.qml'))
        self.assertTrue(self.engine.rootObjects(), capture.messages)
        window = self.engine.rootObjects()[0]
        window.show()
        QtTest.QTest.qWait(70)
        try:
            for name in ('pageNavigation', 'managedTab', 'discoverTab',
                         'discoverPanel', 'catalogList', 'catalogSearchField',
                         'catalogRetry', 'catalogViewMore', 'flatpakSourceButton',
                         'appimageSourceButton', 'debSourceButton', 'rpmSourceButton',
                         'repositorySetupPanel', 'repositoryEnableButton',
                         'categoryStrip', 'featuredStrip',
                         'featuredHeading',
                         'contentArea', 'appMenuBar'):
                self.assertIsNotNone(window.findChild(QtCore.QObject, name), name)
            expr = lambda v: QtQml.QQmlExpression(
                QtQml.qmlContext(window), window, v).evaluate()[0]
            self.assertFalse(expr('discoverPanel.visible'))
            self.assertTrue(expr('contentArea.visible'))
            self.assertTrue(expr('menuToggle.visible'))
            window.setProperty('discoverSelected', True)
            self.app.processEvents()
            self.assertTrue(expr('discoverPanel.visible'))
            self.assertGreaterEqual(expr('catalogList.columns'), 1)
            self.assertFalse(expr('contentArea.visible'))
            self.assertFalse(expr('filtersPanel.visible'))
            self.assertTrue(expr('menuToggle.visible'))
            window.setProperty('discoverSelected', False)
            self.app.processEvents()
            self.assertTrue(expr('contentArea.visible'))
            self.assertFalse(expr('discoverPanel.visible'))
            self.assertFalse(any('Error' in m for m in capture.messages),
                             capture.messages)
        finally:
            window.close()
            self.engine.deleteLater()
            self.app.processEvents()


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


class QmlInteractionTests(QmlManagerBase):
    def setUp(self):
        super().setUp()
        self.load_inventory([
            (f'appimage:app{i}', self.stage_installed_appimage(
                f'appimage:app{i}', f'{i:02d} ' + ('Long name ' * 30 if i == 0 else 'App')))
            for i in range(40)
        ])
        self.engine = QtQml.QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('bridge', self.bridge)
        self.engine.rootContext().setContextProperty('appsModel', self.model)
        self.engine.addImportPath(str(manager_qml.QML_DIR.parent))
        self.engine.load(str(manager_qml.QML_DIR / 'main.qml'))
        self.window = self.engine.rootObjects()[0]
        self.window.setWidth(720)
        self.window.setHeight(600)
        self.window.show()
        QtTest.QTest.qWait(100)

    def tearDown(self):
        self.window.close()
        self.engine.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        super().tearDown()

    def evaluate(self, expression, scope=None):
        scope = scope or self.window
        expr = QtQml.QQmlExpression(QtQml.qmlContext(scope), scope, expression)
        value, _ = expr.evaluate()
        self.assertFalse(expr.hasError(), expr.error().toString())
        return value

    def card(self):
        # A child belongs to AppCard's own component context (its private ids),
        # whereas the delegate root belongs to main.qml's delegate context.
        return self.evaluate('appList.currentItem').childItems()[0]

    def press(self, key):
        QtTest.QTest.keyClick(self.window, key)
        QtTest.QTest.qWait(30)

    def assert_current_visible(self, index):
        self.assertEqual(self.evaluate('appList.currentIndex'), index)
        self.assertTrue(self.evaluate('appList.currentItem.activeFocus'))
        self.assertTrue(self.evaluate('appList.currentItem.y >= appList.contentY - 1'
                                     ' && appList.currentItem.y + appList.currentItem.height'
                                     ' <= appList.contentY + appList.height + 1'))

    def test_long_name_keeps_actions_inside_narrow_window(self):
        card = self.card()
        self.assertTrue(self.evaluate('nameLabel.truncated', card))
        for button in ('openButton', 'moreButton'):
            self.assertTrue(self.evaluate(
                f'{button}.mapToItem(card, 0, 0).x + {button}.width <= card.width', card), button)
        # Short names show in full; only genuinely long names elide.
        self.evaluate('appList.focusCard(1)')
        QtTest.QTest.qWait(30)
        self.assertFalse(self.evaluate('nameLabel.truncated', self.card()))

    def test_tab_then_arrows_tracks_focused_card_and_scrolls(self):
        self.evaluate('appList.focusCard(0)')
        self.press(QtCore.Qt.Key_Tab)
        self.assert_current_visible(1)
        self.press(QtCore.Qt.Key_Down)
        self.assert_current_visible(2)
        for index in range(3, 15):
            self.press(QtCore.Qt.Key_Tab)
            self.assert_current_visible(index)
        self.press(QtCore.Qt.Key_Up)
        self.assert_current_visible(13)

    def test_end_home_focus_offscreen_delegates(self):
        self.evaluate('appList.focusCard(0)')
        self.press(QtCore.Qt.Key_End)
        self.assert_current_visible(39)
        self.press(QtCore.Qt.Key_Home)
        self.assert_current_visible(0)

    def test_card_context_menu_keyboard_shortcuts(self):
        for key, modifiers in ((QtCore.Qt.Key_Menu, QtCore.Qt.NoModifier),
                               (QtCore.Qt.Key_F10, QtCore.Qt.ShiftModifier)):
            self.evaluate('appList.focusCard(0)')
            QtTest.QTest.keyClick(self.window, key, modifiers)
            QtTest.QTest.qWait(30)
            self.assertTrue(self.evaluate('moreMenu.visible', self.card()), str(key))
            self.evaluate('moreMenu.close()', self.card())

    def test_card_describes_keyboard_actions(self):
        description = self.evaluate('card.Accessible.description', self.card())
        primary = 'Open' if self.evaluate('card.canLaunch', self.card()) else 'Review'
        self.assertEqual(self.evaluate('openButton.text', self.card()), primary)
        for action in ('Enter', primary, 'Space', 'Details', 'Menu', 'Shift+F10'):
            self.assertIn(action, description)

    def _click_dropdown_option(self, button, popup, repeater, index):
        """Test an actual button click followed by a popup option click."""
        if button == 'statusFilter':
            self.window.setProperty('advancedFilters', True)
            self.app.processEvents()
        trigger = self.evaluate(button)
        point = trigger.mapToScene(QtCore.QPointF(
            trigger.width() / 2, trigger.height() / 2)).toPoint()
        QtTest.QTest.mouseClick(self.window, QtCore.Qt.LeftButton, pos=point)
        QtTest.QTest.qWait(100)
        self.assertTrue(self.evaluate(f'{popup}.visible'))
        self.assertGreater(self.evaluate(f'{popup}.height'), 40)
        option = self.evaluate(f'{repeater}.itemAt({index})')
        self.assertIsNotNone(option, f'{popup} choice {index} missing')
        point = option.mapToScene(
            QtCore.QPointF(option.width() / 2, option.height() / 2)).toPoint()
        QtTest.QTest.mouseClick(self.window, QtCore.Qt.LeftButton, pos=point)
        QtTest.QTest.qWait(80)
        self.assertEqual(self.evaluate(f'{button}.selectedIndex'), index)
        self.assertFalse(self.evaluate(f'{popup}.visible'))

    def test_status_dropdown_mouse_select_filters_inventory(self):
        self._click_dropdown_option('statusFilter', 'statusPopup', 'statusRepeater', 4)
        self.assertEqual(self.model.rowCount(), 0)
        self._click_dropdown_option('statusFilter', 'statusPopup', 'statusRepeater', 0)
        self.assertEqual(self.model.rowCount(), 40)

    def test_sort_dropdown_mouse_select_reorders_inventory(self):
        self._click_dropdown_option('sortCombo', 'sortPopup', 'sortRepeater', 1)
        self.assertTrue(
            self.model.data(self.model.index(0, 0), self.model.NameRole).startswith('39 '))
        self._click_dropdown_option('sortCombo', 'sortPopup', 'sortRepeater', 0)
        self.assertTrue(
            self.model.data(self.model.index(0, 0), self.model.NameRole).startswith('00 '))

    def test_status_dropdown_keyboard_navigation(self):
        self.window.setProperty('advancedFilters', True)
        self.evaluate('statusFilter.forceActiveFocus()')
        QtTest.QTest.keyClick(self.window, QtCore.Qt.Key_Space)
        QtTest.QTest.qWait(100)
        self.assertTrue(self.evaluate('statusPopup.visible'))
        QtTest.QTest.keyClick(self.window, QtCore.Qt.Key_Down)
        QtTest.QTest.keyClick(self.window, QtCore.Qt.Key_Return)
        QtTest.QTest.qWait(80)
        self.assertEqual(self.evaluate('statusFilter.selectedIndex'), 1)
        self.assertEqual(self.model.rowCount(), 40)
        self.assertFalse(self.evaluate('statusPopup.visible'))
        self.evaluate('statusPopup.open()')
        QtTest.QTest.qWait(100)
        QtTest.QTest.keyClick(self.window, QtCore.Qt.Key_Escape)
        QtTest.QTest.qWait(60)
        self.assertFalse(self.evaluate('statusPopup.visible'))

    def test_hovered_card_is_neutral_in_dark_mode(self):
        self.evaluate('Theme.mode = "dark"')
        card = self.card()
        point = card.mapToScene(QtCore.QPointF(8, 8)).toPoint()
        QtTest.QTest.mouseMove(self.window, point)
        QtTest.QTest.qWait(220)
        self.assertTrue(self.evaluate('card.hovered', card))
        color = self.evaluate('cardSurface.color', card)
        self.assertIsInstance(color, QtGui.QColor)
        self.assertEqual(color.alpha(), 255)
        self.assertLess(max(color.red(), color.green(), color.blue()), 100,
                        'Hovered card must never turn bright yellow')

    def test_translucent_theme_tokens_use_qt_argb_order(self):
        for mode in ('light', 'dark'):
            self.evaluate(f'Theme.mode = "{mode}"')
            for token in ('hover', 'pressed', 'successBg', 'warningBg',
                          'dangerBg', 'neutralBg', 'shadow'):
                value = self.evaluate(f'Theme.colors.{token}')
                color = QtGui.QColor(value)
                self.assertTrue(color.isValid(), f'{mode}.{token}')
                self.assertLessEqual(color.alpha(), 64, f'{mode}.{token}')

    def test_checked_filter_text_contrast_in_both_themes_and_states(self):
        def luminance(channels):
            linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
                      for c in channels]
            return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

        for theme in ('light', 'dark'):
            self.evaluate(f'Theme.mode = "{theme}"')
            chip = self.evaluate('managedTab')
            point = chip.mapToScene(QtCore.QPointF(chip.width() / 2, chip.height() / 2)).toPoint()
            for state in ('normal', 'hover', 'pressed'):
                with self.subTest(theme=theme, state=state):
                    QtTest.QTest.mouseMove(self.window, QtCore.QPoint(1, 1) if state == 'normal' else point)
                    if state == 'pressed':
                        QtTest.QTest.mousePress(self.window, QtCore.Qt.LeftButton, pos=point)
                    QtTest.QTest.qWait(220)
                    self.assertTrue(chip.property('highlighted'))
                    self.assertEqual(chip.property('hovered'), state != 'normal')
                    foreground = chip.property('contentItem').property('color')
                    background = chip.property('background').property('color')
                    base = self.window.property('color')
                    alpha = background.alphaF()
                    blended = [a * alpha + b * (1 - alpha) for a, b in
                               zip(background.getRgbF()[:3], base.getRgbF()[:3])]
                    values = (luminance(foreground.getRgbF()[:3]), luminance(blended))
                    ratio = (max(values) + 0.05) / (min(values) + 0.05)
                    self.assertGreaterEqual(ratio, 4.5, f'{theme} {state}: {ratio:.2f}:1')
                    if state == 'pressed':
                        QtTest.QTest.mouseRelease(self.window, QtCore.Qt.LeftButton, pos=point)


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
