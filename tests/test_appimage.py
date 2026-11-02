import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('backend', Path(__file__).resolve().parents[1]/'appimage_backend.py')
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

class AppImageTests(unittest.TestCase):
    def test_install_replace_and_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'download.AppImage'
            # ELF stub + squashfs magic so passive preview locates the payload offset.
            source.write_bytes(bytes.fromhex('7f454c460201010000')+b'\x00\x41\x49\x02'+b'\x00'*1000+b'hsqs'+b'\x00'*256)
            destination = root/'Applications'
            env = {'XDG_DATA_HOME':str(root/'data'), 'XDG_STATE_HOME':str(root/'state')}
            def extract(argv, **kwargs):
                # Stand-in for unsquashfs: passive unpack only, nothing spawns the image.
                self.assertNotIn('--appimage-extract', argv)
                appdir = Path(argv[argv.index('-d')+1])
                appdir.mkdir()
                (appdir/'AppRun').write_text('#!/bin/sh\n')
                (appdir/'AppRun').chmod(0o755)
                (appdir/'icon.png').write_bytes(b'icon')
                (appdir/'app.desktop').write_text('[Desktop Entry]\nType=Application\nName=Example App\nExec=AppRun --example %U\nCategories=Entertainment;\nIcon=icon\n')
                return subprocess.CompletedProcess(argv,0,b'')
            passive = {'unsquashfs':'/usr/bin/unsquashfs'}
            with patch.dict(os.environ, env), patch.object(backend.shutil,'which',lambda name:passive.get(name) if name in passive else backend.shutil.which(name)), patch.object(backend.subprocess,'run',side_effect=extract):
                backend.install(source,destination)
                entry = next((root/'data/applications').glob('*.desktop'))
                meta = backend.desktop(entry)
                info = json.loads(Path(meta['X-AppInstall-Manifest']).read_text())
                self.assertEqual(info['args'],['--example'])
                self.assertEqual(meta['Categories'],'AudioVideo;')
                self.assertEqual(Path(meta['Icon']).read_bytes(),b'icon')
                self.assertTrue(source.exists())
                self.assertEqual(entry.name, 'app.desktop')
                # Simulate the app rewriting its own desktop entry on launch.
                entry.write_text('[Desktop Entry]\nType=Application\nName=Example App\nTryExec='+info['target']+'\nExec='+info['target']+'\nIcon=icon\n')
                # A legacy AppInstall entry must be retired at the next install.
                legacy = entry.parent/'appinstall-legacy.desktop'
                legacy.write_text('[Desktop Entry]\nType=Application\nName=Example App\n')
                first = info['generation']
                backend.install(source,destination,True)
                self.assertFalse(Path(first).exists())
                self.assertEqual(len(list((root/'data/applications').glob('*.desktop'))),1)
                before = entry.read_text()
                manifest = Path(backend.desktop(entry)['X-AppInstall-Manifest'])
                current = manifest.read_text()
            with patch.dict(os.environ,env), patch.object(backend.shutil,'which',lambda name:passive.get(name) if name in passive else backend.shutil.which(name)), patch.object(backend.subprocess,'run',return_value=subprocess.CompletedProcess([],1,b'broken image')):
                with self.assertRaises(RuntimeError):
                    backend.install(source,destination)
                self.assertEqual(entry.read_text(),before)
                self.assertEqual(manifest.read_text(),current)
    def test_categories_and_identity(self):
        self.assertEqual(backend.categories('Development;IDE;'), 'Development;IDE;')
        self.assertEqual(backend.categories('Entertainment;'), 'AudioVideo;')
        self.assertEqual(backend.categories(''), 'Utility;')
        self.assertEqual(backend.app_name('Example (3.10.4)'), 'Example')

    def test_launch_without_interception(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp)/'app.json'
            manifest.write_text(json.dumps(dict(target='/example/app',args=['--option'],fallback='')))
            with patch.object(backend.os,'execvpe') as execute:
                backend.run(manifest,['https://example.org'])
            command, argv, env = execute.call_args.args
            self.assertEqual(argv,['/example/app','--option','https://example.org'])
            self.assertEqual(env['APPIMAGELAUNCHER_DISABLE'],'1')

if __name__ == '__main__':
    unittest.main()
