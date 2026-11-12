"""Tests for url_install.py: secure download, validation and format detection.

No real network is used. DNS resolution is stubbed to a public address and the
HTTP response is faked, so every download path (progress, size limit,
cancellation, checksum) runs locally and deterministically.
"""

from __future__ import annotations

import hashlib
import inspect
import io
import os
import subprocess
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
            addresses = u._resolve_public_addresses("example.com")
        self.assertEqual(addresses, ("93.184.216.34", "2606:2800:220:1::"))

    def test_resolver_fail_closed_on_resolution_failure(self):
        # NXDOMAIN and any resolution error must fail closed, never open.
        with patch.object(u.socket, "getaddrinfo",
                          side_effect=u.socket.gaierror("Name or service not known")):
            with self.assertRaises(u.DownloadError):
                u._resolve_public_addresses("missing.example.com")

    def test_resolver_fail_closed_on_empty_answer(self):
        with patch.object(u.socket, "getaddrinfo", return_value=[]):
            with self.assertRaises(u.DownloadError):
                u._resolve_public_addresses("empty.example.com")

    def test_resolver_reports_blocked_address_in_error(self):
        def fake_getaddrinfo(host, port, *args, **kwargs):
            return [("AF_INET", None, None, None, ("169.254.169.254", 0))]
        with patch.object(u.socket, "getaddrinfo", fake_getaddrinfo):
            with self.assertRaises(u.DownloadError) as ctx:
                u._resolve_public_addresses("metadata.example.com")
        self.assertIn("169.254.169.254", str(ctx.exception))

    def test_pinned_connection_refuses_without_allowed_addresses(self):
        # Fail closed: a pinned connection must never dial an unvalidated host.
        conn = u._PinnedHTTPSConnection("example.com", allowed_addresses=())
        with self.assertRaises(u.DownloadError):
            conn._create_validated_connection(("example.com", 443))

    def test_pinned_connection_dials_only_validated_addresses(self):
        # The pinning hook must dial the validated literal, not the hostname.
        dialed = []
        def fake_create_connection(address, timeout=None, source_address=None):
            dialed.append(address)
            return object()
        with patch.object(u.socket, "create_connection", fake_create_connection):
            conn = u._PinnedHTTPSConnection("example.com",
                                            allowed_addresses=("93.184.216.34",))
            conn._create_validated_connection(("example.com", 8443))
        self.assertEqual(dialed, [("93.184.216.34", 8443)])

    def test_pinned_connection_keeps_tls_hostname_verification(self):
        # TLS must stay tied to the hostname: the subclass overrides only the
        # TCP dial hook and never touches the stdlib connect()/wrap_socket
        # path that performs SNI and certificate verification.
        source = inspect.getsource(u._PinnedHTTPSConnection)
        self.assertNotIn("wrap_socket", source)
        self.assertNotIn("check_hostname", source)
        self.assertIn("_create_connection", source)
        # The stdlib connect() (TLS wrap with server_hostname) is inherited.
        self.assertTrue(hasattr(u.HTTPSConnection, "connect"))
        self.assertIn("server_hostname", inspect.getsource(u.HTTPSConnection.connect))

    # Realistic DNS-rebinding scenarios (DNS changes between validation and
    # connection, redirect loops, proxies) run against a real local HTTPS
    # server in tests/test_url_rebinding.py.


class RedirectProtectionTests(unittest.TestCase):
    """Redirect destinations are re-validated like the original URL."""

    def _download_with_response(self, response, **kwargs):
        with patch.object(u.socket, "getaddrinfo",
                          return_value=[("AF_INET", None, None, None,
                                         ("93.184.216.34", 0))]), \
             patch.object(u, "build_opener",
                          lambda *handlers: FakeOpener(response)):
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
                                            'get_method': lambda self: 'GET'})()
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
    # Arbitrary payloads detect as "flatpak" via the (only) extension hint,
    # so these tests exercise download mechanics rather than detection.
    DOWNLOAD_URL = "https://example.com/file.flatpak"

    def _download(self, chunks, url=None, **kwargs):
        response = FakeResponse(chunks, content_length=kwargs.pop("content_length", None))
        with stub_dns(), patch.object(u, "build_opener",
                                      lambda *handlers: FakeOpener(response)):
            return u.download_url(url or self.DOWNLOAD_URL, **kwargs)

    def test_download_success(self):
        data = b"chunk-one" * 1000
        result = self._download([data])
        self.assertEqual(result.detected_format, "flatpak")
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

    def test_download_checksum_mismatch_cleans_temp(self):
        temp_root = Path(tempfile.mkdtemp(prefix="urlchk-"))
        data = b"checksum payload"
        try:
            with self.assertRaises(u.ChecksumMismatch):
                self._download([data], expected_checksum="0" * 64,
                               temp_root=temp_root)
            self.assertEqual([p.name for p in temp_root.iterdir()], [])
        finally:
            import shutil
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_download_unsupported_format_cleans_temp(self):
        # A file no detector recognizes (post-download failure) must not leave
        # a temporary directory behind. The URL carries no package extension,
        # so the garbage content cannot be accepted via any hint.
        temp_root = Path(tempfile.mkdtemp(prefix="urlbad-"))
        try:
            with self.assertRaises(u.DownloadError):
                self._download([b"\x00\x01\x02\x03\x04\x05"],
                               url="https://example.com/file.bin",
                               temp_root=temp_root)
            self.assertEqual([p.name for p in temp_root.iterdir()], [])
        finally:
            import shutil
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_download_empty_file_cleans_temp(self):
        temp_root = Path(tempfile.mkdtemp(prefix="urlempty-"))
        try:
            with self.assertRaises(u.DownloadError):
                self._download([b""], temp_root=temp_root)
            self.assertEqual([p.name for p in temp_root.iterdir()], [])
        finally:
            import shutil
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_download_cancellation(self):
        cancel = threading.Event()
        data = b"cancellable" * 1000
        response = FakeResponse([data[:100], data[100:]])
        with stub_dns(), patch.object(u, "build_opener",
                                      lambda *handlers: FakeOpener(response)):
            cancel.set()  # cancel immediately
            with self.assertRaises(u.DownloadCancelled):
                u.download_url(self.DOWNLOAD_URL, cancel=cancel)

    def test_download_http_error(self):
        with stub_dns():
            def boom(*handlers):
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


# ── CLI progress reporting ────────────────────────────────────────────

class CliProgressTests(unittest.TestCase):
    """The CLI progress renderer must work and must actually be exercised."""

    def test_cli_progress_formats_sizes(self):
        from contextlib import redirect_stderr
        buf = io.StringIO()
        info = {"bytes_downloaded": 1024, "total_size": 3 * 1024,
                "percent": 100.0 / 3.0, "bytes_per_second": 2048.0}
        with redirect_stderr(buf):
            u._cli_progress(info)
        out = buf.getvalue()
        self.assertIn("1 KiB", out)
        self.assertIn("of 3 KiB", out)
        self.assertIn("(33%)", out)
        self.assertIn("2 KiB/s", out)

    def test_cli_progress_no_total(self):
        from contextlib import redirect_stderr
        buf = io.StringIO()
        info = {"bytes_downloaded": 500, "total_size": None,
                "percent": None, "bytes_per_second": 100.0}
        with redirect_stderr(buf):
            u._cli_progress(info)
        out = buf.getvalue()
        self.assertIn("500 B", out)
        self.assertNotIn("of", out)
        self.assertNotIn("%", out)

    def _make_result(self):
        tmp = Path(tempfile.mkdtemp(prefix="urlcliprog-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        data = b"\x7fELF" + b"\x00" * 4 + b"AI" + b"\x00" * 40
        f = tmp / "file.AppImage"
        f.write_bytes(data)
        return u.DownloadResult(f, "file.AppImage", len(data),
                                hashlib.sha256(data).hexdigest(),
                                "application/octet-stream", "appimage",
                                "https://example.com/file.AppImage")

    def test_run_cli_reports_progress_lines(self):
        """run_cli actually renders CLI progress (regression: NameError on
        ``url_install.human_size`` inside _cli_progress)."""
        from contextlib import redirect_stderr
        result = self._make_result()
        progress_calls = []

        def fake_download(url, expected_checksum=None, cancel=None,
                          progress=None, **kwargs):
            for index in (1, 2, 3):
                info = {"bytes_downloaded": index * 1024,
                        "total_size": 3 * 1024,
                        "percent": index * 100.0 / 3.0,
                        "bytes_per_second": 2048.0}
                progress(info)
                progress_calls.append(info)
            return result

        with patch.object(u, "download_url", fake_download), \
             patch.object(u, "_locate_sibling",
                          lambda name: Path("/nonexistent/" + name)), \
             redirect_stderr(io.StringIO()) as stderr:
            rc = u.run_cli(["--install-url", "https://example.com/file.AppImage",
                            "--yes"])
        self.assertEqual(rc, 2)  # appinstall stub missing -> cannot install
        self.assertEqual(len(progress_calls), 3)
        self.assertIn("KiB", stderr.getvalue())  # progress rendered


# ── CLI confirmation flow ─────────────────────────────────────────────

CONFIRM_STUB = """\
import os, sys
log = os.environ.get("STUB_CONFIRM_LOG")
if log:
    with open(log, "a") as fh:
        fh.write("confirm " + " ".join(sys.argv[1:4]) + "\\n")
sys.exit(int(os.environ.get("STUB_CONFIRM_RC", "0")))
"""

INSTALL_STUB = """\
#!/usr/bin/env python3
import os, sys
log = os.environ.get("STUB_INSTALL_LOG")
if log:
    with open(log, "a") as fh:
        fh.write("install " + " ".join(sys.argv[1:]) + "\\n")
sys.exit(int(os.environ.get("STUB_INSTALL_RC", "0")))
"""


class CliConfirmationTests(unittest.TestCase):
    """run_cli must never install without explicit user approval.

    confirm.py exit codes: 0 approved, 1 cancelled, 3 review window could not
    open, other = failure. The CLI falls back to an explicit terminal prompt
    on 3 only, and stops when no interactive terminal is attached.
    """

    def setUp(self):
        import shutil
        self.dir = Path(tempfile.mkdtemp(prefix="urlcli-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.confirm_log = self.dir / "confirm-log"
        self.install_log = self.dir / "install-log"
        (self.dir / "confirm.py").write_text(CONFIRM_STUB)
        install_stub = self.dir / "appinstall"
        install_stub.write_text(INSTALL_STUB)
        install_stub.chmod(0o755)
        self.result = self._make_result()

    def _make_result(self):
        # The fake download lives in its own subdirectory: run_cli removes
        # result.path.parent after the backend consumed the file, and that
        # must not take away the stubs or logs under test.
        payload = self.dir / "payload"
        payload.mkdir(exist_ok=True)
        data = b"\x7fELF" + b"\x00" * 4 + b"AI" + b"\x00" * 40
        f = payload / "file.AppImage"
        f.write_bytes(data)
        return u.DownloadResult(f, "file.AppImage", len(data),
                                hashlib.sha256(data).hexdigest(),
                                "application/octet-stream", "appimage",
                                "https://example.com/file.AppImage")

    def _run(self, argv, confirm_rc=None, stdin=None, terminal_says=None):
        from contextlib import ExitStack

        def fake_download(url, expected_checksum=None, cancel=None,
                          progress=None, **kwargs):
            return self.result

        env = {"STUB_CONFIRM_LOG": str(self.confirm_log),
               "STUB_INSTALL_LOG": str(self.install_log)}
        if confirm_rc is not None:
            env["STUB_CONFIRM_RC"] = str(confirm_rc)
        with ExitStack() as stack:
            stack.enter_context(patch.object(u, "download_url", fake_download))
            stack.enter_context(patch.object(u, "_locate_sibling",
                                             lambda name: self.dir / name))
            stack.enter_context(patch.dict("os.environ", env))
            if stdin is not None:
                stack.enter_context(patch.object(u.sys, "stdin", stdin))
            if terminal_says is not None:
                stack.enter_context(patch.object(u, "_terminal_confirm",
                                                 lambda prompt: terminal_says))
            return u.run_cli(argv)

    def test_confirm_approved_installs(self):
        rc = self._run(["--install-url", "https://example.com/f"], confirm_rc=0)
        self.assertEqual(rc, 0)
        self.assertIn("install --yes", self.install_log.read_text())
        self.assertIn("confirm", self.confirm_log.read_text())

    def test_confirm_cancelled_stops_before_install(self):
        rc = self._run(["--install-url", "https://example.com/f"], confirm_rc=1)
        self.assertEqual(rc, 1)
        self.assertFalse(self.install_log.exists())

    def test_confirm_unavailable_without_terminal_stops(self):
        # Exit code 3 with no interactive terminal: installation must stop.
        rc = self._run(["--install-url", "https://example.com/f"],
                       confirm_rc=3, stdin=io.StringIO())
        self.assertEqual(rc, 1)
        self.assertFalse(self.install_log.exists())

    def test_confirm_unavailable_terminal_approval_required(self):
        # Exit code 3 with a terminal: the fallback prompt decides.
        rc = self._run(["--install-url", "https://example.com/f"],
                       confirm_rc=3, stdin=io.StringIO(), terminal_says=True)
        self.assertEqual(rc, 0)
        self.assertIn("install --yes", self.install_log.read_text())

    def test_confirm_unavailable_terminal_declined_stops(self):
        rc = self._run(["--install-url", "https://example.com/f"],
                       confirm_rc=3, stdin=io.StringIO(), terminal_says=False)
        self.assertEqual(rc, 1)
        self.assertFalse(self.install_log.exists())

    def test_confirm_error_stops(self):
        rc = self._run(["--install-url", "https://example.com/f"], confirm_rc=2)
        self.assertEqual(rc, 1)
        self.assertFalse(self.install_log.exists())

    def test_yes_skips_confirmation_but_still_installs_via_backend(self):
        rc = self._run(["--install-url", "https://example.com/f", "--yes"])
        self.assertEqual(rc, 0)
        self.assertFalse(self.confirm_log.exists())  # confirm never invoked
        self.assertIn("install --yes", self.install_log.read_text())

    def test_terminal_confirm_requires_tty(self):
        with patch.object(u.sys, "stdin", io.StringIO()):
            self.assertFalse(u._terminal_confirm("Install? [y/N]: "))

    def test_terminal_confirm_answers(self):
        class FakeTTY:
            def __init__(self, data):
                self._data = data

            def isatty(self):
                return True

        with patch.object(u.sys, "stdin", FakeTTY("unused")), \
             patch("builtins.input", lambda prompt="": "y"):
            self.assertTrue(u._terminal_confirm("Install? [y/N]: "))
        with patch.object(u.sys, "stdin", FakeTTY("unused")), \
             patch("builtins.input", lambda prompt="": "n"):
            self.assertFalse(u._terminal_confirm("Install? [y/N]: "))
        with patch.object(u.sys, "stdin", FakeTTY("unused")), \
             patch("builtins.input", lambda prompt="": ""):
            self.assertFalse(u._terminal_confirm("Install? [y/N]: "))

    def test_download_failure_returns_1(self):
        def failing_download(url, **kwargs):
            raise u.DownloadError("Could not connect")

        with patch.object(u, "download_url", failing_download):
            rc = u.run_cli(["--install-url", "https://example.com/f"])
        self.assertEqual(rc, 1)

    def test_cancelled_download_returns_130(self):
        def cancelled_download(url, **kwargs):
            raise u.DownloadCancelled()

        with patch.object(u, "download_url", cancelled_download):
            rc = u.run_cli(["--install-url", "https://example.com/f"])
        self.assertEqual(rc, 130)


# ── Bash entry point flag dispatch ────────────────────────────────────

class BashDispatchTests(unittest.TestCase):
    """appinstall --install-url must honor the flags documented with it.

    Usage documents ``appinstall --install-url URL [--yes]``, so flags AFTER
    the URL must still reach install_url (regression: the dispatch used to
    exit at --install-url, silently dropping trailing --yes/--nolaunch and
    falling back to a graphical confirmation).
    """

    HELPER_STUB = """\
#!/usr/bin/python3
import os, sys
log = os.environ["DISPATCH_LOG"]
with open(log, "a") as fh:
    fh.write(repr(sys.argv[2:]) + "\\n")
sys.exit(0)
"""

    def setUp(self):
        import shutil
        self.dir = Path(tempfile.mkdtemp(prefix="urldispatch-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.log = self.dir / "dispatch.log"
        # installed layout: the real appinstall script + the real helper file
        # (its presence satisfies install_url's check; execution is shimmed)
        bindir = self.dir / "bin"
        bindir.mkdir()
        shutil.copy(ROOT / "appinstall", bindir / "appinstall")
        (bindir / "appinstall").chmod(0o755)
        shutil.copy(ROOT / "url_install.py", bindir / "url_install.py")
        self.bindir = bindir
        # shims: python3 records argv and exits 0; dialog tools fail fast so
        # a headless run can never open a GUI (error_dialog falls through).
        shims = self.dir / "shims"
        shims.mkdir()
        python3 = shims / "python3"
        python3.write_text(self.HELPER_STUB)
        python3.chmod(0o755)
        for tool in ("kdialog", "zenity", "notify-send"):
            tool_stub = shims / tool
            tool_stub.write_text("#!/bin/sh\nexit 1\n")
            tool_stub.chmod(0o755)
        self.shims = shims

    def _run(self, argv):
        env = dict(os.environ)
        env["PATH"] = str(self.shims) + os.pathsep + env["PATH"]
        env["HOME"] = str(self.dir / "home")
        (self.dir / "home").mkdir()
        env["DISPATCH_LOG"] = str(self.log)
        # never touch a real display session from a test
        for key in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR"):
            env.pop(key, None)
        proc = subprocess.run(["bash", str(self.bindir / "appinstall")] + argv,
                              env=env, capture_output=True, text=True, timeout=60)
        return proc.returncode, proc.stdout, proc.stderr

    def _recorded(self):
        if not self.log.exists():
            return None
        import ast
        return [ast.literal_eval(line) for line in
                self.log.read_text().splitlines()]

    def test_documented_trailing_flags_reach_helper(self):
        rc, out, err = self._run(["--install-url", "https://example.test/app.AppImage",
                                  "--yes", "--nolaunch"])
        self.assertEqual(rc, 0, err)
        recorded = self._recorded()
        self.assertIsNotNone(recorded, "install_url must invoke the helper")
        self.assertEqual(recorded[0],
                         ["--install-url", "https://example.test/app.AppImage", "--yes"])

    def test_flags_before_url_still_reach_helper(self):
        rc, out, err = self._run(["--yes", "--nolaunch",
                                  "--install-url", "https://example.test/app.AppImage"])
        self.assertEqual(rc, 0, err)
        recorded = self._recorded()
        self.assertEqual(recorded[0],
                         ["--install-url", "https://example.test/app.AppImage", "--yes"])

    def test_without_yes_helper_gets_no_yes(self):
        rc, out, err = self._run(["--install-url", "https://example.test/app.AppImage"])
        self.assertEqual(rc, 0, err)
        recorded = self._recorded()
        self.assertEqual(recorded[0],
                         ["--install-url", "https://example.test/app.AppImage"])


if __name__ == "__main__":
    unittest.main()
