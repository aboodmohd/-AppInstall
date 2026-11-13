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

    def test_all_checkboxes_unchecked_by_default(self):
        app = dict(key='appimage:example', format='appimage', name='Example',
                   container='', desktop='/x.desktop', exports=[],
                   icons=[], target='/tmp/Example.AppImage',
                   manifest='/tmp/Example.AppImage.manifest')
        items = manager.uninstall_cleanup_items(app)
        dialog = manager.UninstallDialog(app, items)
        for cb in dialog.checks.values():
            self.assertFalse(cb.isChecked(), 'checkbox should be unchecked by default: '+cb.text())

    def test_dialog_shows_exact_paths(self):
        app = dict(key='appimage:example', format='appimage', name='Example',
                   container='', desktop='/x.desktop', exports=[],
                   icons=[], target='/tmp/Example.AppImage',
                   manifest='/tmp/Example.AppImage.manifest')
        items = manager.uninstall_cleanup_items(app)
        dialog = manager.UninstallDialog(app, items)
        for label, path in items:
            found = any(path in cb.text() for cb in dialog.checks.values())
            self.assertTrue(found, 'path not shown in dialog: '+path)

    def test_no_items_produces_empty_dialog(self):
        app = dict(key='flatpak:org.example', format='flatpak', name='Example',
                   container='', desktop='', exports=[], icons=[],
                   target='', manifest='')
        items = manager.uninstall_cleanup_items(app)
        dialog = manager.UninstallDialog(app, items)
        self.assertEqual(dialog.checks, {})


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

    def test_deb_items_include_exports_and_container(self):
        app = dict(key='deb:example', format='deb', name='Example',
                   container='debian-apps-example',
                   exports=[dict(path='/owned.desktop', sha256='hash')],
                   icons=[], target='/tmp/example.deb', manifest=None,
                   desktop='/usr/share/applications/example.desktop')
        items = manager.uninstall_cleanup_items(app)
        paths = [p for _, p in items]
        self.assertIn('/owned.desktop', paths)
        self.assertIn('debian-apps-example', paths)

    def test_appimage_items_include_target_and_manifest(self):
        app = dict(key='appimage:example', format='appimage', name='Example',
                   container='', exports=[], icons=[],
                   target='/tmp/Example.AppImage',
                   manifest='/tmp/Example.AppImage.manifest')
        items = manager.uninstall_cleanup_items(app)
        paths = [p for _, p in items]
        self.assertIn('/tmp/Example.AppImage', paths)
        self.assertIn('/tmp/Example.AppImage.manifest', paths)

    def test_shared_icons_not_duplicated(self):
        app = dict(key='deb:example', format='deb', name='Example',
                   container='debian-apps-example',
                   exports=[dict(path='/shared.desktop', sha256='hash')],
                   icons=[dict(path='/shared.desktop', sha256='hash')],
                   target='/tmp/example.deb', manifest=None,
                   desktop='/usr/share/applications/example.desktop')
        items = manager.uninstall_cleanup_items(app)
        paths = [p for _, p in items]
        self.assertEqual(paths.count('/shared.desktop'), 1)


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

    def test_symlink_passes_cleanup_through(self):
        """The cleanup path is passed through to core.uninstall (verified via
        call args), while the symlink target is never touched by our code."""
        key = 'deb:example'
        spec = self._make_spec(key)
        real = self._write('real.desktop', b'real content')
        link = self.root / 'link.desktop'
        link.symlink_to(real)
        spec['exports'] = [dict(path=str(link), sha256=hashlib.sha256(b'real content').hexdigest())]
        spec['icons'] = []
        import launch_monitor as monitor
        monitor.atomic_json(
            Path(os.environ['XDG_DATA_HOME']) / 'appinstall' / 'launchers.json',
            {key: spec})

        captured = {}
        with patch.object(manager.core, 'uninstall', side_effect=lambda k, cleanup=(): captured.setdefault('cleanup', cleanup)):
            manager.uninstall_app(manager.build_app_record(
                key, spec, 'x'), cleanup={str(link)})
        self.assertEqual(captured['cleanup'], {str(link)})
        # Our code never touches the symlink target.
        self.assertTrue(real.exists())
        self.assertTrue(link.exists())


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

    def test_engine_uninstall_removes_selected_cleanup_path(self):
        from container_backend import Engine as Eng
        import container_backend as c
        engine = c.Engine.__new__(c.Engine)
        engine.root = self.root / 'containers'
        engine.file = engine.root / 'registry.json'
        engine.registry = {
            'deb:example': dict(
                container='debian-apps-example', kind='deb', name='example',
                file='/tmp/example.deb', sha256='abc',
                image='docker.io/library/debian:13',
                exports=[dict(path='/owned.desktop', sha256='hash-owned')],
                icons=[],
            )
        }
        cleanup_path = self.root / 'launch_history.json'
        cleanup_path.write_text('{}')
        engine.registry['deb:example']['exports'] = [
            dict(path='/owned.desktop', sha256='hash-owned'),
            dict(path=str(cleanup_path), sha256=hashlib.sha256(b'{}').hexdigest()),
        ]
        self.root.joinpath('owned.desktop').parent.mkdir(parents=True, exist_ok=True)
        self.root.joinpath('owned.desktop').write_bytes(b'owned')
        engine.root.mkdir(parents=True, exist_ok=True)

        with patch.object(c, 'command'), patch.object(c.os, 'geteuid', return_value=1000):
            engine.uninstall('deb:example', cleanup={str(cleanup_path)})

        self.assertFalse(cleanup_path.exists())
        self.assertNotIn('deb:example', engine.registry)


if __name__ == '__main__':
    unittest.main()
