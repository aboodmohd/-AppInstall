"""Manager list view tests: status filter, sorting, favorites, sizes, theme.

Offscreen Qt regressions for the My Applications window additions. All
registry, settings and package files live under a disposable XDG tree; no
real user data is read or written. Flatpak inventory queries are patched so
results never depend on the host's Flatpak installation.
"""
import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location('manager', ROOT / 'manager.py')
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)

import settings as settings_mod


def write_registry(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2))


def make_app(key='appimage:example', fmt='appimage', **overrides):
    raw = dict(format=fmt, name='Example App', version='1.0',
               desktop='/home/user/.local/share/applications/example.desktop',
               icon='', icon_name='example', container=None,
               manifest=None, target='/home/user/Applications/Example.AppImage',
               description='An example application.', status='installed')
    raw.update(overrides)
    return key, raw


def card_menu(card):
    from qt_compat import QtWidgets
    for button in card.findChildren(QtWidgets.QPushButton):
        if button.text() == '⋮' and button.menu() is not None:
            return button.menu()
    return None


def trigger_action(menu, text):
    for action in menu.actions():
        if action.text() == text:
            action.trigger()
            return True
    return False


class WindowBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.environment = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_STATE_HOME': str(self.root / 'state'),
        })
        self.environment.start()
        from qt_compat import QtWidgets
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        self.window = manager.ManagerWindow()
        self.wait_for(lambda: self.window.loader is not None and
                      not self.window.loader.isRunning())

    def tearDown(self):
        self.wait_for(lambda: not self.window.loader.isRunning())
        self.window.close()
        self.app.processEvents()
        self.environment.stop()
        self.temp.cleanup()

    def wait_for(self, condition, timeout=6):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition():
                return
            time.sleep(.02)
        self.fail('condition not reached in time')

    def stage_installed_appimage(self, key, name):
        """Real target and desktop files so the record validates as installed."""
        stem = key.split(':', 1)[-1]
        target = self.root / 'apps' / (stem + '.AppImage')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'\x7fELF-managed-appimage')
        desktop = self.root / 'entries' / (stem + '.desktop')
        desktop.parent.mkdir(parents=True, exist_ok=True)
        desktop.write_text('[Desktop Entry]\nType=Application\nName=' + name + '\n')
        return dict(format='appimage', name=name, version='1.0',
                    desktop=str(desktop), icon='', icon_name=stem,
                    container=None, manifest=None, target=str(target),
                    description='', status='installed')


class SizeHelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        from qt_compat import QtWidgets
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def tearDown(self):
        self.temp.cleanup()

    def test_appimage_size_is_the_generation_file(self):
        target = self.root / 'x.AppImage'
        target.write_bytes(b'\x00' * 1536)
        app = manager.build_app_record(*make_app(target=str(target)), 'x')
        self.assertEqual(manager.app_disk_usage(app), 1536)

    def test_missing_target_is_unknown(self):
        app = manager.build_app_record(
            *make_app(target='/nonexistent/x.AppImage'), 'x')
        self.assertIsNone(manager.app_disk_usage(app))

    def test_flatpak_and_container_records_have_no_per_app_size(self):
        flatpak = manager.build_app_record(
            *make_app('flatpak:org.a', 'flatpak'), 'x')
        self.assertIsNone(manager.app_disk_usage(flatpak))
        deb = manager.build_app_record(*make_app('deb:b', 'deb'), 'x')
        self.assertIsNone(manager.app_disk_usage(deb))

    def test_format_size_units(self):
        self.assertEqual(manager.format_size(None), '—')
        self.assertEqual(manager.format_size(950), '950 B')
        self.assertEqual(manager.format_size(1536), '1.5 KB')
        self.assertEqual(manager.format_size(5*1024*1024), '5.0 MB')
        self.assertEqual(manager.format_size(3*1024*1024*1024), '3.0 GB')

    def test_details_dialog_shows_disk_usage(self):
        from qt_compat import QtWidgets
        target = self.root / 'x.AppImage'
        target.write_bytes(b'\x00' * 2048)
        app = manager.build_app_record(*make_app(target=str(target)), 'x')
        dialog = manager.AppDetailsDialog(app)
        labels = [label.text() for label in dialog.findChildren(QtWidgets.QLabel)]
        self.assertTrue(any('2.0 KB' in text for text in labels),
                        'package size missing from details: '+repr(labels))
        dialog.deleteLater()


class StatusFilterTests(WindowBase):
    def populate(self):
        installed = self.stage_installed_appimage('appimage:good', 'Good App')
        missing = dict(format='appimage', name='Broken App', version='1.0',
                       desktop='/nonexistent/broken.desktop', icon='',
                       icon_name='broken', container=None, manifest=None,
                       target='/nonexistent/broken.AppImage',
                       description='', status='installed')
        flatpak = dict(format='flatpak', name='Flat App', version='2.0',
                       desktop='', icon='', icon_name='flat', container=None,
                       manifest=None, target='', description='', status='installed')
        write_registry(manager.launch_registry_path(), {
            'appimage:good': installed,
            'appimage:broken': missing,
            'flatpak:org.flat.App': flatpak,
        })

    def load(self):
        # Inventory status must not depend on the host Flatpak installation.
        with patch.object(manager, '_flatpak_installed', return_value=None):
            self.window._check_inventory_changes()
            self.wait_for(lambda: len(self.window.inventory) == 3 and
                          not self.window.loader.isRunning())

    def test_status_filter_selects_only_matching_records(self):
        self.populate()
        self.load()
        self.window.status_filter.setCurrentIndex(
            self.window.status_filter.findData(manager.STATUS_MISSING))
        self.assertEqual([a['key'] for a in self.window.filtered],
                         ['appimage:broken'])
        self.window.status_filter.setCurrentIndex(
            self.window.status_filter.findData(manager.STATUS_INSTALLED))
        self.assertEqual(sorted(a['key'] for a in self.window.filtered),
                         ['appimage:good', 'flatpak:org.flat.App'])
        self.window.status_filter.setCurrentIndex(0)
        self.assertEqual(len(self.window.filtered), 3)

    def test_status_filter_combines_with_format_and_search(self):
        self.populate()
        self.load()
        self.window._set_filter('appimage')
        self.window.search.setText('good')
        self.assertEqual([a['key'] for a in self.window.filtered],
                         ['appimage:good'])
        self.window.search.setText('zzz-no-match')
        self.assertEqual(self.window.filtered, [])
        self.window.search.setText('')
        self.window.status_filter.setCurrentIndex(
            self.window.status_filter.findData(manager.STATUS_MISSING))
        self.assertEqual([a['key'] for a in self.window.filtered],
                         ['appimage:broken'])


class SortTests(WindowBase):
    def records(self):
        built = []
        history = {
            'appimage:mango': [{'started': '2026-01-01T10:00:00'}],
            'appimage:apple': [{'started': '2026-03-01T09:00:00'}],
            'appimage:banana': [{'started': '2026-02-01T08:00:00'}],
        }
        with patch.object(manager.monitor, 'history',
                          side_effect=lambda key: history.get(key, [])):
            for key, name in (('appimage:mango', 'Mango'),
                              ('appimage:apple', 'apple'),
                              ('appimage:banana', 'Banana')):
                built.append(manager.build_app_record(
                    key, self.stage_installed_appimage(key, name), 'x'))
        return built

    def test_name_sort_ascending_and_descending(self):
        self.window.inventory = self.records()
        self.window._refilter()
        self.assertEqual([a['name'] for a in self.window.filtered],
                         ['apple', 'Banana', 'Mango'])
        self.window.sort_combo.setCurrentIndex(
            self.window.sort_combo.findData('name-desc'))
        self.assertEqual([a['name'] for a in self.window.filtered],
                         ['Mango', 'Banana', 'apple'])

    def test_recent_sort_uses_last_launch(self):
        self.window.inventory = self.records()
        self.window._refilter()
        self.window.sort_combo.setCurrentIndex(
            self.window.sort_combo.findData('recent'))
        self.assertEqual([a['key'] for a in self.window.filtered],
                         ['appimage:apple', 'appimage:banana', 'appimage:mango'])

    def test_size_sort_puts_largest_first_and_unknown_last(self):
        apps = self.records()
        big = self.root / 'big.AppImage'
        big.write_bytes(b'\x00' * 4096)
        small = self.root / 'small.AppImage'
        small.write_bytes(b'\x00' * 1024)
        apps[0]['target'] = str(big)      # mango: 4096 bytes
        apps[1]['target'] = str(small)    # apple: 1024 bytes
        apps[2]['target'] = '/nonexistent/banana.AppImage'  # unknown
        self.window.inventory = apps
        self.window._refilter()
        self.window.sort_combo.setCurrentIndex(
            self.window.sort_combo.findData('size'))
        self.assertEqual([a['key'] for a in self.window.filtered],
                         ['appimage:mango', 'appimage:apple', 'appimage:banana'])

    def test_sort_survives_registry_refresh(self):
        records = {'appimage:mango': self.stage_installed_appimage('appimage:mango', 'Mango'),
                   'appimage:apple': self.stage_installed_appimage('appimage:apple', 'apple'),
                   'appimage:banana': self.stage_installed_appimage('appimage:banana', 'Banana')}
        write_registry(manager.launch_registry_path(), records)
        self.window._check_inventory_changes()
        self.wait_for(lambda: len(self.window.inventory) == 3 and
                      not self.window.loader.isRunning())
        self.window.sort_combo.setCurrentIndex(
            self.window.sort_combo.findData('name-desc'))
        self.assertEqual([a['name'] for a in self.window.filtered],
                         ['Mango', 'Banana', 'apple'])
        # An external installer atomically replaced the registry: the loader
        # must rebuild the list with the chosen sort still applied.
        temporary = manager.launch_registry_path().with_suffix('.new')
        write_registry(temporary, records)
        temporary.replace(manager.launch_registry_path())
        self.window._check_inventory_changes()
        self.wait_for(lambda: len(self.window.inventory) == 3 and
                      not self.window.loader.isRunning())
        self.assertEqual([a['name'] for a in self.window.filtered],
                         ['Mango', 'Banana', 'apple'])


class FavoriteTests(WindowBase):
    def populated_records(self):
        return {'appimage:zebra': self.stage_installed_appimage('appimage:zebra', 'Zebra'),
                'appimage:alpha': self.stage_installed_appimage('appimage:alpha', 'Alpha')}

    def test_pre_existing_favorite_sorts_first_with_star(self):
        write_registry(manager.launch_registry_path(), self.populated_records())
        write_registry(settings_mod.settings_path(),
                       {'theme': 'auto', 'favorites': ['appimage:zebra'],
                        'notifications': False})
        # Favorites load when the manager opens: a window constructed after
        # the settings file exists must pin on first display.
        window = manager.ManagerWindow()
        self.wait_for(lambda: window.loader is not None and
                      not window.loader.isRunning() and
                      len(window.inventory) == 2)
        self.assertEqual([a['key'] for a in window.filtered],
                         ['appimage:zebra', 'appimage:alpha'])
        card = window.cards['appimage:zebra']
        self.assertTrue(card.pinned)
        self.assertTrue(card.name.text().startswith('★ '))
        window.close()
        window.deleteLater()
        self.app.processEvents()

    def test_pin_and_unpin_update_settings_and_order(self):
        write_registry(manager.launch_registry_path(), self.populated_records())
        self.window._check_inventory_changes()
        self.wait_for(lambda: len(self.window.inventory) == 2 and
                      not self.window.loader.isRunning())
        self.assertEqual([a['key'] for a in self.window.filtered],
                         ['appimage:alpha', 'appimage:zebra'])

        card = self.window.cards['appimage:zebra']
        menu = card_menu(card)
        self.assertIsNotNone(menu)
        labels = [action.text() for action in menu.actions()]
        self.assertIn('Pin to top', labels)
        self.assertNotIn('Unpin from top', labels)
        self.assertTrue(trigger_action(menu, 'Pin to top'))
        self.app.processEvents()
        self.wait_for(lambda: [a['key'] for a in self.window.filtered] ==
                      ['appimage:zebra', 'appimage:alpha'])
        self.assertEqual(settings_mod.read()['favorites'], ['appimage:zebra'])
        self.assertTrue(self.window.cards['appimage:zebra'].name.text().startswith('★ '))

        menu = card_menu(self.window.cards['appimage:zebra'])
        self.assertIn('Unpin from top', [action.text() for action in menu.actions()])
        self.assertTrue(trigger_action(menu, 'Unpin from top'))
        self.app.processEvents()
        self.wait_for(lambda: [a['key'] for a in self.window.filtered] ==
                      ['appimage:alpha', 'appimage:zebra'])
        self.assertEqual(settings_mod.read()['favorites'], [])


class ThemeTests(WindowBase):
    def test_dark_selection_persists_and_recolours_application(self):
        from qt_compat import QtGui
        native = QtGui.QPalette(self.app.palette())
        self.window.theme_actions['dark'].trigger()
        self.assertEqual(settings_mod.read()['theme'], 'dark')
        self.assertTrue(self.window.theme_actions['dark'].isChecked())
        self.assertFalse(self.window.theme_actions['auto'].isChecked())
        self.assertEqual(
            self.app.palette().color(QtGui.QPalette.ColorRole.Window).name(),
            '#31363b')

        self.window.theme_actions['auto'].trigger()
        self.assertEqual(settings_mod.read()['theme'], 'auto')
        self.assertTrue(self.window.theme_actions['auto'].isChecked())
        self.assertEqual(
            self.app.palette().color(QtGui.QPalette.ColorRole.Window),
            native.color(QtGui.QPalette.ColorRole.Window))

    def test_light_selection_uses_light_palette(self):
        from qt_compat import QtGui
        self.window.theme_actions['light'].trigger()
        self.assertEqual(settings_mod.read()['theme'], 'light')
        window_color = self.app.palette().color(QtGui.QPalette.ColorRole.Window)
        self.assertGreater(window_color.lightness(), 200)
        self.window.theme_actions['auto'].trigger()
        self.assertEqual(settings_mod.read()['theme'], 'auto')

    def test_new_window_reflects_saved_theme_menu(self):
        settings_mod.write({'theme': 'dark', 'favorites': [],
                            'notifications': False})
        window = manager.ManagerWindow()
        self.wait_for(lambda: window.loader is not None and
                      not window.loader.isRunning())
        self.assertTrue(window.theme_actions['dark'].isChecked())
        self.assertFalse(window.theme_actions['auto'].isChecked())
        window.close()
        window.deleteLater()
        self.app.processEvents()


if __name__ == '__main__':
    unittest.main()
