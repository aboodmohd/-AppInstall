import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch,MagicMock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication,QPushButton
    import diagnostics_ui as ui
except ImportError:
    ui=None

@unittest.skipIf(ui is None,'PySide6 is optional')
class DiagnosticsUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,{'XDG_DATA_HOME':str(self.root/'data'),'XDG_STATE_HOME':str(self.root/'state')});self.env.start()
    def tearDown(self):self.env.stop();self.temp.cleanup()
    def test_error_buttons_and_copy_details(self):
        import launch_monitor as m
        spec=dict(key='test:ui',name='UI Example',format='test',desktop=str(self.root/'app.desktop'),command='true')
        m.update_registry(spec['key'],spec);attempt=m.new_attempt(spec);attempt['error']=m.failure('crash','The application exited unexpectedly.');m.SafeLog(attempt['log']).add('Startup test')
        window=ui.FailureWindow(attempt)
        buttons={b.text():b for b in window.findChildren(QPushButton)}
        self.assertIn('View Logs',buttons);self.assertIn('Copy Error Details',buttons)
        clipboard=MagicMock()
        with patch.object(ui.QApplication,'clipboard',return_value=clipboard):buttons['Copy Error Details'].click()
        self.assertIn('UI Example',clipboard.setText.call_args.args[0]);self.assertIn('crash',clipboard.setText.call_args.args[0])
        with patch.object(ui,'LogWindow') as logs:
            buttons['View Logs'].click();logs.assert_called_once_with(attempt['log'],window)
        window.close()
    def test_diagnostics_inventory_and_safe_buttons(self):
        import launch_monitor as m
        spec=dict(key='test:ui',name='UI Example',format='test',desktop=str(self.root/'app.desktop'),command='true')
        m.update_registry(spec['key'],spec)
        window=ui.Diagnostics();self.assertEqual(window.table.rowCount(),1)
        self.assertFalse(window.buttons['Repair Dependency'].isEnabled());self.assertFalse(window.buttons['Port Owner'].isEnabled());self.assertFalse(window.buttons['Uninstall'].isEnabled())
        window.close()
