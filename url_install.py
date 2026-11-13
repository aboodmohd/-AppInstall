#!/usr/bin/env python3
"""Secure HTTPS download, validation and format detection for AppInstall "Install from URL".

This module is intentionally dependency-free (Python standard library only). It is
used by both the graphical URL installer (``url_dialog.py``) and the
``appinstall --install-url`` CLI, so GUI and command-line installs share exactly
one download, validation, and detection implementation.

Security model
--------------
Transport: HTTPS only, with certificate verification via Python's default SSL
context (the system trust store). TLS verification is never disabled.

Destination safety: the destination of every connection is validated at
connection time. Before any socket is opened, the target hostname is resolved
and every returned address is checked against localhost, loopback, private
(RFC 1918 / RFC 4193), link-local, multicast and reserved ranges; if any
address is unsafe the download is refused, and if resolution is impossible the
download fails closed. The HTTP client then opens TCP sockets only to those
pre-validated addresses (connection pinning), so a DNS answer that changes
between validation and connection cannot steer the request to an internal
target (DNS rebinding), and TLS keeps verifying the original hostname (SNI and
certificate checks are unaffected by pinning). Ambient proxy settings are
ignored so a proxy cannot bypass destination validation. Every HTTP redirect
destination is re-validated with the same policy, and redirects are capped,
which additionally mitigates server-side-request-forgery (SSRF) via redirects.

Downloads: streamed to a private temporary directory (mode 0700, file mode 0600)
with a sanitized filename. Size is enforced even when the server omits or lies
about Content-Length. A SHA-256 digest is computed as the data arrives. The
download can be cancelled at any time, which closes the response and removes the
partial file.

Integrity: the digest is reported, never treated as proof of trust. An expected
checksum supplied by the caller is compared, but a checksum from the same
untrusted source as the download is never automatically trusted.
"""

from __future__ import annotations

import functools
import hashlib
import ipaddress
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from http.client import HTTPSConnection
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import (HTTPHandler, HTTPRedirectHandler, HTTPSHandler,
                            ProxyHandler, Request, build_opener)

# Default limits. Callers may tighten max_size.
MAX_DOWNLOAD_SIZE = 2 * 1024 * 1024 * 1024  # 2 GiB
CONNECT_TIMEOUT = 30.0  # socket timeout, applied to connect and read operations
MAX_REDIRECTS = 10
CHUNK = 65536  # bytes read per network read
HEAD_LIMIT = 65536  # bytes sampled for format detection
TEMP_DIR_MODE = 0o700
TEMP_FILE_MODE = 0o600

USER_AGENT = "AppInstall/1.1 (+https://github.com/aboodmohd/-AppInstall)"


class DownloadError(Exception):
    """Base class for download failures."""


class SecurityError(DownloadError):
    """The URL or a redirect target violates the network-safety policy."""


class DownloadCancelled(DownloadError):
    """The user cancelled the download."""


class DownloadSizeExceeded(DownloadError):
    """The download exceeded the configured maximum size."""


class ChecksumMismatch(DownloadError):
    """The computed SHA-256 did not match the caller-supplied expected digest."""


class DownloadResult:
    """Outcome of a successful download."""

    def __init__(self, path, filename, size, sha256, content_type, detected_format, final_url,
                 checksum_verified=None):
        self.path = Path(path)
        self.filename = filename
        self.size = size
        self.sha256 = sha256
        self.content_type = content_type
        self.detected_format = detected_format
        self.final_url = final_url
        # True if an expected checksum was supplied and matched, False if
        # supplied but mismatched (mismatch raises before here), None if no
        # expected checksum was provided.
        self.checksum_verified = checksum_verified

    def __repr__(self):  # pragma: no cover - debugging aid
        return ("DownloadResult(filename=%r, size=%d, format=%r)"
                % (self.filename, self.size, self.detected_format))


def _is_blocked_address(host):
    """Return True if an IP address string must not be contacted."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    if (ip.is_loopback or ip.is_private or ip.is_link_local or
            ip.is_multicast or ip.is_reserved):
        return True
    # IPv4-mapped IPv6 loopback, e.g. ::ffff:127.0.0.1.
    if ip.version == 6 and ip.ipv4_mapped is not None:
        return _is_blocked_address(str(ip.ipv4_mapped))
    return False


def _resolve_public_addresses(hostname):
    """Resolve ``hostname`` and return the addresses the client may contact.

    This is the single source of truth for connection destinations. Every
    returned address is public: loopback, private, link-local, multicast and
    reserved addresses are rejected (including IPv4-mapped IPv6 forms, e.g.
    ::ffff:127.0.0.1, and cloud metadata endpoints such as 169.254.169.254).

    The call fails closed: if resolution fails or returns nothing, or if ANY
    returned address is unsafe, a DownloadError is raised. Refusing hosts with
    mixed public and unsafe answers is the DNS-rebinding mitigation — a name
    that alternates between a public and a private address is never contacted.
    """
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError) as error:
        raise DownloadError(
            "Could not resolve " + hostname + ": " + str(error))
    allowed = []
    blocked = []
    for _family, _socktype, _proto, _canonname, sockaddr in infos:
        addr = sockaddr[0]
        if _is_blocked_address(addr):
            if addr not in blocked:
                blocked.append(addr)
        elif addr not in allowed:
            allowed.append(addr)
    if blocked:
        raise DownloadError(
            "Refusing to connect to " + hostname +
            ": local or private network addresses are not allowed ("
            + ", ".join(blocked) + ").")
    if not allowed:
        raise DownloadError("Could not resolve " + hostname + " to any address.")
    return tuple(allowed)


def validate_url(url):
    """Validate and return a parsed HTTPS URL, or raise DownloadError.

    Rejects non-HTTPS schemes, missing hosts, embedded credentials and hosts
    that resolve to any local/private address. The DNS lookup here is a fast
    pre-check; the authoritative validation happens again at connection time
    (see _resolve_public_addresses and _PinnedHTTPSConnection).
    """
    try:
        parsed = urlparse(url)
    except ValueError as error:
        raise DownloadError("Invalid URL: " + str(error))
    if not parsed.scheme:
        raise DownloadError("URL must include a scheme (use https://).")
    if parsed.scheme.lower() != "https":
        raise DownloadError(
            "Only HTTPS downloads are supported (" + parsed.scheme + " is not allowed).")
    if not parsed.hostname:
        raise DownloadError("URL has no host.")
    if parsed.username or parsed.password:
        raise DownloadError("URLs must not contain embedded credentials.")
    _resolve_public_addresses(parsed.hostname)
    return parsed


class _SafeRedirectHandler(HTTPRedirectHandler):
    """Follow redirects only to destinations that pass validate_url."""

    def __init__(self):
        super().__init__()
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > MAX_REDIRECTS:
            raise DownloadError("Too many redirects (maximum " + str(MAX_REDIRECTS) + ").")
        # Re-validate every redirect destination (scheme, credentials, private IP).
        validate_url(newurl)
        new_headers = dict(req.header_items())
        new_headers.pop("Host", None)
        return Request(newurl, headers=new_headers, method=req.get_method())


class _PinnedHTTPSConnection(HTTPSConnection):
    """HTTPS connection that only ever dials pre-validated addresses.

    The TCP socket is opened exclusively to one of ``allowed_addresses`` — an
    explicit, validated resolution of the target host performed at connection
    time. A DNS answer that changes between validation and connection therefore
    cannot steer the socket to a private or local address (DNS rebinding).

    TLS is left untouched: ``HTTPSConnection.connect()`` wraps the socket with
    ``server_hostname=self.host``, so SNI and certificate verification keep
    using the original hostname rather than the pinned IP.
    """

    def __init__(self, *args, allowed_addresses=(), **kwargs):
        super().__init__(*args, **kwargs)
        self._allowed_addresses = tuple(allowed_addresses)
        # http.client stores socket.create_connection in this instance
        # attribute and calls it from connect() precisely so that callers can
        # replace it. Our replacement refuses to dial anything but a
        # validated address, and fails closed when none is available.
        self._create_connection = self._create_validated_connection

    def _create_validated_connection(self, address, timeout=None,
                                     source_address=None):
        if not self._allowed_addresses:
            raise DownloadError(
                "No validated address available for " + str(self.host) + "; "
                "connection refused.")
        _host, port = address
        last_error = None
        for addr in self._allowed_addresses:
            try:
                # ``addr`` is an IP literal from our own resolution, so this
                # lookup cannot return a different address (no rebinding).
                return socket.create_connection((addr, port), timeout,
                                                source_address)
            except OSError as error:
                last_error = error
        raise DownloadError(
            "Could not connect to a validated address for " + str(self.host)
            + ": " + str(last_error))


class _HTTPSOnlyHTTPHandler(HTTPHandler):
    """Refuse plain HTTP at the handler level (defense in depth).

    validate_url already rejects http:// URLs, and every redirect destination
    is re-validated, but a handler-level block guarantees no request is ever
    dispatched over plain HTTP even if a future code path forgets to validate.
    """

    def http_open(self, req):
        raise DownloadError(
            "Only HTTPS downloads are supported (http is not allowed).")


class _ValidatedHTTPSHandler(HTTPSHandler):
    """HTTPS handler that validates and pins the destination of every request.

    ``https_open`` runs for the original request and for every redirect hop,
    so each connection is resolved, policy-checked and pinned at the moment
    it is made. If validation cannot be completed, the handler fails closed.
    """

    def https_open(self, req):
        # req.host may carry the port ("host:port"); resolve the bare hostname.
        hostname = urlparse(req.full_url).hostname
        if not hostname:
            raise DownloadError("Request has no destination host.")
        addresses = _resolve_public_addresses(hostname)
        return self.do_open(
            functools.partial(_PinnedHTTPSConnection, allowed_addresses=addresses),
            req, context=self._context)

    # https_request is inherited from HTTPSHandler.


def _suggest_filename(parsed, headers):
    """Choose a download filename from Content-Disposition, then the URL path."""
    disposition = headers.get("Content-Disposition") or headers.get("content-disposition")
    if disposition:
        match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition, re.I)
        if match:
            name = match.group(1).strip()
            if name:
                return name
    path = parsed.path or "/"
    name = Path(path).name
    if name and name not in (".", ".."):
        return name
    return "download"


def _sanitize_filename(name):
    """Return a safe, collision-resistant basename (no path components)."""
    base = Path(name).name
    base = base.strip().replace("\x00", "")
    if not base or base in (".", ".."):
        base = "download"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", base)
    safe = re.sub(r"-{2,}", "-", safe).strip("-")
    if not safe or safe in (".", ".."):
        safe = "download"
    if len(safe) > 120:
        stem, dot, ext = safe.rpartition(".")
        if dot and len(ext) <= 16:
            safe = stem[:100] + dot + ext
        else:
            safe = safe[:120]
    return safe


_EXTENSION_MAP = {
    "appimage": ".AppImage",
    "deb": ".deb",
    "rpm": ".rpm",
    "flatpak": ".flatpak",
    "flatpakref": ".flatpakref",
    "flatpakrepo": ".flatpakrepo",
}


def _add_extension(safe_name, detected_format):
    """Ensure the temp file carries the extension its detected format expects,
    so existing detection (extension + magic) keeps working."""
    ext = _EXTENSION_MAP.get(detected_format)
    if not ext:
        return safe_name
    stem, dot, existing = safe_name.rpartition(".")
    if dot and existing.lower() == ext.lstrip(".").lower():
        return safe_name
    return safe_name + ext


def _remove_tree(temp_dir):
    if temp_dir is None:
        return
    shutil.rmtree(temp_dir, ignore_errors=True)


def remove_download_dir(path):
    """Remove the per-download temporary directory containing ``path``.

    Public helper shared with url_dialog. ``path`` may be the downloaded
    file itself or the directory; only directories created by download_url
    (prefix ``appinstall-url-``) are ever removed, so a file that lives
    anywhere else — including directly in the system temporary root — can
    never trigger a broader deletion.
    """
    directory = Path(path)
    if directory.is_file():
        directory = directory.parent
    if directory.name.startswith("appinstall-url-"):
        _remove_tree(directory)


def download_url(url, expected_checksum=None, max_size=MAX_DOWNLOAD_SIZE,
                 cancel=None, progress=None, temp_root=None, ssl_context=None):
    """Stream-download ``url`` to a secure temporary file.

    ``cancel`` is a threading.Event; when set the transfer aborts and the partial
    file is removed. ``progress`` is called with a dict of
    {bytes_downloaded, total_size, percent, bytes_per_second} after each chunk.
    ``ssl_context`` optionally supplies the TLS context (e.g. a test trust
    store); the default context always verifies certificates and hostnames.
    The temporary directory is removed on every failure — unsupported or
    malformed files, rename errors, checksum mismatch, cancellation and any
    other post-download exception.
    Returns a DownloadResult or raises DownloadError.
    """
    parsed = validate_url(url)
    # ProxyHandler({}) disables ambient proxy settings (http_proxy/https_proxy
    # environment variables and system proxies): the connection must be pinned
    # to the validated destination, and a proxy would silently change it.
    # _ValidatedHTTPSHandler replaces the stock HTTPSHandler and pins every
    # connection (including redirects) to a validated public address.
    opener = build_opener(ProxyHandler({}), _HTTPSOnlyHTTPHandler(),
                          _SafeRedirectHandler(),
                          _ValidatedHTTPSHandler(context=ssl_context))
    request = Request(url, headers={"User-Agent": USER_AGENT})

    try:
        response = opener.open(request, timeout=CONNECT_TIMEOUT)
    except HTTPError as error:
        raise DownloadError("HTTP " + str(error.code) + " " + error.reason +
                            " for " + parsed.hostname)
    except DownloadError:
        raise
    except URLError as error:
        reason = getattr(error, "reason", error)
        if isinstance(reason, ssl.SSLError):
            raise DownloadError("TLS certificate verification failed for " +
                                parsed.hostname + ": " + str(reason))
        raise DownloadError("Could not connect to " + parsed.hostname + ": " + str(reason))
    except Exception as error:  # noqa: BLE001 - network failures are fatal here
        raise DownloadError("Could not connect to " + parsed.hostname + ": " + str(error))

    # Everything after the connection is cleanup-protected: any failure (web
    # page instead of a package, unsupported format, rename error, checksum
    # mismatch, cancellation, a crash) removes the temporary directory.
    temp_dir = None
    try:
        # Re-validate the final destination after any redirects.
        final_url = response.geturl()
        validate_url(final_url)

        filename = _sanitize_filename(_suggest_filename(parsed, response.headers))
        content_type = response.headers.get("Content-Type")

        total_header = response.headers.get("Content-Length")
        total_size = int(total_header) if total_header and total_header.isdigit() else None

        temp_dir = Path(tempfile.mkdtemp(prefix="appinstall-url-", dir=temp_root))
        temp_dir.chmod(TEMP_DIR_MODE)
        target = temp_dir / filename

        sha = hashlib.sha256()
        downloaded = 0
        start = time.monotonic()
        with open(target, "wb") as out:
            while True:
                if cancel is not None and cancel.is_set():
                    raise DownloadCancelled()
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                downloaded += len(chunk)
                if max_size is not None and downloaded > max_size:
                    raise DownloadSizeExceeded(downloaded, max_size)
                out.write(chunk)
                sha.update(chunk)
                if progress is not None:
                    elapsed = max(time.monotonic() - start, 1e-6)
                    percent = None
                    if total_size:
                        percent = min(100.0, downloaded * 100.0 / total_size)
                    progress({
                        "bytes_downloaded": downloaded,
                        "total_size": total_size,
                        "percent": percent,
                        "bytes_per_second": downloaded / elapsed,
                    })
        digest = sha.hexdigest()

        detected = detect_format(target, url_hint=url)
        final_name = _add_extension(filename, detected)
        final_path = temp_dir / final_name
        if final_path != target:
            os.rename(target, final_path)
        target = final_path

        if expected_checksum is not None:
            expected = str(expected_checksum).strip().lower()
            if digest.lower() != expected:
                raise ChecksumMismatch(digest, expected)

        return DownloadResult(target, final_name, downloaded, digest, content_type,
                              detected, final_url,
                              checksum_verified=(True if expected_checksum is not None else None))
    except BaseException:
        _remove_tree(temp_dir)
        raise
    finally:
        try:
            response.close()
        except Exception:
            pass


# The format detector lives in this same module so ``from . import detect_format``
# above resolves correctly; define it after download_url for readability.


def _read_head(path, limit=HEAD_LIMIT):
    with open(path, "rb") as handle:
        return handle.read(limit)


def _head_text(head):
    try:
        return head.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return head.decode("latin-1")
        except UnicodeDecodeError:
            return None


def _looks_like_html(text):
    stripped = text.lstrip()
    lowered = stripped.lower()
    return (lowered.startswith("<!doctype") or lowered.startswith("<html")
            or "<html" in stripped[:512].lower())


def _extension_hint(url):
    """Weak URL-extension hint, used only where magic bytes cannot decide.

    Only the Flatpak bundle format has no dependable signature, so only the
    ``.flatpak`` extension is trusted as a hint. Every other format must be
    identified by its file contents; an unknown file that merely carries an
    ``.AppImage``/``.deb``/``.rpm`` URL is rejected instead of being handed to
    the wrong installer (misleading-extension protection).
    """
    if not url:
        return None
    if url.lower().endswith(".flatpak"):
        return "flatpak"
    return None


def detect_format(path, url_hint=None):
    """Detect the package format of a downloaded file.

    Magic bytes take precedence; the URL extension is only a weak hint for
    formats without a reliable signature (notably Flatpak bundles). HTML pages
    and unrecognized files are rejected so a website URL is never mistaken for
    a package.
    """
    path = Path(path)
    head = _read_head(path)
    if not head:
        raise DownloadError("The downloaded file is empty.")
    # AppImage: ELF magic with the "AI" AppImage marker at offset 8.
    if head.startswith(b"\x7fELF") and len(head) >= 10 and head[8:10] == b"AI":
        return "appimage"
    # DEB archive magic.
    if head.startswith(b"!<arch>\n"):
        return "deb"
    # RPM magic.
    if len(head) >= 4 and head[:4] == b"\xed\xab\xee\xdb":
        return "rpm"
    # Flatpak reference / repository are INI-style text files.
    text = _head_text(head)
    if text is not None:
        upper = text.upper()
        if "[FLATPAK REF]" in upper or "[FLATPAK_REF]" in upper:
            return "flatpakref"
        if "[FLATPAK REPO]" in upper or "[FLATPAK_REPO]" in upper:
            return "flatpakrepo"
        # A web page is not a package.
        if _looks_like_html(text):
            raise DownloadError(
                "The URL returned a web page, not a downloadable package. "
                "Provide a direct link to the file (for example .../file.AppImage), "
                "not the release page itself.")
    # Weak extension hint for formats without a dependable magic (Flatpak bundle).
    hint = _extension_hint(url_hint)
    if hint:
        return hint
    raise DownloadError(
        "Could not identify the downloaded file as a supported package "
        "(AppImage, Flatpak, Flatpak reference/repository, DEB or RPM).")


def human_size(value):
    """Return a human-readable size string (mirrors package_meta.human_size)."""
    try:
        size = int(value)
    except (TypeError, ValueError):
        return ""
    step = 1024
    units = ("%d B", "%d KiB", "%.1f MiB", "%.2f GiB")
    index = 0
    size = float(size)
    while size >= step and index < len(units) - 1:
        size /= float(step)
        index += 1
    return units[index] % size


def _cli_progress(info):
    """Print compact terminal progress to stderr."""
    parts = [human_size(info["bytes_downloaded"])]
    if info["total_size"]:
        parts.append("of " + human_size(info["total_size"]))
    if info["percent"] is not None:
        parts.append("(" + f"{info['percent']:.0f}%" + ")")
    parts.append("@ " + human_size(int(info["bytes_per_second"])) + "/s")
    print("\r  " + " ".join(parts), end="", file=sys.stderr)


def _terminal_confirm(prompt):
    """Ask for explicit approval in the terminal. False means not approved.

    Used only as a fallback when the graphical package review cannot open
    (confirm.py exit code 3). If no interactive terminal is attached, the
    answer is "no": a download is never installed without explicit approval.
    """
    try:
        if not sys.stdin.isatty():
            return False
        answer = input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt, OSError):
        return False
    return answer in ("y", "yes")


def run_cli(argv):
    """Command-line ``appinstall --install-url`` implementation.

    Downloads, detects the format, confirms (unless --yes), installs through the
    existing backends and removes the temporary download. Returns a process exit
    code.
    """
    url = None
    expected_checksum = None
    assume_yes = False
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--install-url" and index + 1 < len(argv):
            url = argv[index + 1]
            index += 2
        elif arg == "--checksum" and index + 1 < len(argv):
            expected_checksum = argv[index + 1]
            index += 2
        elif arg == "--yes":
            assume_yes = True
            index += 1
        else:
            index += 1
    if not url:
        print("appinstall --install-url: a URL is required.", file=sys.stderr)
        return 2
    cancel = threading.Event()

    def on_progress(info):
        _cli_progress(info)

    try:
        result = download_url(url, expected_checksum=expected_checksum,
                              cancel=cancel, progress=on_progress)
    except DownloadCancelled:
        print("\nDownload cancelled.", file=sys.stderr)
        return 130
    except DownloadError as error:
        print("\nDownload failed: " + str(error), file=sys.stderr)
        return 1
    print("", file=sys.stderr)
    print("Downloaded: " + result.filename)
    print("Format: " + result.detected_format)
    print("Size: " + human_size(result.size))
    print("SHA-256: " + result.sha256)

    kind = result.detected_format
    if not assume_yes and kind in ("appimage", "flatpak", "flatpakref", "flatpakrepo"):
        checksum_note = ""
        if result.checksum_verified is True:
            checksum_note = "\nSHA-256 verified against expected checksum: yes"
        elif result.checksum_verified is False:
            checksum_note = "\nSHA-256 verified against expected checksum: no (mismatch)"
        elif result.checksum_verified is None:
            checksum_note = "\nSHA-256 verified against expected checksum: not provided"
        details = ("Source: " + result.final_url + "\n"
                   "Format: " + kind + "\n"
                   "Size: " + human_size(result.size) + "\n"
                   "SHA-256: " + result.sha256 + checksum_note + "\n"
                   "Downloaded file: " + str(result.path))
        ui = _locate_sibling("confirm.py")
        if not ui:
            print("confirm.py is missing; cannot review package.", file=sys.stderr)
            remove_download_dir(result.path)
            return 2
        try:
            rc = subprocess.run([sys.executable, str(ui), str(result.path), kind, details],
                                capture_output=True, text=True)
        except Exception as error:  # noqa: BLE001
            print("Could not open package review: " + str(error), file=sys.stderr)
            remove_download_dir(result.path)
            return 2
        if rc.returncode == 0:
            pass  # approved in the graphical review
        elif rc.returncode == 1:
            print("Installation cancelled.", file=sys.stderr)
            remove_download_dir(result.path)
            return 1
        elif rc.returncode == 3:
            # The graphical review could not open (usually PySide6 missing).
            # Never install without explicit approval: fall back to a terminal
            # confirmation, or stop when no interactive terminal is available.
            prompt = ("Install " + result.filename + " (" + kind + ")? [y/N]: ")
            if not _terminal_confirm(prompt):
                print("The package review could not open and installation was "
                      "cancelled. Install PySide6 or PyQt6 for the graphical review, or "
                      "answer the terminal prompt.",
                      file=sys.stderr)
                remove_download_dir(result.path)
                return 1
        else:
            print("Package review did not complete (exit code "
                  + str(rc.returncode) + ").", file=sys.stderr)
            remove_download_dir(result.path)
            return 1

    appinstall = _locate_sibling("appinstall")
    if not appinstall:
        print("appinstall entry point is missing.", file=sys.stderr)
        remove_download_dir(result.path)
        return 2
    try:
        rc = subprocess.run([str(appinstall), "--yes", str(result.path)],
                            capture_output=True, text=True)
    except Exception as error:  # noqa: BLE001
        print("Installation could not start: " + str(error), file=sys.stderr)
        remove_download_dir(result.path)
        return 2
    remove_download_dir(result.path)
    if rc.returncode == 0:
        print("Installation completed successfully.")
        return 0
    print("Installation finished with an error (exit code " + str(rc.returncode) + ").",
          file=sys.stderr)
    return rc.returncode


def _locate_sibling(name):
    here = Path(__file__).resolve().parent
    candidate = here / name
    if candidate.is_file():
        return candidate
    deployed = Path("/usr/bin") / name
    if deployed.is_file():
        return deployed
    return None


def main(argv=None):
    """Standalone CLI entry point for ``url_install.py --install-url <URL>``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    rc = run_cli(argv)
    sys.exit(rc)


if __name__ == "__main__":
    main()

