import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import package_meta as meta

class MetaGuardTests(unittest.TestCase):
    """Local reference metadata must never resolve traversal fragments."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.apps=self.root/'applications'; self.apps.mkdir()
    def tearDown(self): self.temp.cleanup()
    def ref(self,name):
        path=self.root/'sample.flatpakref'
        path.write_text('[Flatpak Ref]\nName='+name+'\nComment=shown\n')
        return meta.display_metadata(path,'flatpakref',[self.root])
    def test_plain_reference(self):
        out=self.ref('org.example.Test')
        self.assertEqual(out['appid'],'org.example.Test')
        self.assertEqual(out['name'],'Test')
        self.assertEqual(out['description'],'shown')
    def test_traversal_fragment_is_discarded(self):
        secret=self.root/'secret.ini'
        secret.write_text('[Desktop Entry]\nName=SECRETLEAK\nComment=leak\n')
        out=self.ref('../secret')
        self.assertEqual(out['appid'],'')
        self.assertNotIn('SECRETLEAK',out['name']+out['description'])
    def test_absolute_fragment_is_discarded(self):
        out=self.ref('/etc/passwd')
        self.assertEqual(out['appid'],'')
    def test_valid_id_still_looks_up_installed_entry(self):
        installed=self.apps/'org.test.Valid.desktop'
        installed.write_text('[Desktop Entry]\nName=Installed Name\nComment=local description\n')
        out=self.ref('org.test.Valid')
        self.assertEqual(out['name'],'Installed Name')
        self.assertEqual(out['description'],'local description')
    def test_invalid_id_never_touches_application_lookup(self):
        weird=self.apps/'..%2F..%2Fpasswd.desktop'
        weird.write_text('[Desktop Entry]\nName=WEIRDLEAK\n')
        out=self.ref('bad/id')
        self.assertEqual(out['appid'],'')
        self.assertNotEqual(out['name'],'WEIRDLEAK')

class ConfirmExitCodes(unittest.TestCase):
    """0=install, 1=cancel, 2=unexpected failure, 3=Qt unavailable — with --probe working headless."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def run_confirm(self,*args):
        return subprocess.run([sys.executable,str(ROOT/'confirm.py'),*args],capture_output=True,text=True,timeout=30)
    def test_probe_reports_metadata(self):
        ref=self.root/'app.flatpakref'
        ref.write_text('[Flatpak Ref]\nName=org.example.App\nComment=Explanation on the review screen.\n')
        result=self.run_confirm(str(ref),'flatpakref','','--probe')
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['appid'],'org.example.App')
        self.assertEqual(data['name'],'App')
        self.assertGreater(data['size'],0)
    def test_unexpected_failure_is_two(self):
        ref=self.root/'broken.flatpakref'
        ref.write_text('[Flatpak Ref]\nName=org.example.App\n')
        result=self.run_confirm(str(ref),'deb','not-json')
        self.assertEqual(result.returncode,2,result.stderr)
        self.assertIn('Traceback',result.stderr)
    def test_missing_file_is_crash_not_cancel(self):
        result=self.run_confirm('/nonexistent/example.flatpakref','flatpakref','','--probe')
        self.assertIn(result.returncode,(0,2))
        self.assertNotEqual(result.returncode,1)

class InstallerConfirmFallback(unittest.TestCase):
    """Exit 3 must fall back to the dialog confirmation instead of silently doing nothing."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.home=Path(self.tmp.name)
        self.bin=self.home/'bin'; self.bin.mkdir()
        python=self.bin/'python3'
        confirm=ROOT/'confirm.py'
        python.write_text('#!/bin/sh\ncase "$1" in *confirm.py) exit 3;; *) exec /usr/bin/python3 "$@";; esac\n')
        python.chmod(0o755)
        dialog=self.bin/'kdialog'
        dialog.write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "'+str(self.home/'dialogs.log')+'"\ncase "$1" in --yesno|--getopenfilename) exit 0;; esac\nexit 0\n')
        dialog.chmod(0o755)
        backend=self.bin/'flatpak'
        backend.write_text('#!/bin/sh\ncase "$1" in list) exit 0;; install) exit 0;; esac\nexit 1\n')
        backend.chmod(0o755)
        self.env=dict(os.environ,HOME=str(self.home),XDG_DATA_HOME=str(self.home/'data'),
                      XDG_CONFIG_HOME=str(self.home/'config'),PATH=str(self.bin)+':'+os.environ['PATH'])
    def tearDown(self): self.tmp.cleanup()
    def test_fallback_confirm_runs_installer(self):
        f=self.home/'app.flatpak'
        f.write_text('[Flatpak Ref]\nName=org.example.App\n')
        result=subprocess.run([str(ROOT/'appinstall'),'--nolaunch',str(f)],env=self.env,capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        log_text=(self.home/'dialogs.log').read_text() if (self.home/'dialogs.log').exists() else ''
        self.assertIn('Format: flatpak',log_text)

SQUASHFS=shutil.which('mksquashfs') and shutil.which('unsquashfs')

@unittest.skipIf(not SQUASHFS,'squashfs tools required')
class PassiveAppImagePreview(unittest.TestCase):
    """Preview unpacks contents without executing the image's own runtime."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def make_appimage(self,body):
        source=self.root/'appimg-root'; source.mkdir()
        (source/'AppRun').write_text('#!/bin/sh\ntouch "'+str(self.root/'EXECUTION-MARKER')+'"\n')
        (source/'.DirIcon').write_bytes((ROOT/'appinstall.desktop').read_bytes() and b'\x89PNG\r\n\x1a\n' or b'')
        (source/'.DirIcon').write_bytes(b'')
        sfs=self.root/'payload.sfs'
        subprocess.run(['mksquashfs',str(source),str(sfs),'-no-progress','-all-time','0','-mkfs-time','0'],check=True,capture_output=True)
        blob=sfs.read_bytes()
        stub=bytes.fromhex('7f454c460201010000')+b'\x00'+b'\x41\x49\x02'
        image=self.root/'tiny.AppImage'
        image.write_bytes(stub+b'\x00'*(1024-len(stub))+blob)
        return image
    def test_passive_extraction_never_runs_the_image(self):
        import appimage_backend
        image=self.make_appimage(None)
        scratch=self.root/'scratch'; scratch.mkdir()
        root=appimage_backend.preview_contents(image,scratch)
        self.assertTrue((root/'AppRun').is_file())
        self.assertFalse((self.root/'EXECUTION-MARKER').exists())
        self.assertIsInstance(appimage_backend.squashfs_offset(image),int)
    def test_fallback_path_is_reported_not_hidden(self):
        import appimage_backend
        image=self.make_appimage(None)
        scratch=self.root/'scratch2'; scratch.mkdir()
        with patch.object(__import__('shutil'),'which',lambda name: None if name=='unsquashfs' else shutil.which(name)):
            with self.assertRaises(RuntimeError):
                appimage_backend.preview_contents(image,scratch)

class FlushedLaunchLog(unittest.TestCase):
    """Startup output must be present on disk even for sub-second launches."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,{'XDG_DATA_HOME':str(self.root/'data'),'XDG_STATE_HOME':str(self.root/'state')})
        self.env.start()
    def tearDown(self): self.env.stop(); self.temp.cleanup()
    def test_quick_exit_log_is_flushed(self):
        import launch_monitor as m
        script="print('uniq-1.0-beta-log-marker')"
        desktop=self.root/'quick.desktop'
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Quick\nIcon=quick\nExec='+m.desktop_quote(sys.executable)+' -c '+m.desktop_quote(script)+' %U\n')
        spec=m.wrap_desktop('test:quick',desktop,'test')
        result=m.monitor(spec,notify=False,startup=2)
        self.assertEqual(result['status'],'detached_or_exited_unverified')
        Path(result['log']).read_text().count('uniq-1.0-beta-log-marker')>=1 or self.fail('flushed log missed startup output')

if __name__=='__main__':
    unittest.main()
