"""Tests for the WebView preview: the loopback API, its writes and the
shipped frontend assets.

No external network and no windowing system: the API is exercised over
loopback, the inventory is faked, and the WebView itself is covered by
the packaged smoke job.
"""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import manager_web  # noqa: E402  (path first)
import settings  # noqa: E402


class PreviewBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.environment = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_STATE_HOME': str(self.root / 'state'),
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.temp.cleanup)

        self.inventory = [
            {
                'key': 'appimage:Alpha',
                'name': 'Alpha',
                'format': 'appimage',
                'version': '1.2.3',
                'status': 'installed',
                'container': '',
                'problems': [],
                'icon': '',
                'description': 'The first one',
                'last_launch': {'started': '2026-01-01T10:00:00'},
            },
            {
                'key': 'flatpak:Beta',
                'name': 'Beta',
                'format': 'flatpak',
                'version': '',
                'status': 'missing',
                'container': '',
                'problems': ['application file missing'],
                'icon': '',
                'description': '',
                'last_launch': {},
            },
        ]
        self.state = manager_web.PreviewState()
        with patch.object(manager_web.manager, 'load_inventory',
                          return_value=self.inventory):
            self.state.load()

        self.server = manager_web.PreviewServer(self.state, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)

    def request(self, path, method='GET', payload=None, token=None):
        headers = {}
        if token is not None:
            headers['X-AppInstall-Token'] = token
        body = None
        if payload is not None:
            body = json.dumps(payload).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.server.origin + path,
                                         data=body, headers=headers,
                                         method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            body = error.read()
            error.close()
            return error.code, body


class StateTests(PreviewBase):
    def test_snapshot_carries_the_inventory_with_display_values(self):
        snapshot = self.state.snapshot()
        self.assertTrue(snapshot['ready'])
        self.assertEqual(len(snapshot['apps']), 2)
        alpha = snapshot['apps'][0]
        self.assertEqual(alpha['name'], 'Alpha')
        self.assertEqual(alpha['formatLabel'], 'AppImage')
        self.assertEqual(alpha['statusLabel'], 'Installed')
        self.assertEqual(alpha['statusTone'], 'success')
        self.assertEqual(alpha['initial'], 'A')
        self.assertFalse(alpha['favorite'])
        self.assertEqual(snapshot['counts']['appimage'], 1)
        self.assertEqual(snapshot['counts']['flatpak'], 1)

    def test_problems_are_joined_for_display(self):
        beta = self.state.snapshot()['apps'][1]
        self.assertEqual(beta['problems'], 'application file missing')
        self.assertEqual(beta['statusLabel'], 'Files missing')
        self.assertEqual(beta['statusTone'], 'danger')

    def test_favorites_are_written_through_to_settings(self):
        favorites = self.state.set_favorite('appimage:Alpha', True)
        self.assertEqual(favorites, ['appimage:Alpha'])
        self.assertEqual(settings.read()['favorites'], ['appimage:Alpha'])
        self.assertTrue(self.state.snapshot()['apps'][0]['favorite'])

        self.state.set_favorite('appimage:Alpha', False)
        self.assertEqual(settings.read()['favorites'], [])

    def test_the_theme_is_written_through_to_settings(self):
        self.assertEqual(self.state.set_theme('dark'), 'dark')
        self.assertEqual(settings.read()['theme'], 'dark')
        self.assertEqual(self.state.snapshot()['theme'], 'dark')

    def test_an_unknown_theme_is_rejected(self):
        with self.assertRaises(ValueError):
            self.state.set_theme('neon')

    def test_a_broken_inventory_reports_the_error(self):
        state = manager_web.PreviewState()
        with patch.object(manager_web.manager, 'load_inventory',
                          side_effect=OSError('registry unreadable')):
            state.load()
        self.assertTrue(state.snapshot()['ready'])
        self.assertIn('registry unreadable', state.snapshot()['error'])


class ApiTests(PreviewBase):
    def test_state_requires_the_session_token(self):
        status, _ = self.request('/api/state')
        self.assertEqual(status, 403)
        status, _ = self.request('/api/state', token='wrong')
        self.assertEqual(status, 403)

    def test_state_is_served_with_the_token(self):
        status, body = self.request('/api/state', token=self.server.token)
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(len(payload['apps']), 2)

    def test_a_favorite_is_stored_and_confirmed(self):
        status, body = self.request(
            '/api/favorite', method='POST', token=self.server.token,
            payload={'key': 'flatpak:Beta', 'favorite': True})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['favorites'], ['flatpak:Beta'])
        self.assertEqual(settings.read()['favorites'], ['flatpak:Beta'])

    def test_a_favorite_without_a_key_is_rejected(self):
        status, _ = self.request(
            '/api/favorite', method='POST', token=self.server.token,
            payload={'favorite': True})
        self.assertEqual(status, 400)

    def test_the_theme_is_stored_and_confirmed(self):
        status, body = self.request(
            '/api/theme', method='POST', token=self.server.token,
            payload={'theme': 'light'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['theme'], 'light')
        self.assertEqual(settings.read()['theme'], 'light')

    def test_a_foreign_origin_is_refused(self):
        request = urllib.request.Request(
            self.server.origin + '/api/theme',
            data=json.dumps({'theme': 'dark'}).encode('utf-8'),
            headers={'X-AppInstall-Token': self.server.token,
                     'Content-Type': 'application/json',
                     'Origin': 'https://example.invalid'},
            method='POST')
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                self.fail('expected a refusal, got ' + str(response.status))
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 403)

    def test_the_frontend_is_served(self):
        status, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'<title>My Applications', body)
        status, body = self.request('/app.css')
        self.assertEqual(status, 200)
        self.assertIn(b'--accent', body)

    def test_an_unknown_script_is_not_served(self):
        status, _ = self.request('/js/../manager_web.py')
        self.assertEqual(status, 404)

    def test_an_icon_without_a_record_is_not_served(self):
        status, _ = self.request('/icon/appimage%3AAlpha',
                                 token=self.server.token)
        self.assertEqual(status, 404)

    def test_an_icon_file_is_served_for_a_record(self):
        with tempfile.TemporaryDirectory() as out:
            icon = Path(out) / 'icon.png'
            icon.write_bytes(b'\x89PNG\r\n\x1a\n')
            self.inventory[0]['icon'] = str(icon)
            state = manager_web.PreviewState()
            with patch.object(manager_web.manager, 'load_inventory',
                              return_value=self.inventory):
                state.load()
            snapshot = state.snapshot()
            self.assertEqual(snapshot['apps'][0]['iconUrl'],
                             '/icon/appimage%3AAlpha')
            self.assertEqual(snapshot['apps'][1]['iconUrl'], '')

            server = manager_web.PreviewServer(state, port=0)
            thread = threading.Thread(target=server.serve_forever,
                                       daemon=True)
            thread.start()
            self.addCleanup(server.shutdown)
            self.addCleanup(server.server_close)
            request = urllib.request.Request(
                server.origin + snapshot['apps'][0]['iconUrl'],
                headers={'X-AppInstall-Token': server.token})
            with urllib.request.urlopen(request, timeout=10) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b'\x89PNG\r\n\x1a\n')


class AssetTests(unittest.TestCase):
    """The compiled frontend and the source it comes from."""

    def test_the_compiled_frontend_is_committed(self):
        for name in ('main.js', 'render.js', 'view-model.js', 'api.js'):
            path = ROOT / 'webpreview' / 'dist' / name
            self.assertTrue(path.is_file(), name + ' is missing')
            self.assertGreater(path.stat().st_size, 0, name + ' is empty')

    def test_the_sources_and_the_build_are_both_present(self):
        self.assertTrue((ROOT / 'webpreview' / 'src' / 'main.ts').is_file())
        self.assertTrue((ROOT / 'webpreview' / 'tsconfig.json').is_file())
        self.assertTrue((ROOT / 'webpreview' / 'package.json').is_file())

    def test_the_checkout_frontend_is_found(self):
        index, stylesheet, scripts = manager_web.frontend_paths()
        self.assertEqual(index, ROOT / 'webpreview' / 'assets' / 'index.html')
        self.assertEqual(stylesheet, ROOT / 'webpreview' / 'assets' / 'app.css')
        self.assertEqual(scripts, ROOT / 'webpreview' / 'dist')
        self.assertTrue((scripts / 'main.js').is_file())

    def test_the_packaged_frontend_is_found(self):
        """A native package ships one flat directory, not the sources."""
        with tempfile.TemporaryDirectory() as out:
            root = Path(out) / 'webpreview'
            (root / 'js').mkdir(parents=True)
            (root / 'index.html').write_text('<html></html>')
            (root / 'app.css').write_text('body {}')
            (root / 'js' / 'main.js').write_text('// main')
            with patch.object(manager_web, 'PREVIEW_DIR',
                              Path(out) / 'checkout'), \
                 patch.object(manager_web, 'PACKAGED_ROOT', root):
                index, stylesheet, scripts = manager_web.frontend_paths()
            self.assertEqual(index, root / 'index.html')
            self.assertEqual(stylesheet, root / 'app.css')
            self.assertEqual(scripts, root / 'js')

    def test_the_compiled_output_matches_the_sources(self):
        """A stale dist/ would ship an old preview."""
        compiler = ROOT / 'webpreview' / 'node_modules' / '.bin' / 'tsc'
        if not compiler.exists():
            self.skipTest('typescript is not installed in this checkout')
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as out:
            result = subprocess.run(
                [str(compiler), '--project',
                 str(ROOT / 'webpreview' / 'tsconfig.json'),
                 '--outDir', out, '--noEmitOnError', 'false'],
                capture_output=True, text=True, timeout=300)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ('main.js', 'render.js', 'view-model.js', 'api.js',
                         'types.js'):
                fresh = Path(out) / name
                self.assertTrue(fresh.is_file(), name + ' was not compiled')
                self.assertEqual(
                    fresh.read_text(),
                    (ROOT / 'webpreview' / 'dist' / name).read_text(),
                    name + ' is stale')


if __name__ == '__main__':
    unittest.main()
