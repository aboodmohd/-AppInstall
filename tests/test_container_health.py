"""Container health & repair tests.

Covers container_health on Engine, repair_container/repair_export in
diagnostics_core, and the manager wiring (card menu, health dialog,
repair/reexport handlers). Everything runs with stubbed podman/distrobox
and disposable XDG trees — no real container engine is required.
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location('container_backend', ROOT / 'container_backend.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
sys.modules['container_backend'] = c

spec = importlib.util.spec_from_file_location('manager', ROOT / 'manager.py')
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)

import diagnostics_core
import launch_monitor as monitor


def make_info(key='deb:example', container='debian-apps-example', kind='deb',
              name='example', exports=()):
    info = dict(container=container, kind=kind, name=name, file='/tmp/example.deb',
                sha256='abc', image='docker.io/library/debian:13')
    info['exports'] = [dict(path=p, sha256=h) for p, h in exports]
    return info


class ContainerHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_STATE_HOME': str(self.root / 'state'),
        })
        self.env.start()
        self.arch = patch.object(c.platform, 'machine', return_value='x86_64')
        self.arch.start()

    def tearDown(self):
        self.arch.stop()
        self.env.stop()
        self.tmp.cleanup()

    def engine(self):
        with patch.object(c.os, 'geteuid', return_value=1000):
            engine = c.Engine()
            self.addCleanup(engine.close)
            return engine

    def _stub_subprocess(self, found=0, responsive=0):
        """Stub subprocess.run: podman container exists -> found, distrobox enter -> responsive."""
        def run(args, **kwargs):
            import subprocess as sp
            if 'container' in args and 'exists' in args:
                return sp.CompletedProcess(args, found)
            if 'distrobox' in args and 'enter' in args:
                return sp.CompletedProcess(args, responsive)
            return sp.CompletedProcess(args, 0)
        return patch.object(c.subprocess, 'run', side_effect=run)

    def test_healthy_container(self):
        engine = self.engine()
        owned = self.root / 'data' / 'applications' / 'owned.desktop'
        owned.parent.mkdir(parents=True)
        owned.write_bytes(b'owned-content')
        import hashlib
        digest = hashlib.sha256(b'owned-content').hexdigest()
        info = make_info(exports=[(str(owned), digest)])
        engine.registry['deb:example'] = info
        with self._stub_subprocess(found=0, responsive=0):
            report = engine.container_health('deb:example')
        self.assertTrue(report['healthy'])
        self.assertTrue(report['checks']['container_exists'])
        self.assertTrue(report['checks']['container_responsive'])
        self.assertTrue(report['checks']['exports_intact'])
        self.assertEqual(report['issues'], [])

    def test_container_missing(self):
        engine = self.engine()
        info = make_info()
        engine.registry['deb:example'] = info
        with self._stub_subprocess(found=1, responsive=0):
            report = engine.container_health('deb:example')
        self.assertFalse(report['healthy'])
        self.assertFalse(report['checks']['container_exists'])
        self.assertFalse(report['checks']['container_responsive'])
        self.assertTrue(any('does not exist' in i for i in report['issues']))

    def test_container_not_responding(self):
        engine = self.engine()
        info = make_info()
        engine.registry['deb:example'] = info
        with self._stub_subprocess(found=0, responsive=1):
            report = engine.container_health('deb:example')
        self.assertFalse(report['healthy'])
        self.assertTrue(report['checks']['container_exists'])
        self.assertFalse(report['checks']['container_responsive'])
        self.assertTrue(any('not responding' in i for i in report['issues']))

    def test_export_missing(self):
        engine = self.engine()
        info = make_info(exports=[(str(self.root / 'missing.desktop'), 'hash')])
        engine.registry['deb:example'] = info
        with self._stub_subprocess(found=0, responsive=0):
            report = engine.container_health('deb:example')
        self.assertFalse(report['healthy'])
        self.assertFalse(report['checks']['exports_intact'])
        self.assertTrue(any('missing' in i for i in report['issues']))

    def test_export_modified(self):
        engine = self.engine()
        owned = self.root / 'data' / 'applications' / 'owned.desktop'
        owned.parent.mkdir(parents=True)
        owned.write_bytes(b'owned-content')
        import hashlib
        info = make_info(exports=[(str(owned), 'wrong-hash')])
        engine.registry['deb:example'] = info
        with self._stub_subprocess(found=0, responsive=0):
            report = engine.container_health('deb:example')
        self.assertFalse(report['healthy'])
        self.assertFalse(report['checks']['exports_intact'])
        self.assertTrue(any('modified' in i for i in report['issues']))

    def test_rpm_health_report(self):
        engine = self.engine()
        info = make_info(key='rpm:example', container='fedora-apps-example',
                         kind='rpm', name='example')
        engine.registry['rpm:example'] = info
        with self._stub_subprocess(found=0, responsive=0):
            report = engine.container_health('rpm:example')
        self.assertTrue(report['healthy'])


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_STATE_HOME': str(self.root / 'state'),
        })
        self.env.start()
        self.arch = patch.object(c.platform, 'machine', return_value='x86_64')
        self.arch.start()

    def tearDown(self):
        self.arch.stop()
        self.env.stop()
        self.tmp.cleanup()

    def _spec(self, key='deb:example', kind='deb'):
        return dict(key=key, container='debian-apps-example', kind=kind,
                    name='example', file='/tmp/example.deb', sha256='abc',
                    image='docker.io/library/debian:13')

    def engine(self):
        with patch.object(c.os, 'geteuid', return_value=1000):
            engine = c.Engine()
            self.addCleanup(engine.close)
            return engine

    def test_repair_container_calls_ensure(self):
        spec = self._spec()
        monitor.atomic_json(
            Path(os.environ['XDG_DATA_HOME']) / 'appinstall' / 'launchers.json',
            {'deb:example': spec})
        engine = self.engine()
        engine.ensure = Mock()
        with patch.object(c, 'Engine', return_value=engine):
            message = diagnostics_core.repair_container('deb:example')
        engine.ensure.assert_called_once_with(spec)
        self.assertIn('healthy', message)

    def test_repair_container_rejects_flatpak(self):
        spec = self._spec(key='flatpak:org.example', kind='flatpak')
        monitor.atomic_json(
            Path(os.environ['XDG_DATA_HOME']) / 'appinstall' / 'launchers.json',
            {'flatpak:org.example': spec})
        engine = self.engine()
        with patch.object(c, 'Engine', return_value=engine):
            with self.assertRaises(RuntimeError):
                diagnostics_core.repair_container('flatpak:org.example')

    def test_repair_export_calls_reexport(self):
        spec = self._spec()
        spec.update(desktop='/owned.desktop', desktop_hash='hash',
                    exports=[dict(path='/owned.desktop', sha256='hash')])
        monitor.atomic_json(
            Path(os.environ['XDG_DATA_HOME']) / 'appinstall' / 'launchers.json',
            {'deb:example': spec})
        with patch.object(c, 'Engine') as EngineCls:
            engine = EngineCls.return_value
            engine.registry = {'deb:example': spec}
            engine.export.return_value = [dict(path='/owned.desktop', sha256='hash')]
            with patch.object(diagnostics_core, 'reexport',
                              return_value='reexported') as reexport:
                message = diagnostics_core.repair_export('deb:example')
        reexport.assert_called_once_with('deb:example')
        self.assertEqual(message, 'reexported')

    def test_repair_export_rejects_flatpak(self):
        spec = self._spec(key='flatpak:org.example', kind='flatpak')
        monitor.atomic_json(
            Path(os.environ['XDG_DATA_HOME']) / 'appinstall' / 'launchers.json',
            {'flatpak:org.example': spec})
        engine = self.engine()
        with patch.object(c, 'Engine', return_value=engine):
            with self.assertRaises(RuntimeError):
                diagnostics_core.repair_export('flatpak:org.example')


class ManagerHealthTests(unittest.TestCase):
    def test_container_health_report_none_for_non_container(self):
        app = dict(key='flatpak:org.example', format='flatpak', name='Example',
                   container='', desktop='/x.desktop')
        self.assertIsNone(manager.container_health_report(app))

    def test_container_health_report_for_deb(self):
        app = dict(key='deb:example', format='deb', name='Example',
                   container='debian-apps-example')
        engine = Mock()
        engine.container_health.return_value = dict(healthy=True, checks={}, issues=[])
        engine.close = Mock()
        with patch.object(c, 'Engine', return_value=engine):
            report = manager.container_health_report(app)
        engine.container_health.assert_called_once_with('deb:example')
        engine.close.assert_called_once()
        self.assertTrue(report['healthy'])

    def test_repair_container_app_rejects_flatpak(self):
        app = dict(key='flatpak:org.example', format='flatpak', name='Example')
        with self.assertRaises(RuntimeError):
            manager.repair_container_app(app)

    def test_reexport_launcher_rejects_flatpak(self):
        app = dict(key='flatpak:org.example', format='flatpak', name='Example')
        with self.assertRaises(RuntimeError):
            manager.reexport_launcher(app)


class CardMenuTests(unittest.TestCase):
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

    def deb_app(self):
        return dict(key='deb:example', format='deb', name='Example', version='1.0',
                    container='debian-apps-example', desktop='/owned.desktop',
                    icon='', icon_name='example', manifest=None, target='/tmp/example.deb',
                    description='', status='installed', problems=[])

    def flatpak_app(self):
        return dict(key='flatpak:org.example', format='flatpak', name='Example',
                    version='1.0', container='', desktop='', icon='', icon_name='example',
                    manifest=None, target='', description='', status='installed', problems=[])

    def menu_labels(self, app):
        card = manager.AppCard(app)
        labels = [action.text() for action in card._build_menu().actions()]
        card.deleteLater()
        return labels

    def test_deb_menu_has_container_actions(self):
        labels = self.menu_labels(self.deb_app())
        self.assertIn('Container Health…', labels)
        self.assertIn('Repair Container', labels)
        self.assertIn('Re-export Launcher', labels)

    def test_flatpak_menu_has_no_container_actions(self):
        labels = self.menu_labels(self.flatpak_app())
        self.assertNotIn('Container Health…', labels)
        self.assertNotIn('Repair Container', labels)
        self.assertNotIn('Re-export Launcher', labels)


if __name__ == '__main__':
    unittest.main()
