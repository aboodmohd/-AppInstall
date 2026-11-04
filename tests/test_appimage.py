import importlib.util
import json
import os
import struct
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('backend', Path(__file__).resolve().parents[1]/'appimage_backend.py')
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


def fixture_appimage():
    """Synthetic SquashFS v4 metadata for mocked-extraction tests."""
    runtime = bytes.fromhex('7f454c460201010000') + b'\x00\x41\x49\x02' + b'\x00' * 1000
    superblock = bytearray(128)
    superblock[:4] = b'hsqs'
    struct.pack_into('<I', superblock, 4, 1)
    struct.pack_into('<I', superblock, 12, 131072)
    struct.pack_into('<H', superblock, 20, 1)
    struct.pack_into('<H', superblock, 22, 17)
    struct.pack_into('<HH', superblock, 28, 4, 0)
    struct.pack_into('<Q', superblock, 40, len(superblock))
    struct.pack_into('<Q', superblock, 64, 96)
    struct.pack_into('<Q', superblock, 72, 96)
    return runtime + bytes(superblock)


class AppImageTests(unittest.TestCase):

    def test_squashfs_offset_skips_false_magic_in_runtime(self):
        """Mizuki/AnymeX runtimes: false magic at 194183; actual header at 944632."""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'sample.AppImage'
            data = bytearray(944632)
            data[:4] = b'\x7fELF'
            data[8:11] = b'AI\x02'
            data[194183:194187] = b'hsqs'
            data.extend(fixture_appimage()[1013:])
            path.write_bytes(data)
            self.assertEqual(backend.squashfs_offset(path), 944632)

    def test_squashfs_offset_supports_runtime_over_one_megabyte(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'large-runtime.AppImage'
            offset = 1500000
            data = bytearray(offset)
            data[:4] = b'\x7fELF'
            data[8:11] = b'AI\x02'
            data.extend(fixture_appimage()[1013:])
            path.write_bytes(data)
            self.assertEqual(backend.squashfs_offset(path), offset)

    def test_squashfs_offset_across_chunk_boundary_and_rejects_magic_only(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'boundary.AppImage'
            data = bytearray(65534)
            data.extend(fixture_appimage()[1013:])
            path.write_bytes(data)
            self.assertEqual(backend.squashfs_offset(path), 65534)
            path.write_bytes(b'\x00' * 1000 + b'hsqs' + b'\x00' * 256)
            self.assertIsNone(backend.squashfs_offset(path))


    def test_install_replace_and_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'download.AppImage'
            # ELF stub + squashfs magic so passive preview locates the payload offset.
            source.write_bytes(fixture_appimage())
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

    def test_desktop_entry_includes_startup_wm_class(self):
        """Generated desktop entry includes StartupWMClass from embedded metadata."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'download.AppImage'
            source.write_bytes(fixture_appimage())
            destination = root/'Applications'
            env = {'XDG_DATA_HOME':str(root/'data'), 'XDG_STATE_HOME':str(root/'state')}
            def extract(argv, **kwargs):
                self.assertNotIn('--appimage-extract', argv)
                appdir = Path(argv[argv.index('-d')+1])
                appdir.mkdir()
                (appdir/'AppRun').write_text('#!/bin/sh\n')
                (appdir/'AppRun').chmod(0o755)
                (appdir/'app.desktop').write_text(
                    '[Desktop Entry]\nType=Application\nName=Example App\n'
                    'Exec=AppRun --example %U\nCategories=Entertainment;\nIcon=icon\n'
                    'StartupWMClass=example-app\n')
                return subprocess.CompletedProcess(argv,0,b'')
            passive = {'unsquashfs':'/usr/bin/unsquashfs'}
            with patch.dict(os.environ, env), patch.object(backend.shutil,'which',lambda name:passive.get(name) if name in passive else backend.shutil.which(name)), patch.object(backend.subprocess,'run',side_effect=extract):
                backend.install(source,destination)
                entry = next((root/'data/applications').glob('*.desktop'))
                meta = backend.desktop(entry)
                self.assertEqual(meta.get('StartupWMClass'),'example-app')

    def test_embedded_multiline_metadata_cannot_inject_launcher_commands(self):
        """Continuation lines must not become executable desktop-file keys."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'download.AppImage'
            source.write_bytes(fixture_appimage())
            destination = root/'Applications'
            env = {'XDG_DATA_HOME': str(root/'data'),
                   'XDG_STATE_HOME': str(root/'state')}

            def extract(argv, **kwargs):
                appdir = Path(argv[argv.index('-d') + 1])
                appdir.mkdir()
                (appdir/'AppRun').write_text('#!/bin/sh\n')
                (appdir/'app.desktop').write_text(
                    '[Desktop Entry]\nType=Application\nName=Example App\n'
                    'Exec=AppRun %U\n'
                    'StartupWMClass=example\n'
                    ' Exec=/bin/false\n'
                    ' Actions=untrusted;\n'
                    'Comment=Description\n'
                    ' Exec=/bin/false\n')
                return subprocess.CompletedProcess(argv, 0, b'')

            with patch.dict(os.environ, env), \
                 patch.object(backend.shutil, 'which',
                              lambda name: '/usr/bin/unsquashfs' if name == 'unsquashfs' else None), \
                 patch.object(backend.subprocess, 'run', side_effect=extract):
                backend.install(source, destination)
            launcher = next((root/'data/applications').glob('*.desktop'))
            text = launcher.read_text()
            self.assertEqual(text.count('\nExec='), 1)
            self.assertEqual(text.count('\nActions='), 0)
            self.assertNotIn('\nExec=/bin/false', text)
            self.assertIn('StartupWMClass=example', text)
            self.assertIn('appimage_backend.py', backend.desktop(launcher)['Exec'])

    def test_passive_metadata_ignores_symlinks_outside_appdir(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            appdir = base/'squashfs-root'
            appdir.mkdir()
            private = base/'private.desktop'
            private.write_text('[Desktop Entry]\nName=Do Not Read\n')
            (appdir/'external.desktop').symlink_to(private)
            (appdir/'safe.desktop').write_text('[Desktop Entry]\nName=Safe\n')
            self.assertEqual([p.name for p in backend.safe_desktop_files(appdir)],
                             ['safe.desktop'])

    def test_desktop_entry_includes_try_exec(self):
        """Generated desktop entry's TryExec is preserved through wrap_desktop."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'download.AppImage'
            source.write_bytes(fixture_appimage())
            destination = root/'Applications'
            env = {'XDG_DATA_HOME':str(root/'data'), 'XDG_STATE_HOME':str(root/'state')}
            def extract(argv, **kwargs):
                self.assertNotIn('--appimage-extract', argv)
                appdir = Path(argv[argv.index('-d')+1])
                appdir.mkdir()
                (appdir/'AppRun').write_text('#!/bin/sh\n')
                (appdir/'AppRun').chmod(0o755)
                (appdir/'app.desktop').write_text(
                    '[Desktop Entry]\nType=Application\nName=Example App\n'
                    'Exec=AppRun --example %U\nCategories=Entertainment;\nIcon=icon\n')
                return subprocess.CompletedProcess(argv,0,b'')
            passive = {'unsquashfs':'/usr/bin/unsquashfs'}
            with patch.dict(os.environ, env), patch.object(backend.shutil,'which',lambda name:passive.get(name) if name in passive else backend.shutil.which(name)), patch.object(backend.subprocess,'run',side_effect=extract):
                backend.install(source,destination)
                entry = next((root/'data/applications').glob('*.desktop'))
                text = entry.read_text()
                # TryExec points to the staged image in the generation directory
                self.assertIn('TryExec=', text)
                self.assertIn('download.AppImage', text)

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
