import importlib.util
import contextlib
import errno
import io
import sys
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
            themed_icon = root/'data/icons/hicolor/256x256/apps/icon.png'
            themed_icon.parent.mkdir(parents=True)
            themed_icon.write_bytes(b'existing user-owned themed icon')
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
                self.assertEqual(themed_icon.read_bytes(),
                                 b'existing user-owned themed icon')
                self.assertTrue(source.exists())
                self.assertEqual(entry.name, 'app.desktop')
                # Simulate the app rewriting its own desktop entry on launch.
                entry.write_text('[Desktop Entry]\nType=Application\nName=Example App\nTryExec='+info['target']+'\nExec='+info['target']+'\nIcon=icon\n')
                # A legacy AppInstall entry must be retired at the next install.
                legacy = entry.parent/'appinstall-legacy.desktop'
                legacy.write_text('[Desktop Entry]\nType=Application\nName=Example App\n')
                first = Path(info['generation'])
                result = backend.install(source,destination,True)
                self.assertFalse(first.exists())
                self.assertIsInstance(result, Path)
                self.assertEqual(result, entry)
                self.assertEqual(len(list((root/'data/applications').glob('*.desktop'))),1)
                self.assertIsNotNone(result)
                self.assertTrue(entry.is_file())
                manifest = Path(backend.desktop(entry)['X-AppInstall-Manifest'])
                self.assertTrue(manifest.is_file())
                current = json.loads(manifest.read_text())
                self.assertTrue(Path(current['fallback'], 'AppRun').is_file())
                before_entry, before_manifest = entry.read_bytes(), manifest.read_bytes()
                before_payload = Path(current['target']).read_bytes()
                generations = set(destination.iterdir())
                # Fail during publication, after replacing the manifest. The
                # old manifest, launcher and payload must survive together.
                real_replace = Path.replace
                def fail_launcher(path, target):
                    if path == entry.with_suffix('.new'):
                        raise OSError(errno.ENOSPC, 'simulated full filesystem')
                    return real_replace(path, target)
                with patch.object(Path, 'replace', fail_launcher):
                    with self.assertRaises(OSError):
                        backend.install(source, destination)
                self.assertEqual(entry.read_bytes(), before_entry)
                self.assertEqual(manifest.read_bytes(), before_manifest)
                self.assertEqual(Path(current['target']).read_bytes(), before_payload)
                self.assertEqual(set(destination.iterdir()), generations)
                # An extracted launch cannot silently accept unreadable contents.
                with patch.object(backend.subprocess, 'run', return_value=
                                  subprocess.CompletedProcess([], 1, b'broken image')):
                    with self.assertRaisesRegex(RuntimeError, 'Extracted launches require'):
                        backend.install(source, destination, True)
                self.assertEqual(entry.read_bytes(), before_entry)
                self.assertEqual(manifest.read_bytes(), before_manifest)
                self.assertEqual(Path(current['target']).read_bytes(), before_payload)
                self.assertEqual(set(destination.iterdir()), generations)
    def test_passive_preview_failures_allow_normal_install(self):
        for error in (backend.PreviewUnavailable('no passive reader'),
                      RuntimeError('passive extraction failed')):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source = root / 'Example.AppImage'
                source.write_bytes(fixture_appimage())
                env = {'XDG_DATA_HOME': str(root / 'data'),
                       'XDG_STATE_HOME': str(root / 'state')}
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch.dict(os.environ, env), \
                     patch.object(backend, 'preview_contents', side_effect=error), \
                     patch.object(backend.subprocess, 'run') as run, \
                     contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    result = backend.install(source, root / 'Applications')
                run.assert_not_called()  # Never execute the image for preview.
                self.assertIsInstance(result, Path)
                self.assertTrue(result.is_file())
                self.assertEqual(stdout.getvalue(), '')
                self.assertIn('Detailed preview unavailable', stderr.getvalue())
                manifest = Path(backend.desktop(result)['X-AppInstall-Manifest'])
                info = json.loads(manifest.read_text())
                self.assertEqual(info['fallback'], '')
                self.assertEqual(Path(info['target']).read_bytes(), source.read_bytes())

    def test_cli_stdout_is_desktop_path_and_open_manifest_is_usable(self):
        with tempfile.TemporaryDirectory(prefix='appinstall cli ') as temp:
            root = Path(temp)
            source = root / 'Example App.AppImage'
            # No SquashFS: deterministic passive fallback without dependencies.
            source.write_bytes(b'\x7fELF' + b'\0' * 100)
            env = dict(os.environ, HOME=str(root),
                       XDG_DATA_HOME=str(root / 'data'), XDG_STATE_HOME=str(root / 'state'))
            result = subprocess.run(
                [sys.executable, str(Path(backend.__file__)), str(source), str(root / 'Applications')],
                env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(result.stdout.splitlines()), 1)
            entry = Path(result.stdout.strip())
            self.assertTrue(entry.is_file())
            manifest = backend.desktop(entry)['X-AppInstall-Manifest']
            info = json.loads(Path(manifest).read_text())
            with patch.object(backend.os, 'execvpe') as execute:
                backend.run(manifest, [])
            self.assertEqual(execute.call_args.args[0], info['target'])
            self.assertTrue(Path(info['target']).is_file())

    def test_shell_installer_passes_cli_manifest_to_open_action(self):
        script = (Path(backend.__file__).parent / 'appinstall').read_text()
        def function(name):
            start = script.index(name + '() {')
            return script[start:script.index('\n}', start) + 2]
        with tempfile.TemporaryDirectory(prefix='appinstall shell ') as temp:
            root = Path(temp)
            source = root / 'Example App.AppImage'
            source.write_bytes(b'\x7fELF' + b'\0' * 100)
            env = dict(os.environ, HOME=str(root),
                       XDG_DATA_HOME=str(root / 'data'), XDG_STATE_HOME=str(root / 'state'),
                       INSTALL_DIR=str(root / 'Applications'), APPS_DIR=str(root / 'data/applications'),
                       OPEN_ARGS=str(root / 'open-args'), NOTICE=str(root / 'notice'),
                       NO_OPEN='0', ASSUME_YES='0')
            # Run the actual installer function and backend. Stub desktop UI,
            # database refresh and launch so no application is opened.
            harness = function('desktop_key') + '\n' + function('install_appimage_pkg') + r"""
validate_appimage() { return 0; }
ldconfig() { printf '%s\n' 'libfuse.so.2'; }
progress_start() { :; }
progress_close() { :; }
have() { return 1; }
dialog_confirm() { return 0; }
notify_ok() { printf '%s\n' "$1" > "$NOTICE"; }
error_dialog() { printf '%s\n' "$1" >&2; }
nohup() { printf '%s\n' "$@" > "$OPEN_ARGS"; }
install_appimage_pkg "$1"
result=$?
wait
exit "$result"
"""
            result = subprocess.run(
                ['bash', '-c', harness, str(Path(backend.__file__).parent / 'appinstall'), str(source)],
                env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            args = (root / 'open-args').read_text().splitlines()
            self.assertEqual(args[:3], ['python3', str(Path(backend.__file__)), '--run'])
            self.assertEqual(len(args), 4)
            manifest = Path(args[3])
            self.assertTrue(manifest.is_file())
            self.assertTrue(Path(json.loads(manifest.read_text())['target']).is_file())
            self.assertIn('Installed Example App', (root / 'notice').read_text())

    def test_retires_legacy_shortcut_but_never_deletes_legacy_appimage(self):
        """Existing AppImageLauncher payload belongs to the user, not AppInstall."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'new.AppImage'
            source.write_bytes(fixture_appimage())
            destination = root/'Applications'
            destination.mkdir()
            old_payload = destination/'previous.AppImage'
            old_payload.write_bytes(b'important previous version')
            apps = root/'data/applications'
            apps.mkdir(parents=True)
            legacy = apps/'appimagekit_previous.desktop'
            legacy.write_text(
                '[Desktop Entry]\nType=Application\nName=Example App\n'
                f'TryExec={old_payload}\nExec={old_payload}\n')
            env = {'XDG_DATA_HOME': str(root/'data'),
                   'XDG_STATE_HOME': str(root/'state')}

            def extract(argv, **kwargs):
                appdir = Path(argv[argv.index('-d') + 1])
                appdir.mkdir()
                (appdir/'AppRun').write_text('#!/bin/sh\n')
                (appdir/'app.desktop').write_text(
                    '[Desktop Entry]\nType=Application\nName=Example App\n'
                    'Exec=AppRun %U\n')
                return subprocess.CompletedProcess(argv, 0, b'')

            with patch.dict(os.environ, env), \
                 patch.object(backend.shutil, 'which',
                              lambda name: '/usr/bin/unsquashfs' if name == 'unsquashfs' else None), \
                 patch.object(backend.subprocess, 'run', side_effect=extract):
                backend.install(source, destination)
            self.assertFalse(legacy.exists())
            self.assertEqual(old_payload.read_bytes(), b'important previous version')
            backup = root/'data/appinstall/launcher-backups'/legacy.name
            self.assertTrue(backup.exists())

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
            self.assertIn('launch_monitor.py', backend.desktop(launcher)['Exec'])

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
            # Invalid top-level metadata must not block a nested safe entry.
            (appdir/'safe.desktop').unlink()
            nested = appdir/'usr/share/applications'
            nested.mkdir(parents=True)
            (nested/'nested.desktop').write_text(
                '[Desktop Entry]\nType=Application\nName=Nested\n')
            self.assertEqual([p.name for p in backend.safe_desktop_files(appdir)],
                             ['nested.desktop'])

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
