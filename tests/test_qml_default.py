"""TDD: QML is the default UI for the Installed Applications Manager.

These tests are written BEFORE the appinstall changes they describe. They
verify which manager backend `appinstall` dispatches to:

  * `appinstall --manage`        -> manager_qml.py   (QML default)
  * `appinstall --widgets`       -> manager.py       (Widgets fallback)
  * `appinstall` (no args)       -> manager_qml.py   (QML default)
  * `appinstall --manage --widgets` -> manager.py    (Widgets fallback)

python3 is stubbed to record its arguments and exit 0, so no real GUI is
launched. Dialog tools (kdialog/zenity/notify-send/flatpak) are stubbed to
exit 1, and DISPLAY/WAYLAND_DISPLAY are unset so qt_message returns early.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class QmlDefaultDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.bin = self.home / 'bin'
        self.bin.mkdir()
        # Stub out GUI helpers so no real dialogs open.
        for tool in ('kdialog', 'zenity', 'notify-send', 'flatpak'):
            stub = self.bin / tool
            stub.write_text('#!/bin/sh\nexit 1\n')
            stub.chmod(0o755)
        # Stub python3: record every argument, then exit without launching a GUI.
        self.calls_log = self.home / 'python_calls.log'
        self.calls_log.write_text('')
        python = self.bin / 'python3'
        python.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$@" >> "{}"; exit 0\n'.format(
                self.calls_log))
        python.chmod(0o755)
        self.env = dict(
            os.environ,
            HOME=str(self.home),
            XDG_DATA_HOME=str(self.home / 'data'),
            XDG_CONFIG_HOME=str(self.home / 'config'),
            PATH=str(self.bin) + ':' + os.environ['PATH'],
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_app(self, *args):
        return subprocess.run(
            [str(ROOT / 'appinstall'), *map(str, args)],
            env=self.env, capture_output=True, text=True)

    def launched_managers(self):
        """Basenames of manager scripts python3 was asked to run, in order."""
        managers = []
        for line in self.calls_log.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if parts and Path(parts[0]).name in ('manager.py', 'manager_qml.py'):
                managers.append(Path(parts[0]).name)
        return managers

    def test_manage_launches_qml_manager_by_default(self):
        self.run_app('--manage')
        self.assertEqual(self.launched_managers(), ['manager_qml.py'])

    def test_widgets_launches_widgets_manager(self):
        self.run_app('--widgets')
        self.assertEqual(self.launched_managers(), ['manager.py'])

    def test_no_args_launches_qml_manager_by_default(self):
        self.run_app()
        self.assertEqual(self.launched_managers(), ['manager_qml.py'])

    def test_manage_with_widgets_launches_widgets_manager(self):
        # --widgets must be honoured whether it precedes or follows --manage.
        self.run_app('--manage', '--widgets')
        self.run_app('--widgets', '--manage')
        self.assertEqual(self.launched_managers(), ['manager.py', 'manager.py'])

    def test_integration_modules_include_manager_qml(self):
        integration = ROOT / 'integration.py'
        text = integration.read_text()
        self.assertIn("'manager_qml.py'", text)


if __name__ == '__main__':
    unittest.main()
