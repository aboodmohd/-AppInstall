import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('native',Path(__file__).resolve().parents[1]/'native_backend.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
class NativeTests(unittest.TestCase):
    def test_distribution_routing(self):
        for release,kind,expected in [('ID=ubuntu','deb','apt-get'),('ID=fedora','rpm','dnf'),('ID=opensuse-tumbleweed','rpm','zypper')]:
            with patch.object(Path,'read_text',return_value=release):
                self.assertEqual(native.backend(kind),expected)
    def test_cachyos_rejected(self):
        with patch.object(Path,'read_text',return_value='ID=cachyos\nID_LIKE=arch'),patch.object(native.subprocess,'run') as run:
            for kind in ('deb','rpm'):
                with self.assertRaises(RuntimeError): native.backend(kind)
            run.assert_not_called()
    def test_install_arguments(self):
        with patch.object(native.shutil,'which',return_value='/usr/bin/apt-get'),patch.object(native.subprocess,'run') as run:
            native.install(dict(manager='apt-get',installed='',version='1',name='example',file='/tmp/space ; file.deb'))
            self.assertEqual(run.call_args.args[0],['pkexec','/usr/bin/apt-get','install','--assume-yes','--no-remove','/tmp/space ; file.deb'])
