"""Phase 5: Installed Applications Manager — inventory and action tests.

All tests run under isolated XDG_DATA_HOME/XDG_STATE_HOME so no real user
registry, launcher or launch history is read, written or deleted.
"""
import importlib.util
import json
import os
import hashlib
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location('manager', ROOT / 'manager.py')
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


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


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_STATE_HOME': str(self.root / 'state'),
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_empty_inventory(self):
        apps = manager.load_inventory()
        self.assertEqual(apps, [])

    def test_container_registry_only(self):
        write_registry(manager.container_registry_path(), {
            'deb:example': make_app('deb:example', 'deb', container='debian-apps',
                                    target='/tmp/staged/example.deb')[1]
        })
        apps = manager.load_inventory()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]['package_id'], 'deb:example')
        self.assertEqual(apps[0]['format'], 'deb')
        self.assertEqual(apps[0]['source'], 'container-registry')

    def test_launch_registry_only(self):
        write_registry(manager.launch_registry_path(), {
            'appimage:example': make_app()[1]
        })
        apps = manager.load_inventory()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]['package_id'], 'appimage:example')
        self.assertEqual(apps[0]['source'], 'launch-monitor')

    def test_container_wins_over_launch_duplicate(self):
        write_registry(manager.container_registry_path(), {
            'appimage:example': make_app('appimage:example', 'appimage')[1],
        })
        write_registry(manager.launch_registry_path(), {
            'appimage:example': make_app('appimage:example-dupe', 'appimage',
                                         name='Duplicate App')[1],
        })
        apps = manager.load_inventory()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]['name'], 'Example App')

    def test_missing_launcher_is_flagged_stale(self):
        target = self.root / 'Example.AppImage'
        target.write_bytes(b'elf')
        write_registry(manager.launch_registry_path(), {
            'appimage:example': make_app(desktop='/nonexistent/example.desktop',
                                         target=str(target))[1],
        })
        apps = manager.load_inventory()
        self.assertEqual(len(apps), 1)
        self.assertIn('launcher missing', apps[0]['problems'])
        self.assertEqual(apps[0]['status'], manager.STATUS_STALE)

    def test_missing_appimage_file_is_missing(self):
        write_registry(manager.launch_registry_path(), {
            'appimage:example': make_app(target='/nonexistent/Example.AppImage')[1],
        })
        apps = manager.load_inventory()
        self.assertEqual(apps[0]['status'], manager.STATUS_MISSING)
        self.assertIn('application file missing', apps[0]['problems'])

    def test_corrupted_record(self):
        write_registry(manager.launch_registry_path(), {
            'appimage:example': make_app(status='corrupted')[1],
        })
        apps = manager.load_inventory()
        self.assertEqual(apps[0]['status'], manager.STATUS_CORRUPTED)

    def test_container_launcher_found_via_exports(self):
        """Container record whose desktop path is missing but whose export
        launcher exists on disk is still 'installed'."""
        key, raw = make_app('deb:example', 'deb', container='debian-apps',
                            target='/tmp/staged/example.deb',
                            desktop='/nonexistent/system/freebuff.desktop')
        # The real managed launcher lives in exports, not the system path.
        raw['exports'] = [{'path': str(self.root / 'debian-apps-example.desktop'), 'sha256': 'deadbeef'}]
        (self.root / 'debian-apps-example.desktop').write_text('[Desktop Entry]\nType=Application\nName=Example\n')
        write_registry(manager.container_registry_path(), {key: raw})
        apps = manager.load_inventory()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]['status'], manager.STATUS_INSTALLED)
        self.assertNotIn('launcher missing', apps[0]['problems'])

    def test_desktop_path_resolved_via_exports(self):
        """Container record's desktop path falls back to exports path when
        the recorded system path does not exist on disk."""
        key, raw = make_app('deb:example', 'deb', container='debian-apps',
                            target='/tmp/staged/example.deb',
                            desktop='/nonexistent/system/freebuff.desktop')
        export_path = str(self.root / 'debian-apps-example.desktop')
        raw['exports'] = [{'path': export_path, 'sha256': 'deadbeef'}]
        (self.root / 'debian-apps-example.desktop').write_text('[Desktop Entry]\nType=Application\nName=Example\n')
        write_registry(manager.container_registry_path(), {key: raw})
        apps = manager.load_inventory()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]['desktop'], export_path)

    def test_description_junk_is_hidden(self):
        """A description that is only whitespace or a stray '.' is treated
        as empty and not displayed."""
        key, raw = make_app(description='\n.')
        app = manager.build_app_record(key, raw, 'launch-monitor')
        self.assertEqual(app['description'], '')

        key2, raw2 = make_app(description='  \n  ')
        app2 = manager.build_app_record(key2, raw2, 'launch-monitor')
        self.assertEqual(app2['description'], '')

        key3, raw3 = make_app(description='A real description.')
        app3 = manager.build_app_record(key3, raw3, 'launch-monitor')
        self.assertEqual(app3['description'], 'A real description.')

    def test_launch_status_mapped_to_friendly_text(self):
        """Raw launch status strings are shown as user-friendly text."""
        self.assertEqual(manager._friendly_launch_status('detached_or_exited_unverified'),
                         'Launch unverified')
        self.assertEqual(manager._friendly_launch_status('running_unverified'),
                         'Running (unverified)')
        self.assertEqual(manager._friendly_launch_status('failed'), 'Failed')
        self.assertEqual(manager._friendly_launch_status('Never launched'), 'Never launched')
        self.assertEqual(manager._friendly_launch_status('weird_status'), 'weird_status')

    def test_appimage_target_resolved_from_manifest(self):
        """AppImage target missing from the launch record is read from the manifest."""
        target = self.root / 'Example.AppImage'
        target.write_bytes(b'elf')
        manifest = self.root / 'example.json'
        manifest.write_text(json.dumps(dict(target=str(target), args=[], fallback='',
                                            generation=str(self.root))))
        desktop = self.root / 'example.desktop'
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Example\n')
        key, raw = make_app('appimage:example', 'appimage', manifest=str(manifest),
                            target='', desktop=str(desktop))
        write_registry(manager.launch_registry_path(), {key: raw})
        apps = manager.load_inventory()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]['target'], str(target))
        self.assertEqual(apps[0]['status'], manager.STATUS_INSTALLED)

    def test_unknown_status_no_problems_becomes_installed(self):
        desktop = self.root / 'example.desktop'
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Example\n')
        key, raw = make_app(fmt='flatpak', desktop=str(desktop), target='')
        raw.pop('status', None)
        write_registry(manager.launch_registry_path(), {key: raw})
        apps = manager.load_inventory()
        self.assertEqual(apps[0]['status'], manager.STATUS_INSTALLED)

    def test_inventory_sorted_by_name(self):
        write_registry(manager.launch_registry_path(), {
            'appimage:alpha': make_app('appimage:alpha', 'appimage', name='Zeta App')[1],
            'appimage:beta': make_app('appimage:beta', 'appimage', name='Alpha App')[1],
        })
        apps = manager.load_inventory()
        self.assertEqual([a['name'] for a in apps], ['Alpha App', 'Zeta App'])

    def test_formats_summary(self):
        write_registry(manager.launch_registry_path(), {
            'appimage:a': make_app('appimage:a', 'appimage')[1],
            'appimage:b': make_app('appimage:b', 'appimage')[1],
            'flatpak:c': make_app('flatpak:c', 'flatpak')[1],
        })
        apps = manager.load_inventory()
        summary = manager.formats_summary(apps)
        self.assertEqual(summary['appimage'], 2)
        self.assertEqual(summary['flatpak'], 1)
        self.assertEqual(summary['deb'], 0)

    def test_last_launch_and_error_surface(self):
        state = Path(os.environ['XDG_STATE_HOME']) / 'appinstall'
        digest = hashlib.sha256(b'appimage:example').hexdigest()[:20]
        launch_dir = state / 'launches' / digest
        launch_dir.mkdir(parents=True)
        attempt = dict(id='abc', key='appimage:example', name='Example App',
                       format='appimage', started='2026-01-01T00:00:00+00:00',
                       status='failed', error=dict(category='crash',
                       detail='The application exited unexpectedly during startup.'))
        (launch_dir / 'abc.json').write_text(json.dumps(attempt))
        write_registry(manager.launch_registry_path(), {
            'appimage:example': make_app()[1],
        })
        apps = manager.load_inventory()
        self.assertIsNotNone(apps[0]['last_launch'])
        self.assertEqual(apps[0]['last_error']['category'], 'crash')

    def test_non_dict_records_are_skipped(self):
        write_registry(manager.launch_registry_path(), {
            'appimage:example': 'not a dict',
            'appimage:valid': make_app()[1],
        })
        apps = manager.load_inventory()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]['package_id'], 'appimage:valid')


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_STATE_HOME': str(self.root / 'state'),
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_build_app_record_unknown_version(self):
        key, raw = make_app()
        del raw['version']
        app = manager.build_app_record(key, raw, 'launch-monitor')
        self.assertEqual(app['version'], 'unknown')

    def test_can_uninstall_formats(self):
        for fmt in ('appimage', 'flatpak', 'deb', 'rpm'):
            key, raw = make_app(fmt=fmt)
            self.assertTrue(manager.can_uninstall(manager.build_app_record(key, raw, 'x')))

    def test_can_reinstall_appimage_without_file(self):
        key, raw = make_app(target='/nonexistent/x.AppImage')
        app = manager.build_app_record(key, raw, 'x')
        self.assertFalse(manager.can_reinstall(app))

    def test_can_reinstall_appimage_with_file(self):
        target = self.root / 'x.AppImage'
        target.write_bytes(b'elf')
        key, raw = make_app(target=str(target))
        app = manager.build_app_record(key, raw, 'x')
        self.assertTrue(manager.can_reinstall(app))

    def test_can_update_only_flatpak(self):
        key, raw = make_app(fmt='flatpak', appid='com.example.App')
        app = manager.build_app_record(key, raw, 'x')
        self.assertTrue(manager.can_update(app))
        key2, raw2 = make_app(fmt='deb')
        app2 = manager.build_app_record(key2, raw2, 'x')
        self.assertFalse(manager.can_update(app2))

    def test_find_app(self):
        apps = [manager.build_app_record(*make_app('appimage:a'), 'x'),
                manager.build_app_record(*make_app('appimage:b'), 'x')]
        self.assertIsNone(manager.find_app(apps, 'nope'))
        self.assertEqual(manager.find_app(apps, 'appimage:a')['package_id'], 'appimage:a')


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_STATE_HOME': str(self.root / 'state'),
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_uninstall_appimage(self):
        key, raw = make_app()
        app = manager.build_app_record(key, raw, 'launch-monitor')
        calls = []
        with patch.object(manager.core, 'uninstall', side_effect=lambda k: calls.append(k)):
            message = manager.uninstall_app(app)
        self.assertEqual(calls, [key])
        self.assertIn('removed', message.lower())

    def test_uninstall_unsupported_format(self):
        key, raw = make_app(fmt='flatpak')
        raw.pop('desktop', None)
        app = manager.build_app_record(key, raw, 'x')
        # flatpak is uninstallable; use unknown format
        app['format'] = 'unknown'
        with self.assertRaises(RuntimeError):
            manager.uninstall_app(app)

    def test_reinstall_appimage_missing_file(self):
        key, raw = make_app(target='/nonexistent/x.AppImage')
        app = manager.build_app_record(key, raw, 'launch-monitor')
        with self.assertRaises(RuntimeError) as ctx:
            manager.reinstall_app(app)
        self.assertIn('no longer available', str(ctx.exception))

    def test_reinstall_flatpak_requires_file(self):
        key, raw = make_app(fmt='flatpak')
        app = manager.build_app_record(key, raw, 'launch-monitor')
        with self.assertRaises(RuntimeError):
            manager.reinstall_app(app)

    def test_update_non_flatpak_refused(self):
        key, raw = make_app(fmt='deb')
        app = manager.build_app_record(key, raw, 'x')
        with self.assertRaises(RuntimeError):
            manager.update_app(app)

    def test_update_flatpak_invokes_flatpak(self):
        key, raw = make_app(fmt='flatpak', appid='com.example.App')
        app = manager.build_app_record(key, raw, 'launch-monitor')
        with patch('manager.subprocess.run') as fake_run:
            fake_run.return_value.returncode = 0
            fake_run.return_value.stdout = ''
            message = manager.update_app(app)
        self.assertIn('completed', message.lower())
        args = fake_run.call_args[0][0]
        self.assertEqual(args[:4], ['flatpak', 'update', '--user', '--noninteractive'])


if __name__ == '__main__':
    unittest.main()
