"""Realistic DNS-rebinding and destination-validation integration tests.

Unlike tests/test_url_install.py (which stubs the HTTP response object), these
tests run a REAL local HTTPS server (http.server + ssl, self-signed
certificate generated with openssl) and drive the actual urllib client in
url_install.py end to end:

* the TCP connection, TLS handshake (SNI + certificate verification against
  the real hostname) and the full HTTP transfer all happen for real;
* DNS answers are stubbed, which is exactly the attacker's control point in a
  DNS-rebinding attack, and each scenario proves what the client does with a
  hostile answer before and while connecting.

No external network is used: sockets are redirected to the local test server
by a test-only NAT shim, and the server records every request it receives.
"""

from __future__ import annotations

import os
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

import url_install as u

PUBLIC_IP = "93.184.216.34"   # public, allowed address used as the DNS answer
LOOPBACK = "127.0.0.1"
METADATA_IP = "169.254.169.254"
TEST_HOST = "rebind.test"

APPIMAGE_PAYLOAD = b"\x7fELF" + b"\x00" * 4 + b"AI" + b"\x00" * 40


def openssl_available():
    return shutil.which("openssl") is not None


def generate_certificate(directory, common_name=TEST_HOST):
    """Self-signed certificate with subjectAltName DNS:<common_name>."""
    cert = Path(directory) / "cert.pem"
    key = Path(directory) / "key.pem"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", str(key), "-out", str(cert), "-days", "1",
         "-subj", "/CN=" + common_name,
         "-addext", "subjectAltName=DNS:" + common_name],
        check=True, capture_output=True)
    return cert, key


class _Handler(BaseHTTPRequestHandler):
    """Records requests; serves the payload; supports a 302 hop."""

    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep test output clean
        pass

    def do_GET(self):
        server = self.server
        server.requests.append(self.path)
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", server.redirect_target)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = server.payload
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _TLSServer:
    """Real HTTPS server on loopback with a self-signed certificate."""

    def __init__(self, cert_file, key_file, payload=APPIMAGE_PAYLOAD):
        self.payload = payload
        self.requests = []
        self.redirect_target = None
        self.httpd = ThreadingHTTPServer((LOOPBACK, 0), _Handler)
        self.httpd.payload = self.payload
        self.httpd.requests = self.requests
        self.httpd.redirect_target = self.redirect_target
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def url(self, path="/app.AppImage"):
        return "https://" + TEST_HOST + ":" + str(self.port) + path


class _NatShim:
    """Test-only NAT for socket.create_connection.

    Records every address the client dials and forwards the TCP connection to
    the local test server. In production the client dials the address it
    resolved itself; the shim keeps that observable without external network.
    """

    def __init__(self, server_port):
        self.server_port = server_port
        self.dialed = []
        # Capture the real connect before any test patching happens.
        self._real_create_connection = socket.create_connection

    def __call__(self, address, timeout=None, source_address=None):
        host, port = address
        self.dialed.append((host, port))
        return self._real_create_connection((LOOPBACK, self.server_port),
                                            timeout, source_address)


def _dns_answer(address):
    """Stub getaddrinfo: names resolve to ``address``, IP literals pass through.

    The returned sockaddr must carry the port the caller asked for —
    ``socket.create_connection`` calls ``getaddrinfo(host, port)`` and connects
    to the sockaddr it gets back. IP literals never touch DNS in reality, so a
    literal host (e.g. the loopback address the NAT shim dials) keeps its own
    meaning even while names are hijacked.
    """
    import ipaddress

    def fake(host, port=None, *args, **kwargs):
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None
        resolved = host if ip is not None else address
        family = (socket.AF_INET6 if ip is not None and ip.version == 6
                  else socket.AF_INET)
        return [(family, socket.SOCK_STREAM, 6, "",
                 (resolved, port if port is not None else 0))]

    return fake


@unittest.skipUnless(openssl_available(), "openssl CLI is required for certificates")
class RealServerDownloadTests(unittest.TestCase):
    """End-to-end downloads against a real HTTPS server."""

    def setUp(self):
        # Keep any accidental external dial from stalling the test run.
        timeout_patcher = patch.object(u, "CONNECT_TIMEOUT", 5.0)
        timeout_patcher.start()
        self.addCleanup(timeout_patcher.stop)
        self.dir = Path(tempfile.mkdtemp(prefix="urlrebind-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        cert, key = generate_certificate(self.dir)
        self.server = _TLSServer(cert, key)
        self.server.start()
        self.addCleanup(self.server.stop)
        # Client trust store pinned to the test CA: hostname verification
        # (rebind.test) and certificate-chain checks stay fully active.
        self.client_context = ssl.create_default_context(cafile=str(cert))

    def _download(self, url, **kwargs):
        shim = _NatShim(self.server.port)
        with patch.object(socket, "getaddrinfo", _dns_answer(PUBLIC_IP)), \
             patch.object(socket, "create_connection", shim):
            result = u.download_url(url, ssl_context=self.client_context, **kwargs)
        return result, shim

    def test_download_over_real_tls_uses_validated_address(self):
        """Happy path: real TLS handshake, hostname verified, download done.

        Also proves connection pinning: the socket is dialed at the validated
        public address (the DNS answer), never at any other destination.
        """
        result, shim = self._download(self.server.url())
        self.assertEqual(result.detected_format, "appimage")
        self.assertEqual(result.path.read_bytes(), APPIMAGE_PAYLOAD)
        self.assertEqual(result.sha256,
                         __import__("hashlib").sha256(APPIMAGE_PAYLOAD).hexdigest())
        # Every dial went to the validated public address.
        self.assertEqual(shim.dialed, [(PUBLIC_IP, self.server.port)])
        # The request really reached the server (over TLS).
        self.assertEqual(self.server.requests, ["/app.AppImage"])

    def test_untrusted_certificate_is_rejected(self):
        """TLS verification is never disabled by destination pinning.

        The default context does not trust the test CA, so the handshake must
        fail and no request may be processed.
        """
        with patch.object(socket, "getaddrinfo", _dns_answer(PUBLIC_IP)), \
             patch.object(socket, "create_connection", _NatShim(self.server.port)):
            with self.assertRaises(u.DownloadError) as ctx:
                u.download_url(self.server.url())
        self.assertIn("TLS certificate verification failed", str(ctx.exception))
        self.assertEqual(self.server.requests, [])

    def test_ambient_proxy_settings_are_ignored(self):
        """http_proxy/https_proxy must not bypass destination validation."""
        env = {"https_proxy": "http://10.255.255.1:9999",
               "HTTPS_PROXY": "http://10.255.255.1:9999",
               "http_proxy": "http://10.255.255.1:9999",
               "HTTP_PROXY": "http://10.255.255.1:9999",
               "all_proxy": "socks5://10.255.255.1:9999"}
        with patch.dict(os.environ, env):
            result, shim = self._download(self.server.url())
        self.assertEqual(result.path.read_bytes(), APPIMAGE_PAYLOAD)
        self.assertEqual(shim.dialed, [(PUBLIC_IP, self.server.port)])
        self.assertEqual(self.server.requests, ["/app.AppImage"])

    def test_explicit_port_in_url_is_supported(self):
        """URLs with an explicit port must resolve the bare hostname."""
        result, shim = self._download(self.server.url())  # url() includes :port
        self.assertEqual(shim.dialed, [(PUBLIC_IP, self.server.port)])
        self.assertEqual(self.server.requests, ["/app.AppImage"])


@unittest.skipUnless(openssl_available(), "openssl CLI is required for certificates")
class DnsRebindingIntegrationTests(unittest.TestCase):
    """The client must refuse destinations that DNS points at unsafely.

    In each scenario the attacker controls DNS (stubbed getaddrinfo) and a
    real HTTPS service waits on loopback — the "internal service" the attack
    tries to reach. The client must send it no HTTP request at all.
    """

    def setUp(self):
        timeout_patcher = patch.object(u, "CONNECT_TIMEOUT", 5.0)
        timeout_patcher.start()
        self.addCleanup(timeout_patcher.stop)
        self.dir = Path(tempfile.mkdtemp(prefix="urlrebind2-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        cert, key = generate_certificate(self.dir)
        self.server = _TLSServer(cert, key)
        self.server.start()
        self.addCleanup(self.server.stop)
        self.client_context = ssl.create_default_context(cafile=str(cert))

    def test_dns_resolving_to_loopback_is_refused_before_connect(self):
        """DNS says 127.0.0.1: refused, and the local service sees nothing."""
        with patch.object(socket, "getaddrinfo", _dns_answer(LOOPBACK)):
            with self.assertRaises(u.DownloadError):
                u.download_url(self.server.url(), ssl_context=self.client_context)
        self.assertEqual(self.server.requests, [])

    def test_dns_answer_changing_between_validation_and_connection(self):
        """The core rebinding regression: DNS is public during URL validation
        and private at connection time. The connection-time check must win.
        """
        calls = []

        def flaky_dns(host, port=None, *args, **kwargs):
            calls.append(host)
            address = PUBLIC_IP if len(calls) == 1 else LOOPBACK
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]

        with patch.object(socket, "getaddrinfo", flaky_dns):
            with self.assertRaises(u.DownloadError) as ctx:
                u.download_url(self.server.url(), ssl_context=self.client_context)
        self.assertIn("local or private network", str(ctx.exception))
        # The public answer satisfied validate_url, but the connection-time
        # validation caught the switch and no request reached the service.
        self.assertEqual(self.server.requests, [])

    def test_dns_answer_changing_to_metadata_ip(self):
        """Rebinding to the cloud-metadata endpoint is refused at connect."""
        calls = []

        def flaky_dns(host, port=None, *args, **kwargs):
            calls.append(host)
            address = PUBLIC_IP if len(calls) == 1 else METADATA_IP
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]

        with patch.object(socket, "getaddrinfo", flaky_dns):
            with self.assertRaises(u.DownloadError):
                u.download_url(self.server.url(), ssl_context=self.client_context)
        self.assertEqual(self.server.requests, [])

    def test_dns_failure_fails_closed(self):
        """If resolution fails at connect time, nothing is connected."""
        with patch.object(socket, "getaddrinfo",
                          side_effect=socket.gaierror("NXDOMAIN")):
            with self.assertRaises(u.DownloadError):
                u.download_url(self.server.url(), ssl_context=self.client_context)
        self.assertEqual(self.server.requests, [])


@unittest.skipUnless(openssl_available(), "openssl CLI is required for certificates")
class RedirectDestinationTests(unittest.TestCase):
    """Redirects must pass the same destination policy as the original URL."""

    def setUp(self):
        timeout_patcher = patch.object(u, "CONNECT_TIMEOUT", 5.0)
        timeout_patcher.start()
        self.addCleanup(timeout_patcher.stop)
        self.dir = Path(tempfile.mkdtemp(prefix="urlredir-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        cert, key = generate_certificate(self.dir)
        self.server = _TLSServer(cert, key)
        self.server.start()
        self.addCleanup(self.server.stop)
        self.client_context = ssl.create_default_context(cafile=str(cert))

    def _open(self, path):
        with patch.object(socket, "getaddrinfo", _dns_answer(PUBLIC_IP)), \
             patch.object(socket, "create_connection",
                          _NatShim(self.server.port)):
            return u.download_url(self.server.url(path),
                                  ssl_context=self.client_context)

    def test_redirect_to_metadata_ip_is_refused(self):
        self.server.redirect_target = "https://" + METADATA_IP + "/latest/meta-data/"
        self.server.httpd.redirect_target = self.server.redirect_target
        with self.assertRaises(u.DownloadError):
            self._open("/redirect")
        # Only the first hop happened; the redirect was never followed.
        self.assertEqual(self.server.requests, ["/redirect"])

    def test_safe_self_redirect_is_followed(self):
        """A redirect to another validated HTTPS destination is followed."""
        self.server.redirect_target = ("https://" + TEST_HOST + ":" +
                                       str(self.server.port) + "/app.AppImage")
        self.server.httpd.redirect_target = self.server.redirect_target
        result = self._open("/redirect")
        self.assertEqual(result.path.read_bytes(), APPIMAGE_PAYLOAD)
        self.assertEqual(self.server.requests, ["/redirect", "/app.AppImage"])

    def test_redirect_to_private_lan_address_is_refused(self):
        self.server.redirect_target = "https://10.0.0.1/evil"
        self.server.httpd.redirect_target = self.server.redirect_target
        with self.assertRaises(u.DownloadError):
            self._open("/redirect")
        self.assertEqual(self.server.requests, ["/redirect"])

    def test_redirect_to_plain_http_is_refused(self):
        self.server.redirect_target = "http://" + TEST_HOST + ":80/app.AppImage"
        self.server.httpd.redirect_target = self.server.redirect_target
        with self.assertRaises(u.DownloadError):
            self._open("/redirect")
        self.assertEqual(self.server.requests, ["/redirect"])


if __name__ == "__main__":
    unittest.main()
