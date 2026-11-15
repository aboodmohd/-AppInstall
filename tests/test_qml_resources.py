"""Regression tests: source-installed QML resources.

Verifies that integration.py deploys manager_qml.py together with its
manager_ui/ QML files (Theme.qml, main.qml, AppCard.qml, qmldir) to the
user state directory, that the source-installed QML manager launches
headlessly without relying on repository files, and that uninstall removes
all QML resources.

Uses an isolated HOME so no real user data is touched.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class QmlResourceDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.bin = self.home / 'bin'
        self.bin.mkdir()
        # Stub GUI helpers so no real dialogs open.
        for tool in ('kdialog', 'zenity', 'notify-send', 'flatpak'):
            stub = self.bin / tool
            stub.write_text('#!/bin/sh\nexit 1\n')
            stub.chmod(0o755)
        # Stub python3 to a no-op so integration.py can run but we verify
        # deployment separately through direct file checks.
        self.env = dict(
            os.environ,
            HOME=str(self.home),
            XDG_DATA_HOME=str(self.home / 'data'),
            XDG_CONFIG_HOME=str(self.home / 'config'),
            PATH=str(self.bin) + ':' + os.environ['PATH'],
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_integration(self, *extra):
        """Run integration.py with the isolated HOME."""
        return subprocess.run(
            ['python3', str(ROOT / 'integration.py'), *map(str, extra)],
            env=self.env, capture_output=True, text=True)

    def state(self, *parts):
        return self.home / 'data' / 'appinstall' / Path(*parts)

    def test_integration_deploys_manager_qml_and_qml_files(self):
        """integration.py installs manager_qml.py plus manager_ui/ QML files."""
        result = self.run_integration()
        self.assertEqual(result.returncode, 0, result.stderr)
        # Python module deployed.
        self.assertTrue(self.state('manager_qml.py').is_file(),
                        'manager_qml.py not deployed')
        # QML files deployed alongside.
        for qml in ('qmldir', 'Theme.qml', 'main.qml', 'AppCard.qml'):
            self.assertTrue(self.state('manager_ui', qml).is_file(),
                            f'manager_ui/{qml} not deployed')

    def test_source_installed_qml_launches_headlessly(self):
        """The source-installed manager_qml.py loads without repo files."""
        self.run_integration()
        # Run the deployed manager_qml.py in headless smoke mode from a
        # directory other than the repo root, so it cannot rely on
        # repository-located QML files.
        env_no_repo = dict(self.env)
        env_no_repo.pop('PYTHONPATH', None)
        result = subprocess.run(
            ['python3', str(self.state('manager_qml.py')), '--smoke'],
            env=env_no_repo, capture_output=True, text=True,
            cwd=self.tmp.name,
            timeout=30)
        self.assertEqual(result.returncode, 0,
                         f'QML smoke failed: {result.stderr[-500:]}')

    def test_uninstall_removes_qml_resources(self):
        """integration.py --uninstall removes manager_qml.py and QML files."""
        self.run_integration()
        # Verify deployment first.
        self.assertTrue(self.state('manager_qml.py').is_file())
        self.assertTrue(self.state('manager_ui', 'main.qml').is_file())
        # Uninstall.
        result = self.run_integration('--uninstall')
        self.assertEqual(result.returncode, 0, result.stderr)
        # QML resources removed.
        self.assertFalse(self.state('manager_qml.py').exists(),
                         'manager_qml.py not removed')
        self.assertFalse(self.state('manager_ui', 'main.qml').exists(),
                         'manager_ui/main.qml not removed')
        self.assertFalse(self.state('manager_ui', 'Theme.qml').exists(),
                         'manager_ui/Theme.qml not removed')
        self.assertFalse(self.state('manager_ui', 'AppCard.qml').exists(),
                         'manager_ui/AppCard.qml not removed')
        self.assertFalse(self.state('manager_ui', 'qmldir').exists(),
                         'manager_ui/qmldir not removed')


if __name__ == '__main__':
    unittest.main()
