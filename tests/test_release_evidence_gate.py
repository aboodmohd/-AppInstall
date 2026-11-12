"""Exercise the actual package evidence gate without building or installing.

Covers the narrowed image policy: only the eight official AppInstall icon
sources (distinct makepkg-compatible basenames) and their hicolor installed
destinations are permitted PNGs; every other PNG, all evidence/phase4 assets,
unrelated screenshots and unexpected images are rejected. MIT license
preservation is maintained.
"""
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
        (self.root / 'LICENSE').write_bytes((ROOT / 'LICENSE').read_bytes())
        # The gate validates icon sources at ROOT/<name>, so stage the real
        # official icon sources in the disposable root.
        for name in gate.APP_INSTALL_ICON_SOURCES:
            (self.root / name).write_bytes((ROOT / name).read_bytes())
        self.license = (ROOT / 'LICENSE').read_bytes()
        self.package = self.root / 'candidate.pkg.tar.zst'
        self.package.write_bytes(b'mocked archive')
        icon_lines = ''.join(
            f'usr/share/icons/hicolor/{s}x{s}/apps/appinstall.png\n'
            for s in gate.APP_INSTALL_ICON_SIZES)
        self.files = ('usr/bin/appinstall\n' + icon_lines +
                      'usr/share/licenses/appinstall/LICENSE\n')

    def verify(self, files=None, license_data=None):
        results = [subprocess.CompletedProcess([], 0, self.files if files is None else files),
                   subprocess.CompletedProcess([], 0, self.license if license_data is None else license_data)]
        with patch.object(gate, 'ROOT', self.root), \
             patch.object(gate.subprocess, 'run', side_effect=results), \
             contextlib.redirect_stdout(io.StringIO()):
            gate.verify_package(self.package)

    def test_current_pkgbuild_passes_source_parser_and_package_checks(self):
        """Official icons + license are permitted; evidence stays out."""
        self.verify()

    def test_permitted_official_icons_are_allowed(self):
        """All eight icon sizes pass both source and package checks."""
        # Sources already validated by test_current_pkgbuild_passes_*; assert
        # the packaged inventory matches exactly.
        self.verify()

    def test_evidence_source_is_rejected(self):
        path = self.root / 'PKGBUILD'
        path.write_text(path.read_text().replace("'appinstall'", "'evidence/secret.txt'", 1))
        with self.assertRaisesRegex(ValueError, 'references evidence'):
            self.verify()

    def test_unexpected_png_source_is_rejected(self):
        """A non-icon PNG source (even one named like an icon) is rejected."""
        path = self.root / 'PKGBUILD'
        text = path.read_text().replace("'appinstall'", "'secret.png'", 1)
        path.write_text(text)
        with self.assertRaisesRegex(ValueError, 'unexpectedly references image assets'):
            self.verify()

    def test_fake_icon_source_is_rejected(self):
        """An invented icon basename not in the official inventory is rejected."""
        path = self.root / 'PKGBUILD'
        text = path.read_text().replace("'DEPENDENCY_LICENSE_AUDIT.md'",
                                        "'DEPENDENCY_LICENSE_AUDIT.md'\n        'appinstall-99.png'", 1)
        path.write_text(text)
        with self.assertRaisesRegex(ValueError, 'unexpectedly references image assets'):
            self.verify()

    def test_icon_source_inventory_must_be_complete(self):
        """Dropping one official icon source is rejected."""
        path = self.root / 'PKGBUILD'
        text = path.read_text().replace("'appinstall-16.png'\n", "", 1)
        path.write_text(text)
        with self.assertRaisesRegex(ValueError, 'icon source inventory'):
            self.verify()

    def test_packaged_unexpected_image_is_rejected(self):
        for extra in ('usr/share/picture.png', 'usr/share/icons/hicolor/99x99/apps/appinstall.png',
                      'usr/share/evidence/phase4/RESULTS.md'):
            with self.subTest(extra=extra), self.assertRaisesRegex(
                    ValueError, 'unexpectedly includes screenshot/image evidence'):
                self.verify(files=self.files + extra + '\n')

    def test_packaged_icon_inventory_must_be_complete(self):
        """Dropping one packaged icon is rejected."""
        missing = 'usr/share/icons/hicolor/512x512/apps/appinstall.png\n'
        files = self.files.replace(missing, "", 1)
        with self.assertRaisesRegex(ValueError, 'Packaged AppInstall icon inventory'):
            self.verify(files=files)

    def test_missing_packaged_license_is_rejected(self):
        # Icons present, license omitted: must fail at the license check.
        icon_lines = ''.join(
            f'usr/share/icons/hicolor/{s}x{s}/apps/appinstall.png\n'
            for s in gate.APP_INSTALL_ICON_SIZES)
        files = 'usr/bin/appinstall\n' + icon_lines
        with self.assertRaisesRegex(ValueError, 'missing its MIT license'):
            self.verify(files=files)

    def test_changed_packaged_license_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'differs from'):
            self.verify(license_data=b'changed license')


if __name__ == '__main__':
    unittest.main()
