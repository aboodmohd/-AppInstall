"""Phase 5: bounded, source-qualified PNG/WebP artwork cache tests."""
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import catalog_artwork as art


def sample_png():
    """Produce a real 1x1 RGB PNG, without Pillow or network."""
    def chunk(name, data):
        return (struct.pack(">I", len(data)) + name + data +
                struct.pack(">I", zlib.crc32(name + data) & 0xffffffff))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
            + chunk(b"IEND", b""))


class FakeResponse:
    def __init__(self, url, data, mime="image/png", final=None):
        self.url = url
        self.data = data
        self.headers = {"Content-Type": mime}
        self.final = final or url
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.final

    def read(self, count):
        self.calls.append(count)
        return self.data[:count]


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.count = 0

    def open(self, req, timeout):
        self.count += 1
        self.req = req
        return self.response


class TrustedArtworkTests(unittest.TestCase):
    DEB = ("https://appstream.debian.org/media/pool/"
           "org/gimp/GIMP/icon.png")
    FLATPAK = "https://dl.flathub.org/media/org/gimp/GIMP/icons/gimp.png"
    APPIMAGE = "https://appimage.github.io/database/SomeApp/icons/icon.png"

    def test_valid_bitmap_source_mapping_is_strict(self):
        self.assertTrue(art.trusted_url("Flatpak", self.FLATPAK))
        self.assertTrue(art.trusted_url("DEB", self.DEB))
        self.assertTrue(art.trusted_url("AppImage", self.APPIMAGE))
        self.assertFalse(art.trusted_url("RPM", self.DEB))
        self.assertFalse(art.trusted_url("DEB", self.FLATPAK))
        self.assertFalse(art.trusted_url("RPM", self.APPIMAGE))

    def test_untrusted_artwork_is_discarded_before_network(self):
        bad = (
            "https://evil.invalid/icon.png",
            "https://dl.flathub.org.evil.invalid/media/icon.png",
            "http://dl.flathub.org/media/icon.png",
            "file:///etc/passwd",
            "https://user:pass@dl.flathub.org/media/icon.png",
            "https://dl.flathub.org/media/../private/icon.png",
            "https://dl.flathub.org/media/%2e%2e/icon.png",
            "https://dl.flathub.org/media/icon.svg",
            "https://dl.flathub.org/media/icon.png?key=secret",
            "https://dl.flathub.org/media/icon.png#fragment",
            "https://dl.flathub.org:bad/media/icon.png",
        )
        for url in bad:
            with self.subTest(url=url):
                self.assertFalse(art.trusted_url("Flatpak", url))
                with patch.object(art.urllib.request, "build_opener") as open_:
                    self.assertEqual(art.get("Flatpak", "org.gimp.GIMP", url), "")
                open_.assert_not_called()

    def test_svg_and_oversize_or_absurd_dimensions_never_become_cached(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        self.assertEqual(art._format(svg), "")
        self.assertEqual(art._format(b"x" * (art.MAX_IMAGE_BYTES + 1)), "")
        oversized = bytearray(sample_png())
        oversized[16:24] = struct.pack(">II", 8192, 8192)
        self.assertEqual(art._format(bytes(oversized)), "")

    def test_zero_fetch_limit_causes_zero_network_or_worker_calls(self):
        with patch.object(art, "get") as fetch:
            self.assertEqual(art.cache_results([{
                "source": "Flatpak", "appId": "org.example.App",
                "iconUrl": self.FLATPAK
            }], limit=0), {})
        fetch.assert_not_called()


class CacheTests(unittest.TestCase):
    FLATPAK = "https://dl.flathub.org/media/org/gimp/GIMP/icons/gimp.png"
    IMAGE = sample_png()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"XDG_CACHE_HOME": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)

    def test_first_download_saves_private_verified_local_icon_and_cache_reuses(self):
        opener = FakeOpener(FakeResponse(self.FLATPAK, self.IMAGE))
        first = art.get("Flatpak", "org.gimp.GIMP", self.FLATPAK, opener=opener)
        self.assertTrue(first.startswith("file:///"), first)
        target = Path(first.removeprefix("file://"))
        self.assertTrue(target.is_file())
        self.assertEqual(target.read_bytes(), self.IMAGE)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(opener.count, 1)
        second = art.get("Flatpak", "org.gimp.GIMP", self.FLATPAK, opener=opener)
        self.assertEqual(second, first)
        self.assertEqual(opener.count, 1)

    def test_source_namespaces_do_not_share_cache_identity(self):
        with patch.object(art, "_download", return_value=self.IMAGE):
            self.assertNotEqual(
                art.get("DEB", "gimp",
                        "https://appstream.debian.org/media/pool/gimp/icons/icon.png"),
                art.get("Flatpak", "gimp", self.FLATPAK))

    def test_wrong_mime_or_redirect_is_rejected(self):
        for mime, final in (
            ("text/html", self.FLATPAK),
            ("image/svg+xml", self.FLATPAK),
            ("image/png", "https://evil.invalid/icon.png"),
        ):
            with self.subTest(mime=mime, final=final):
                opener = FakeOpener(FakeResponse(
                    self.FLATPAK, self.IMAGE, mime=mime, final=final))
                self.assertEqual(
                    art._download(self.FLATPAK, opener=opener), b"")

    def test_invalid_image_body_does_not_poison_cache(self):
        opener = FakeOpener(FakeResponse(self.FLATPAK, b"not-an-image"))
        self.assertEqual(
            art.get("Flatpak", "org.example.App", self.FLATPAK, opener=opener), "")
        self.assertEqual(list(art.cache_dir().iterdir()), [])

    def test_symlinked_cache_root_is_not_followed(self):
        cache_parent = Path(self.tmp.name) / "appinstall"
        cache_parent.mkdir()
        target = Path(self.tmp.name) / "other"
        target.mkdir()
        (cache_parent / "catalog-artwork").symlink_to(target, target_is_directory=True)
        with patch.object(art, "_download") as download:
            self.assertEqual(
                art.get("Flatpak", "org.example.App", self.FLATPAK), "")
        download.assert_not_called()

    def test_stale_verified_cache_remains_available_offline(self):
        with patch.object(art, "_download", return_value=self.IMAGE):
            first = art.get("Flatpak", "org.example.App", self.FLATPAK)
        old = Path(first.removeprefix("file://"))
        os.utime(old, (1, 1))
        with patch.object(art, "_download", return_value=b""):
            self.assertEqual(
                art.get("Flatpak", "org.example.App", self.FLATPAK), first)

    def test_cached_map_is_limited_to_same_source_valid_urls(self):
        rows = [
            {"source": "DEB", "appId": "gimp",
             "iconUrl": "https://appstream.debian.org/media/pool/gimp/icons/icon.png"},
            {"source": "DEB", "appId": "gimp-doc",
             "iconUrl": "https://evil.invalid/icon.png"},
            {"source": "DEB", "appId": "inkscape",
             "iconUrl": "https://appstream.debian.org/media/pool/inkscape/icons/icon.png"},
        ]
        with patch.object(art, "get", side_effect=lambda s, app, u: "file:///tmp/" + app) as fetch:
            result = art.cache_results(rows, limit=1)
        self.assertEqual(result, {"gimp": "file:///tmp/gimp"})
        fetch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
