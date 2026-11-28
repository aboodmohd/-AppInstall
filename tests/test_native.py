import importlib.util
from pathlib import Path
import tempfile
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
    def _inspect(self, output_values, kind='deb'):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / ('example.deb' if kind == 'deb' else 'example.rpm')
            package.write_bytes(b'fixture')
            with patch.object(Path, 'read_text', return_value='ID=ubuntu' if kind == 'deb' else 'ID=fedora'), \
                 patch.object(native.shutil, 'which', return_value='/usr/bin/manager'), \
                 patch.object(native, 'output', side_effect=output_values):
                return native.inspect(str(package))

    def test_native_deb_architectures(self):
        for host, package in (('amd64', 'amd64'), ('arm64', 'arm64'), ('arm64', 'all')):
            with self.subTest(host=host, package=package):
                info = self._inspect([f'example 1 {package} desc', 'example', '1',
                                      package, host, ''])
                self.assertEqual(info['name'], 'example')
                self.assertEqual(info['version'], '1')

    def test_wrong_deb_architecture_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'architecture'):
            self._inspect(['example 1 amd64 desc', 'example', '1', 'amd64', 'arm64', ''])

    def test_native_rpm_architectures(self):
        for host, package in (('x86_64', 'x86_64'), ('aarch64', 'aarch64'),
                              ('aarch64', 'noarch')):
            with self.subTest(host=host, package=package):
                info = self._inspect([f'example\n1-2\n{package}\nDescription',
                                      host, ''], kind='rpm')
                self.assertEqual(info['name'], 'example')
                self.assertEqual(info['version'], '1-2')

    def test_wrong_rpm_architecture_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'architecture'):
            self._inspect(['example\n1-2\nx86_64\nDescription', 'aarch64', ''],
                          kind='rpm')

    def test_install_arguments(self):
        with patch.object(native.shutil,'which',return_value='/usr/bin/apt-get'),patch.object(native.subprocess,'run') as run:
            native.install(dict(manager='apt-get',installed='',version='1',name='example',file='/tmp/space ; file.deb'))
            self.assertEqual(run.call_args.args[0],['pkexec','/usr/bin/apt-get','install','--assume-yes','--no-remove','/tmp/space ; file.deb'])
