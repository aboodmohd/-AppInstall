import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.bin = self.home / 'bin'
        self.bin.mkdir()
        for tool in ('kdialog', 'zenity', 'notify-send'):
            stub = self.bin / tool
            stub.write_text('#!/bin/sh\nexit 1\n')
            stub.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), XDG_DATA_HOME=str(self.home / 'data'), XDG_CONFIG_HOME=str(self.home / 'config'), PATH=str(self.bin) + ':' + os.environ['PATH'])
    def tearDown(self):
        self.tmp.cleanup()
    def run_app(self, *args):
        return subprocess.run([str(ROOT / 'appinstall'), *map(str,args)], env=self.env, capture_output=True, text=True)
    def test_invalid_appimage(self):
        f = self.home / 'fake.AppImage'
        f.write_text('not an executable')
        self.assertNotEqual(self.run_app('--yes', f).returncode, 0)
        self.assertTrue(f.exists())
        self.assertFalse((self.home / 'Applications').exists())
    def test_cancel_flatpak(self):
        python = self.bin / 'python3'
        python.write_text('#!/bin/sh\nexit 1\n')
        python.chmod(0o755)
        dialog = self.bin / 'kdialog'
        dialog.write_text('#!/bin/sh\nexit 1\n')
        dialog.chmod(0o755)
        f = self.home / 'app.flatpakref'
        f.write_text('[Flatpak Ref]\nName=org.example.App\nUrl=https://example.org/repo\n')
        self.assertEqual(self.run_app(f).returncode, 0)
        self.assertFalse((self.home / 'Applications').exists())
    def test_flatpak_failure_propagates(self):
        backend = self.bin / 'flatpak'
        backend.write_text('#!/bin/sh\ncase "$1" in install) echo download-failed >&2; exit 1;; esac\n')
        backend.chmod(0o755)
        f = self.home / 'app.flatpak'
        f.touch()
        result = self.run_app('--yes',f)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('download-failed',result.stderr)
    def test_already_installed_reference(self):
        backend = self.bin / 'flatpak'
        backend.write_text('#!/bin/sh\ncase "$1" in --default-arch) echo x86_64;; info) exit 0;; install) echo unexpected-install >&2; exit 12;; esac\n')
        backend.chmod(0o755)
        f = self.home / 'app.flatpakref'
        f.write_text('[Flatpak Ref]\nName=com.stremio.Stremio\nBranch=stable\n')
        result = self.run_app('--yes', f)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('unexpected-install', result.stderr)

    def test_registration_restore(self):
        config = self.home / 'config'
        config.mkdir()
        defaults = config / 'mimeapps.list'
        defaults.write_text('[Default Applications]\napplication/vnd.flatpak=previous.desktop;\ntext/plain=editor.desktop;\n')
        subprocess.run(['python3',str(ROOT / 'integration.py')],env=self.env,check=True,capture_output=True)
        self.assertIn('application/vnd.flatpak=appinstall.desktop;',defaults.read_text())
        subprocess.run([str(self.home / '.local/bin/appinstall-uninstall')],env=self.env,check=True,capture_output=True)
        self.assertIn('application/vnd.flatpak=previous.desktop;',defaults.read_text())
        self.assertIn('text/plain=editor.desktop;',defaults.read_text())

    def test_appimage_review_action_registered_and_removed(self):
        menu = self.home / 'data/kio/servicemenus/appinstall-appimage-review.desktop'
        subprocess.run(['python3', str(ROOT / 'integration.py')],
                       env=self.env, check=True, capture_output=True)
        self.assertTrue(menu.is_file())
        self.assertTrue(menu.stat().st_mode & 0o100)
        text = menu.read_text()
        self.assertIn('MimeType=application/vnd.appimage;', text)
        self.assertIn('Actions=ReviewWithAppInstall;', text)
        self.assertIn('X-KDE-Priority=TopLevel', text)
        self.assertIn('X-KDE-RequiredNumberOfUrls=1', text)
        self.assertIn('X-AppInstall-Managed=true', text)
        self.assertIn('Exec="'+str(self.home / '.local/bin/appinstall')+'" %f', text)
        self.assertNotIn('Exec=./', text)
        subprocess.run([str(self.home / '.local/bin/appinstall-uninstall')],
                       env=self.env, check=True, capture_output=True)
        self.assertFalse(menu.exists())

    def test_registration_rejects_unrelated_service_menu(self):
        menu = self.home / 'data/kio/servicemenus/appinstall-appimage-review.desktop'
        menu.parent.mkdir(parents=True)
        data = '[Desktop Entry]\\nType=Service\\nName=Unrelated\\n'
        menu.write_text(data)
        result = subprocess.run(['python3', str(ROOT / 'integration.py')],
                                env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(menu.read_text(), data)
        self.assertFalse((self.home / '.local/bin/appinstall').exists())

    def test_uninstall_preserves_user_modified_unmanaged_menu(self):
        menu = self.home / 'data/kio/servicemenus/appinstall-appimage-review.desktop'
        subprocess.run(['python3', str(ROOT / 'integration.py')],
                       env=self.env, check=True, capture_output=True)
        custom = '[Desktop Entry]\\nName=Replaced by user\\n'
        menu.write_text(custom)
        subprocess.run([str(self.home / '.local/bin/appinstall-uninstall')],
                       env=self.env, check=True, capture_output=True)
        self.assertEqual(menu.read_text(), custom)

    def test_desktop_entry_fields(self):
        """Desktop entry has correct GenericName, Comment, and Exec."""
        desktop = ROOT / 'appinstall.desktop'
        text = desktop.read_text()
        self.assertIn('GenericName=Application Installer', text)
        self.assertIn('Comment=Install AppImage, Flatpak, DEB, and RPM applications', text)
        self.assertIn('Exec=appinstall %F', text)

    def test_integration_copies_manager_py(self):
        """integration.py includes manager.py in its module copy list."""
        integration = ROOT / 'integration.py'
        text = integration.read_text()
        self.assertIn("'manager.py'", text)

    def test_installed_appinstall_supports_manage(self):
        """The deployed appinstall executable supports --manage."""
        candidates = (
            Path.home() / '.local/bin' / 'appinstall',
            Path('/usr/bin/appinstall'),
        )
        installed = next((p for p in candidates if p.is_file()), None)
        if installed is None:
            self.skipTest('Installed appinstall not found')
        text = installed.read_text()
        self.assertIn('--manage', text)
        self.assertIn('manager.py', text)

    def test_integration_copies_result_ui(self):
        """integration.py includes result_ui.py in its module copy list."""
        integration = ROOT / 'integration.py'
        text = integration.read_text()
        self.assertIn("'result_ui.py'", text)

    def test_integration_copies_ui_style(self):
        """integration.py includes ui_style.py in its module copy list."""
        integration = ROOT / 'integration.py'
        text = integration.read_text()
        self.assertIn("'ui_style.py'", text)

    def test_deployed_modules_importable(self):
        """All deployed AppInstall Python modules can be imported."""
        state = Path.home() / '.local/share' / 'appinstall'
        if not state.exists():
            self.skipTest('Installed appinstall state directory not found')
        required = ['ui_style', 'result_ui', 'container_ui', 'confirm',
                    'package_meta', 'appimage_backend', 'native_backend',
                    'container_backend', 'launch_monitor', 'runtime_probe',
                    'diagnostics_core', 'diagnostics_ui', 'manager']
        import importlib.util
        for modname in required:
            modfile = state / f'{modname}.py'
            self.assertTrue(modfile.exists(), f'{modname}.py missing from deployed state')
            spec = importlib.util.spec_from_file_location(modname, modfile)
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                self.fail(f'Failed to import {modname}: {e}')

if __name__ == '__main__':
    unittest.main()
