"""Format detection edge cases: misleading extensions, magic-byte precedence."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

import url_install as u


class MisleadingExtensionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp(prefix="urlfmt-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _write(self, name, head):
        p = self.tempdir / name
        p.write_bytes(head)
        return p

    def test_appimage_extension_but_html_content_is_rejected(self):
        head = b"<html><body>release page</body></html>"
        with self.assertRaises(u.DownloadError):
            u.detect_format(self._write("misleading.AppImage", head),
                            url_hint="https://example.com/x.AppImage")

    def test_deb_extension_but_rpm_magic_is_detected_as_rpm(self):
        head = b"\xed\xab\xee\xdb" + b"\x00" * 100
        self.assertEqual(u.detect_format(self._write("m.deb", head),
                                         url_hint="https://example.com/m.deb"), "rpm")

    def test_rpm_extension_but_deb_magic_is_detected_as_deb(self):
        head = b"!<arch>\n" + b"\x00" * 60
        self.assertEqual(u.detect_format(self._write("n.rpm", head),
                                         url_hint="https://example.com/n.rpm"), "deb")

    def test_plain_elf_without_appimage_marker_is_rejected(self):
        head = b"\x7fELF" + b"\x00" * 60
        with self.assertRaises(u.DownloadError):
            u.detect_format(self._write("o.elf", head))

    def test_flatpakref_content_detected_even_with_wrong_extension(self):
        head = b"[Flatpak Ref]\nName=org.example.App\nUrl=https://flathub.org/repo\n"
        self.assertEqual(u.detect_format(self._write("p.bin", head),
                                         url_hint="https://example.com/p"), "flatpakref")

    def test_flatpakrepo_content_detected_even_with_wrong_extension(self):
        head = b"[Flatpak Repo]\nTitle=Example\nUrl=https://flathub.org/repo\n"
        self.assertEqual(u.detect_format(self._write("q.bin", head),
                                         url_hint="https://example.com/q"), "flatpakrepo")

    def test_unknown_extension_and_no_magic_is_rejected(self):
        with self.assertRaises(u.DownloadError):
            u.detect_format(self._write("r.xyz", b"\x00\x01\x02\x03"),
                            url_hint="https://example.com/r.xyz")

    def test_unknown_content_with_appimage_url_is_rejected(self):
        # The .AppImage extension alone is not evidence: garbage must not be
        # handed to the AppImage backend (misleading-extension protection).
        with self.assertRaises(u.DownloadError):
            u.detect_format(self._write("s.bin", b"\x00\x01\x02\x03\x04"),
                            url_hint="https://example.com/s.AppImage")

    def test_unknown_content_with_deb_url_is_rejected(self):
        with self.assertRaises(u.DownloadError):
            u.detect_format(self._write("t.bin", b"\x00\x01\x02\x03\x04"),
                            url_hint="https://example.com/t.deb")

    def test_unknown_content_with_rpm_url_is_rejected(self):
        with self.assertRaises(u.DownloadError):
            u.detect_format(self._write("u.bin", b"\x00\x01\x02\x03\x04"),
                            url_hint="https://example.com/u.rpm")

    def test_unknown_content_with_flatpak_url_uses_extension_hint(self):
        # Only the Flatpak bundle lacks reliable magic; its extension is the
        # one and only trusted hint.
        self.assertEqual(u.detect_format(self._write("v.bin", b"\x00\x01\x02\x03\x04"),
                                         url_hint="https://example.com/v.flatpak"),
                         "flatpak")


if __name__ == "__main__":
    unittest.main()
