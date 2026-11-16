"""Uninstall cleanup tests.

Covers UninstallDialog (all checkboxes unchecked by default, exact paths
shown) and uninstall_app with cleanup paths. Verifies that unchecked paths,
symlinks, and shared data remain untouched after uninstall.
"""
import importlib.util
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location('manager', ROOT / 'manager.py')
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)

import diagnostics_core


def make_app(key='appimage:example', fmt='appimage', **overrides):
    raw = dict(format=fmt, name='Example App', version='1.0',
               desktop='/home/user/.local/share/applications/example.desktop',
               icon='', icon_name='example', container=None,
               manifest=None, target='/home/user/Applications/Example.AppImage',
               description='An example application.', status='installed',
               problems=[], exports=[], icons=[])
    raw.update(overrides)
    return key, raw


class UninstallDialogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_STATE_HOME': str(self.root / 'state'),
        })
        self.env.start()
        from qt_compat import QtWidgets
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def app_record(self):
        return dict(key='appimage:example', format='appimage',
                    name='Example', desktop='/x.desktop', exports=[],
                    icons=[], target='/tmp/Example.AppImage',
                    manifest='/tmp/Example.AppImage.manifest')

    def create_history(self):
        key='appimage:example'
        folder=self.root / 'state' / 'appinstall' / 'launches' / hashlib.sha256(
            key.encode()).hexdigest()[:20]
        folder.mkdir(parents=True)
        (folder/'attempt.json').write_text('{}')
        return folder

    def test_app_only_default_preserves_history(self):
        app=self.app_record()
        path=self.create_history()
        dialog=manager.UninstallDialog(app, manager.uninstall_cleanup_items(app))
        self.assertTrue(dialog.app_only.isChecked())
        self.assertEqual(dialog.selected_paths(), set())
        self.assertTrue(str(path) in next(iter(dialog.checks)))
        self.assertFalse(next(iter(dialog.checks.values())).isEnabled())

    def test_remove_with_managed_folders_requires_explicit_selection(self):
        app=self.app_record()
        path=self.create_history()
        dialog=manager.UninstallDialog(app, manager.uninstall_cleanup_items(app))
        dialog.with_managed_data.setChecked(True)
        self.assertEqual(dialog.selected_paths(), {str(path)})
        dialog.app_only.setChecked(True)
        self.assertEqual(dialog.selected_paths(), set())

    def test_settings_default_prefills_without_skipping_confirmation(self):
        import settings
        app=self.app_record()
        path=self.create_history()
        settings.update('uninstall_mode', 'with_managed_data')
        dialog=manager.UninstallDialog(app, manager.uninstall_cleanup_items(app))
        self.assertTrue(dialog.with_managed_data.isChecked())
        self.assertEqual(dialog.selected_paths(), {str(path)})

    def test_no_managed_folders(self):
        app=self.app_record()
        dialog=manager.UninstallDialog(app, manager.uninstall_cleanup_items(app))
        self.assertEqual(dialog.checks, {})
        self.assertEqual(dialog.selected_paths(), set())


class CleanupItemsTests(unittest.TestCase):
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

    def test_shared_container_and_personal_files_are_never_offered(self):
        app = dict(key='deb:example', format='deb', name='Example',
                   container='debian-apps',
                   exports=[dict(path='/owned.desktop', sha256='hash')],
                   icons=[dict(path='/owned.icon', sha256='hash')],
                   target='/tmp/example.deb', manifest=None,
                   desktop='/usr/share/applications/example.desktop')
        self.assertEqual(manager.uninstall_cleanup_items(app), [])

    def test_only_exact_managed_history_is_offered(self):
        key='appimage:example'
        folder=self.root / 'state' / 'appinstall' / 'launches' / hashlib.sha256(
            key.encode()).hexdigest()[:20]
        folder.mkdir(parents=True)
        app=dict(key=key, format='appimage', target='/tmp/SomeFile.AppImage',
                 manifest='/tmp/file.manifest', exports=[], icons=[])
        self.assertEqual(manager.uninstall_cleanup_items(app),
                         [('AppInstall launch history', str(folder))])

    def test_symlinked_history_is_never_offered(self):
        key='appimage:example'
        folder=self.root / 'state' / 'appinstall' / 'launches' / hashlib.sha256(
            key.encode()).hexdigest()[:20]
        folder.parent.mkdir(parents=True)
        external=self.root / 'personal'
        external.mkdir()
        folder.symlink_to(external, target_is_directory=True)
        self.assertEqual(manager.uninstall_cleanup_items({'key': key}), [])


class UninstallSafetyTests(unittest.TestCase):
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

    def _make_spec(self, key='deb:example', kind='deb'):
        return dict(key=key, container='debian-apps-example', kind=kind,
                    name='example', file='/tmp/example.deb', sha256='abc',
                    image='docker.io/library/debian:13',
                    exports=[dict(path='/owned.desktop', sha256='hash-owned')],
                    icons=[dict(path='/owned.icon', sha256='hash-icon')])

    def _write(self, name, content=b'data'):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        return p

    def test_unchecked_launch_history_remains(self):
        key = 'deb:example'
        spec = self._make_spec(key)
        history_dir = self.root / 'state' / 'appinstall' / 'launches' / 'abcd1234'
        history_dir.mkdir(parents=True)
        (history_dir / 'attempt.json').write_text('{}')
        owned = self._write('owned.desktop', b'data')
        spec['exports'] = [dict(path=str(owned), sha256=hashlib.sha256(b'data').hexdigest())]
        owned_icon = self._write('owned.icon', b'data')
        spec['icons'] = [dict(path=str(owned_icon), sha256=hashlib.sha256(b'data').hexdigest())]
        import launch_monitor as monitor
        monitor.atomic_json(
            Path(os.environ['XDG_DATA_HOME']) / 'appinstall' / 'launchers.json',
            {key: spec})

        with patch.object(manager.core, 'uninstall', return_value='removed'):
            manager.uninstall_app(manager.build_app_record(
                key, spec, 'x'), cleanup=set())

        # Launch history dir still exists (unchecked)
        self.assertTrue((history_dir / 'attempt.json').exists())

    def test_rejects_untrusted_cleanup_before_uninstall(self):
        key = 'deb:example'
        spec = self._make_spec(key)
        personal = self._write('personal/important.txt', b'never remove')
        import launch_monitor as monitor
        monitor.atomic_json(
            Path(os.environ['XDG_DATA_HOME'])/'appinstall'/'launchers.json',
            {key: spec})
        with patch.object(manager.core, 'uninstall') as uninstall:
            with self.assertRaises(ValueError):
                manager.uninstall_app(
                    manager.build_app_record(key, spec, 'x'),
                    cleanup={str(personal)})
        uninstall.assert_not_called()
        self.assertTrue(personal.exists())

    def test_success_unregisters_app_and_clears_favorite(self):
        key='appimage:example'
        _, raw=make_app(key=key)
        import launch_monitor as monitor
        import settings
        monitor.update_registry(key, raw)
        settings.update('favorites', [key])
        with patch.object(manager.core, 'uninstall',
                          side_effect=lambda selected_key, cleanup=():
                              monitor.update_registry(selected_key, None)):
            result=manager.uninstall_app(manager.build_app_record(key, raw, 'x'))
        self.assertIn('removed', result)
        self.assertFalse(any(item['key'] == key for item in manager.load_inventory()))
        self.assertNotIn(key, settings.read()['favorites'])

    def test_failed_uninstall_keeps_app_registry_and_favorite(self):
        key='appimage:example'
        _, raw=make_app(key=key)
        import launch_monitor as monitor
        import settings
        monitor.update_registry(key, raw)
        settings.update('favorites', [key])
        with patch.object(manager.core, 'uninstall', side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):
                manager.uninstall_app(manager.build_app_record(key, raw, 'x'))
        self.assertIn(key, monitor.registry())
        self.assertIn(key, settings.read()['favorites'])


class EngineUninstallCleanupTests(unittest.TestCase):
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

    def make_engine(self):
        import container_backend as c
        key='deb:example'
        engine=c.Engine.__new__(c.Engine)
        engine.root=self.root/'containers'
        engine.file=engine.root/'registry.json'
        engine.root.mkdir(parents=True, exist_ok=True)
        engine.registry={key: dict(
            container='debian-apps', kind='deb', name='example',
            file='/tmp/example.deb', sha256='abc',
            image='docker.io/library/debian:13',
            exports=[], icons=[])}
        return engine

    def test_selected_app_history_removed_but_shared_container_retained(self):
        import container_backend as c
        key='deb:example'
        engine=self.make_engine()
        history=self.root/'state'/'appinstall'/'launches'/hashlib.sha256(
            key.encode()).hexdigest()[:20]
        history.mkdir(parents=True)
        (history/'attempt.json').write_text('{}')
        with patch.object(c, 'command') as run, \
             patch.object(c.os, 'geteuid', return_value=1000):
            engine.uninstall(key, cleanup={str(history)})
        self.assertFalse(history.exists())
        self.assertNotIn(key, engine.registry)
        self.assertFalse(any('distrobox' in str(call)
                             for call in run.call_args_list))

    def test_arbitrary_folder_refused_before_uninstall(self):
        import container_backend as c
        key='deb:example'
        engine=self.make_engine()
        personal=self.root/'my-important-files'
        personal.mkdir()
        with patch.object(c, 'command') as command:
            with self.assertRaises(ValueError):
                engine.uninstall(key, cleanup={str(personal)})
        command.assert_not_called()
        self.assertTrue(personal.exists())
        self.assertIn(key, engine.registry)


if __name__ == '__main__':
    unittest.main()
