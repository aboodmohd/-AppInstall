"""Syntax gates for executable Python entry points."""
import py_compile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('integration.py', 'launch_monitor.py', 'container_backend.py',
           'appimage_backend.py', 'url_install.py', 'manager.py',
           'manager_qml.py', 'portable_update.py')


class SourceSyntaxTests(unittest.TestCase):
    def test_entry_points_compile(self):
        for name in MODULES:
            with self.subTest(module=name):
                py_compile.compile(str(ROOT/name), doraise=True)


if __name__ == '__main__':
    unittest.main()
