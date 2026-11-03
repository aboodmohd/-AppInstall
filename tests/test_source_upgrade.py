"""Isolated real-source installation/upgrade smoke tests.

These tests use a disposable HOME/XDG tree. No system package or live user
installation is touched.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "integration.py"
MIME = "application/vnd.flatpak"


class SourceUpgradeSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="appinstall-upgrade-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home with spaces"
        self.home.mkdir()
        self.config = self.home / "config"
        self.config.mkdir()
        self.data = self.home / "data"
        self.state = self.data / "appinstall"
        self.defaults_file = self.config / "mimeapps.list"
        self.defaults_file.write_text(
            "[Default Applications]\n"
            "application/vnd.flatpak=original.desktop;\n"
            "text/plain=editor.desktop;\n"
        )
        self.env = dict(os.environ)
        self.env.update({
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.config),
            "XDG_DATA_HOME": str(self.data),
            "XDG_STATE_HOME": str(self.home / "state"),
            "QT_QPA_PLATFORM": "offscreen",
        })

    def register(self, *args):
        result = subprocess.run(
            [sys.executable, str(REGISTER), *args],
            cwd=ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_clean_registration_and_rollback_keep_app_data(self):
        # Fresh XDG/HOME tree with no prior AppInstall registration.
        self.assertFalse(self.state.exists())
        self.register()

        installed = self.home / ".local/bin/appinstall"
        self.assertTrue(installed.is_file())
        self.assertEqual(installed.read_bytes(), (ROOT / "appinstall").read_bytes())
        self.assertTrue((self.data / "applications/appinstall.desktop").exists())
        self.assertTrue((self.state / "manager.py").exists())
        self.assertTrue((self.state / "launch_monitor.py").exists())
        saved = json.loads((self.state / "associations.json").read_text())
        self.assertEqual(saved[MIME], "original.desktop;")
        self.assertIn(MIME + "=appinstall.desktop;", self.defaults_file.read_text())

        # Desktop registration removal is not application-data removal.
        registry = self.state / "containers/registry.json"
        registry.parent.mkdir(parents=True)
        data = {"rpm:keep": {"name": "Keep", "status": "installed"}}
        registry.write_text(json.dumps(data))
        self.register("--uninstall")

        self.assertFalse(installed.exists())
        self.assertFalse((self.data / "applications/appinstall.desktop").exists())
        self.assertIn(MIME + "=original.desktop;", self.defaults_file.read_text())
        self.assertIn("text/plain=editor.desktop;", self.defaults_file.read_text())
        self.assertEqual(json.loads(registry.read_text()), data)

    def test_incomplete_checkout_cannot_overwrite_existing_source_install(self):
        # Incomplete clone must fail before touching the existing deployment.
        self.register()
        old_module = self.state / "manager.py"
        old_module.write_text("# working deployed manager\n")
        old_associations = (self.state / "associations.json").read_bytes()
        old_defaults = self.defaults_file.read_bytes()
        old_launcher = (self.data / "applications/appinstall.desktop").read_bytes()
        old_executable = (self.home / ".local/bin/appinstall").read_bytes()

        incomplete = Path(self.temp.name) / "incomplete source"
        incomplete.mkdir()
        broken = incomplete / "integration.py"
        broken.write_bytes(REGISTER.read_bytes())
        result = subprocess.run(
            [sys.executable, str(broken)],
            cwd=incomplete,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Incomplete AppInstall source directory", result.stderr)
        self.assertIn("No user files were changed", result.stderr)
        self.assertEqual(old_module.read_text(), "# working deployed manager\n")
        self.assertEqual((self.state / "associations.json").read_bytes(), old_associations)
        self.assertEqual(self.defaults_file.read_bytes(), old_defaults)
        self.assertEqual((self.data / "applications/appinstall.desktop").read_bytes(), old_launcher)
        self.assertEqual((self.home / ".local/bin/appinstall").read_bytes(), old_executable)

    def test_source_upgrade_keeps_records_original_association_and_modules(self):
        registry = self.state / "containers" / "registry.json"
        registry.parent.mkdir(parents=True)
        original = {"deb:untouched": {"version": "1.0", "source": "/tmp/not-present.deb"}}
        registry.write_text(json.dumps(original))
        self.register()
        saved = json.loads((self.state / "associations.json").read_text())
        self.assertEqual(saved[MIME], "original.desktop;")
        self.assertIn(MIME + "=appinstall.desktop;", self.defaults_file.read_text())
        self.assertEqual(json.loads(registry.read_text()), original)

        # Emulate an old deployed module and upgrade by rerunning registration.
        deployed = self.state / "manager.py"
        deployed.write_text("# previous version\n")
        self.register()
        self.assertEqual(deployed.read_bytes(), (ROOT / "manager.py").read_bytes())
        self.assertEqual(json.loads((self.state / "associations.json").read_text()), saved)
        self.assertEqual(json.loads(registry.read_text()), original)
        self.assertIn("text/plain=editor.desktop;", self.defaults_file.read_text())

        self.register("--uninstall")
        self.assertIn(MIME + "=original.desktop;", self.defaults_file.read_text())
        self.assertIn("text/plain=editor.desktop;", self.defaults_file.read_text())
        self.assertEqual(json.loads(registry.read_text()), original)


    def test_stale_appimage_launcher_remains_intact_across_source_upgrade(self):
        apps = self.data / 'applications'
        apps.mkdir(parents=True, exist_ok=True)
        stale = apps / 'legacy.desktop'
        manifest = self.state / 'old-version-no-longer-here.json'
        original = (
            '[Desktop Entry]\nType=Application\nName=Legacy Application\n'
            'Exec=/old/Application.AppImage\n'
            'X-AppInstall-Manifest=' + str(manifest) + '\n'
        )
        stale.write_text(original)
        result = self.register()
        self.assertIn('Skipped stale AppInstall launcher', result.stderr)
        self.assertNotIn('[Errno 2]', result.stderr)
        self.assertIn('No files were removed', result.stderr)
        self.assertEqual(stale.read_text(), original)
        self.assertFalse(manifest.exists())
        again = self.register()
        self.assertIn('Skipped stale AppInstall launcher', again.stderr)
        self.assertEqual(stale.read_text(), original)

    def test_uninstall_respects_default_changed_after_installation(self):
        self.register()
        current = self.defaults_file.read_text()
        self.assertIn(MIME + "=appinstall.desktop;", current)
        self.defaults_file.write_text(
            current.replace(MIME + "=appinstall.desktop;", MIME + "=user-choice.desktop;")
        )
        self.register("--uninstall")
        final = self.defaults_file.read_text()
        self.assertIn(MIME + "=user-choice.desktop;", final)
        self.assertIn("text/plain=editor.desktop;", final)


if __name__ == "__main__":
    unittest.main()
