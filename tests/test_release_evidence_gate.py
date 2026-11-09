"""Exercise the actual package evidence gate without building or installing."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('evidence_gate', ROOT / 'tools/ci_release_evidence_gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ReleaseEvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'PKGBUILD').write_bytes((ROOT / 'PKGBUILD').read_bytes())
        self.license = (ROOT / 'LICENSE').read_bytes()
        (self.root / 'LICENSE').write_bytes(self.license)
        self.package = self.root / 'candidate.pkg.tar.zst'
        self.package.write_bytes(b'mocked archive')
        self.files = 'usr/bin/appinstall\nusr/share/licenses/appinstall/LICENSE\n'

    def verify(self, files=None, license_data=None):
        results = [subprocess.CompletedProcess([], 0, self.files if files is None else files),
                   subprocess.CompletedProcess([], 0, self.license if license_data is None else license_data)]
        with patch.object(gate, 'ROOT', self.root), \
             patch.object(gate.subprocess, 'run', side_effect=results), \
             contextlib.redirect_stdout(io.StringIO()):
            gate.verify_package(self.package)

    def test_current_pkgbuild_passes_source_parser_and_package_checks(self):
        self.verify()

    def test_evidence_source_is_rejected(self):
        path = self.root / 'PKGBUILD'
        path.write_text(path.read_text().replace("'appinstall'", "'evidence/secret.txt'", 1))
        with self.assertRaisesRegex(ValueError, 'references evidence'):
            self.verify()

    def test_png_source_is_rejected(self):
        path = self.root / 'PKGBUILD'
        path.write_text(path.read_text().replace("'appinstall'", "'secret.png'", 1))
        with self.assertRaisesRegex(ValueError, 'references evidence'):
            self.verify()

    def test_packaged_images_and_evidence_are_rejected(self):
        for extra in ('usr/share/picture.png', 'usr/share/evidence/phase4/RESULTS.md'):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'screenshot/image evidence'):
                self.verify(files=self.files + extra + '\n')

    def test_missing_packaged_license_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'missing its MIT license'):
            self.verify(files='usr/bin/appinstall\n')

    def test_changed_packaged_license_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'differs from'):
            self.verify(license_data=b'changed license')
