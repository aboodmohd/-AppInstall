"""Tests for url_install.py: secure download, validation and format detection.

No real network is used. DNS resolution is stubbed to a public address and the
HTTP response is faked, so every download path (progress, size limit,
cancellation, checksum) runs locally and deterministically.
"""

from __future__ import annotations

import hashlib
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

import url_install as u


# ── helpers ──────────────────────────────────────────────────────────────

PUBLIC_ADDR = [("AF_INET", None, None, None, ("93.184.216.34", 0))]


def stub_dns():
    """Stub socket.getaddrinfo to resolve any host to a public address."""
    return patch.object(u.socket, "getaddrinfo", return_value=PUBLIC_ADDR)


class FakeResponse:
    """Minimal fake urllib response: headers, geturl, chunked read, close."""

    def __init__(self, chunks, url="https://example.com/file.AppImage",
                 content_length=None, content_type="application/octet-stream"):
        self._chunks = list(chunks)
        self._url = url
        self._headers = MagicMock()
        self.headers = self._headers
        cl = str(content_length) if content_length is not None else None
        self._headers.get = lambda key, default=None: {
            "Content-Length": cl,
            "Content-Type": content_type,
        }.get(key, default)
        self.closed = False

    def geturl(self):
        return self._url

    def read(self, size=-1):
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    def close(self):
        self.closed = True


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.opened_url = None
        self.timeout = None

    def open(self, request, timeout=None):
        self.opened_url = (request.full_url if hasattr(request, "full_url")
                           else str(request))
        self.timeout = timeout
        return self.response


# ── URL validation ─────────────────────────────────────────────────────

class UrlValidationTests(unittest.TestCase):
    def test_accepts_https(self):
        with stub_dns():
            parsed = u.validate_url("https://example.com/app.AppImage")
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.hostname, "example.com")

    def test_rejects_no_scheme(self):
        with self.assertRaises(u.DownloadError):
            u.validate_url("example.com/app.AppImage")

    def test_rejects_non_https(self):
        for url in ("http://example.com/x", "ftp://example.com/x"):
            with self.assertRaises(u.DownloadError):
                u.validate_url(url)

    def test_rejects_missing_host(self):
        with self.assertRaises(u.DownloadError):
            u.validate_url("https:///x")

    def test_rejects_credentials(self):
        with self.assertRaises(u.DownloadError):
            u.validate_url("https://user:pass@example.com/x")

    def test_rejects_localhost(self):
        with self.assertRaises(u.DownloadError):
            u.validate_url("https://localhost/x")

    def test_rejects_loopback_v4(self):
        with self.assertRaises(u.DownloadError):
            u.validate_url("https://127.0.0.1/x")

    def test_rejects_private_v4(self):
        for host in ("10.0.0.5", "192.168.1.1", "172.16.0.1"):
            with self.assertRaises(u.DownloadError):
                u.validate_url("https://" + host + "/x")

    def test_rejects_link_local_metadata(self):
        with self.assertRaises(u.DownloadError):
            u.validate_url("https://169.254.169.254/x")

    def test_rejects_loopback_v6(self):
        with self.assertRaises(u.DownloadError):
            u.validate_url("https://[::1]/x")

    def test_rejects_invalid(self):
        with self.assertRaises(u.DownloadError):
            u.validate_url("not-a-url")


class BlockedAddressTests(unittest.TestCase):
    def test_is_blocked_address(self):
        self.assertTrue(u._is_blocked_address("127.0.0.1"))
        self.assertTrue(u._is_blocked_address("10.0.0.1"))
        self.assertTrue(u._is_blocked_address("192.168.1.1"))
        self.assertTrue(u._is_blocked_address("172.16.0.1"))
        self.assertTrue(u._is_blocked_address("169.254.0.1"))
        self.assertTrue(u._is_blocked_address("224.0.0.1"))
        self.assertTrue(u._is_blocked_address("::1"))
        self.assertTrue(u._is_blocked_address("fe80::1"))
        self.assertFalse(u._is_blocked_address("93.184.216.34"))
        self.assertFalse(u._is_blocked_address("1.2.3.4"))
        self.assertTrue(u._is_blocked_address("not-an-ip"))

    def test_ipv4_mapped_v6_loopback_blocked(self):
        self.assertTrue(u._is_blocked_address("::ffff:127.0.0.1"))


class DnsRebindingTests(unittest.TestCase):
    """DNS rebinding: a host resolving to any unsafe address is refused."""

    def test_mixed_public_and_private_addresses_blocked(self):
        def fake_getaddrinfo(host, port, *args, **kwargs):
            return [("AF_INET", None, None, None, ("93.184.216.34", 0)),
                    ("AF_INET", None, None, None, ("10.0.0.1", 0))]
        with patch.object(u.socket, "getaddrinfo", fake_getaddrinfo):
            with self.assertRaises(u.DownloadError):
                u.validate_url("https://rebinding.example.com/x")

    def test_mixed_public_and_linklocal_addresses_blocked(self):
        def fake_getaddrinfo(host, port, *args, **kwargs):
            return [("AF_INET", None, None, None, ("93.184.216.34", 0)),
                    ("AF_INET", None, None, None, ("169.254.169.254", 0))]
        with patch.object(u.socket, "getaddrinfo", fake_getaddrinfo):
            with self.assertRaises(u.DownloadError):
                u.validate_url("https://rebinding.example.com/x")

    def test_all_public_addresses_allowed(self):
        def fake_getaddrinfo(host, port, *args, **kwargs):
            return [("AF_INET", None, None, None, ("93.184.216.34", 0)),
                    ("AF_INET6", None, None, None, ("2606:2800:220:1::", 0))]
        with patch.object(u.socket, "getaddrinfo", fake_getaddrinfo):
            parsed = u.validate_url("https://example.com/x")
            self.assertEqual(parsed.hostname, "example.com")


class RedirectProtectionTests(unittest.TestCase):
    """Redirect destinations are re-validated like the original URL."""

    def _download_with_response(self, response, **kwargs):
        with patch.object(u.socket, "getaddrinfo",
                          return_value=[("AF_INET", None, None, None,
                                         ("93.184.216.34", 0))]), \
             patch.object(u, "build_opener",
                          lambda handler: FakeOpener(response)):
            return u.download_url("https://example.com/file.AppImage", **kwargs)

    def test_redirect_to_blocked_url_is_rejected(self):
        response = FakeResponse([], url="https://localhost/evil.AppImage")
        with self.assertRaises(u.DownloadError):
            self._download_with_response(response)

    def test_redirect_to_private_address_is_rejected(self):
        response = FakeResponse([], url="https://10.0.0.1/evil.AppImage")
        with self.assertRaises(u.DownloadError):
            self._download_with_response(response)

    def test_redirect_to_linklocal_metadata_is_rejected(self):
        response = FakeResponse([], url="https://169.254.169.254/evil.AppImage")
        with self.assertRaises(u.DownloadError):
            self._download_with_response(response)

    def test_too_many_redirects_is_rejected(self):
        with patch.object(u.socket, "getaddrinfo",
                          return_value=[("AF_INET", None, None, None,
                                         ("93.184.216.34", 0))]):
            handler = u._SafeRedirectHandler()
            fake_req = type('FakeReq', (), {'header_items': lambda self: [],
                                            'method': 'GET'})()
            # MAX_REDIRECTS redirects are allowed; the next one is rejected.
            for i in range(u.MAX_REDIRECTS):
                handler.redirect_request(fake_req, None, 302, "Moved",
                                         {}, "https://example.com/next")
            with self.assertRaises(u.DownloadError):
                handler.redirect_request(fake_req, None, 302, "Moved",
                                         {}, "https://example.com/next")


# ── Filename sanitization ──────────────────────────────────────────────

class SanitizeTests(unittest.TestCase):
    def test_sanitize_strips_path(self):
        # Path traversal collapses to the safe basename only.
        self.assertEqual(u._sanitize_filename("../evil/AppImage"), "AppImage")
        self.assertEqual(u._sanitize_filename("dir/sub/file.deb"), "file.deb")
        self.assertNotIn("/", u._sanitize_filename("../evil/AppImage"))
        self.assertNotIn("..", u._sanitize_filename("../evil/AppImage"))

    def test_sanitize_unsafe_chars(self):
        self.assertEqual(u._sanitize_filename("a  b!!c"), "a-b-c")

    def test_sanitize_empty_and_dot(self):
        self.assertEqual(u._sanitize_filename(""), "download")
        self.assertEqual(u._sanitize_filename("."), "download")
        self.assertEqual(u._sanitize_filename(".."), "download")

    def test_sanitize_preserves_extension(self):
        self.assertEqual(u._sanitize_filename("my app.AppImage"), "my-app.AppImage")


# ── Format detection ───────────────────────────────────────────────────

class FormatDetectionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp(prefix="urlformat-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _write(self, name, head):
        p = self.tempdir / name
        p.write_bytes(head)
        return p

    def test_appimage_magic(self):
        head = b"\x7fELF" + b"\x00" * 4 + b"AI" + b"\x00" * 40
        self.assertEqual(u.detect_format(self._write("a.AppImage", head)), "appimage")

    def test_appimage_elf_without_ai_is_not_appimage(self):
        head = b"\x7fELF" + b"\x00" * 60  # plain ELF, no AppImage marker
        with self.assertRaises(u.DownloadError):
            u.detect_format(self._write("plain.elf", head))

    def test_deb_magic(self):
        self.assertEqual(u.detect_format(self._write("b.deb", b"!<arch>\n" + b"\x00" * 60)), "deb")

    def test_rpm_magic(self):
        self.assertEqual(u.detect_format(self._write("c.rpm", b"\xed\xab\xee\xdb" + b"\x00" * 100)), "rpm")

    def test_flatpakref(self):
        self.assertEqual(u.detect_format(self._write("d.flatpakref", b"[Flatpak Ref]\nName=x\n")), "flatpakref")

    def test_flatpakrepo(self):
        self.assertEqual(u.detect_format(self._write("e.flatpakrepo", b"[Flatpak Repo]\nTitle=x\n")), "flatpakrepo")

    def test_flatpak_bundle_by_extension(self):
        self.assertEqual(u.detect_format(self._write("f.flatpak", b"\x00\x01\x02\x03"),
                                         url_hint="https://example.com/f.flatpak"), "flatpak")

    def test_html_rejected(self):
        with self.assertRaises(u.DownloadError):
            u.detect_format(self._write("g.html", b"<html><body>page</body></html>"))

    def test_empty_rejected(self):
        with self.assertRaises(u.DownloadError):
            u.detect_format(self._write("h.empty", b""))

    def test_unknown_rejected(self):
        with self.assertRaises(u.DownloadError):
            u.detect_format(self._write("i.bin", b"\x00\x01\x02\x03\x04\x05"))


# ── Download ───────────────────────────────────────────────────────────

class DownloadTests(unittest.TestCase):
    def _download(self, chunks, **kwargs):
        response = FakeResponse(chunks, content_length=kwargs.pop("content_length", None))
        with stub_dns(), patch.object(u, "build_opener",
                                      lambda handler: FakeOpener(response)):
            return u.download_url("https://example.com/file.AppImage", **kwargs)

    def test_download_success(self):
        data = b"chunk-one" * 1000
        result = self._download([data])
        self.assertEqual(result.detected_format, "appimage")
        self.assertEqual(result.size, len(data))
        self.assertEqual(result.sha256, hashlib.sha256(data).hexdigest())
        self.assertTrue(result.path.is_file())
        self.assertEqual(result.path.read_bytes(), data)

    def test_download_reports_sha256(self):
        data = b"some payload bytes"
        result = self._download([data])
        self.assertEqual(result.sha256, hashlib.sha256(data).hexdigest())

    def test_download_extension_added(self):
        data = b"\x7fELF" + b"\x00" * 4 + b"AI" + b"\x00" * 40
        result = self._download([data])
        self.assertTrue(result.filename.endswith(".AppImage"))

    def test_download_progress_callback(self):
        calls = []
        data = b"x" * 1000
        def prog(info):
            calls.append(info)
        self._download([data[:500], data[500:]], progress=prog,
                       content_length=len(data))
        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual(calls[-1]["bytes_downloaded"], len(data))
        self.assertEqual(calls[-1]["percent"], 100.0)
        self.assertIsNotNone(calls[-1]["bytes_per_second"])

    def test_download_indeterminate_without_content_length(self):
        calls = []
        data = b"y" * 500
        def prog(info):
            calls.append(info)
        self._download([data], progress=prog)
        self.assertIsNone(calls[-1]["total_size"])
        self.assertIsNone(calls[-1]["percent"])

    def test_download_size_limit_enforced(self):
        temp_root = Path(tempfile.mkdtemp(prefix="urlsize-"))
        data = b"z" * 2000
        with self.assertRaises(u.DownloadSizeExceeded):
            self._download([data], max_size=500, temp_root=temp_root)
        # the per-download temp directory must be removed
        self.assertEqual([p.name for p in temp_root.iterdir()], [])
        import shutil
        shutil.rmtree(temp_root, ignore_errors=True)

    def test_download_checksum_match(self):
        data = b"checksum payload"
        result = self._download([data], expected_checksum=hashlib.sha256(data).hexdigest())
        self.assertEqual(result.sha256, hashlib.sha256(data).hexdigest())

    def test_download_checksum_mismatch(self):
        data = b"checksum payload"
        with self.assertRaises(u.ChecksumMismatch):
            self._download([data], expected_checksum="0" * 64)

    def test_download_cancellation(self):
        cancel = threading.Event()
        data = b"cancellable" * 1000
        response = FakeResponse([data[:100], data[100:]])
        with stub_dns(), patch.object(u, "build_opener",
                                      lambda handler: FakeOpener(response)):
            cancel.set()  # cancel immediately
            with self.assertRaises(u.DownloadCancelled):
                u.download_url("https://example.com/file.AppImage", cancel=cancel)

    def test_download_http_error(self):
        with stub_dns():
            def boom(handler):
                class BoomOpener:
                    def open(self, request, timeout=None):
                        raise u.HTTPError("https://example.com/x", 404, "Not Found", {}, None)
                return BoomOpener()
            with patch.object(u, "build_opener", boom):
                with self.assertRaises(u.DownloadError):
                    u.download_url("https://example.com/x")

    def test_human_size(self):
        self.assertEqual(u.human_size(0), "0 B")
        self.assertIn("KiB", u.human_size(2048))
        self.assertIn("MiB", u.human_size(2048 * 1024))


if __name__ == "__main__":
    unittest.main()
