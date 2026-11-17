"""Safe, optional on-disk artwork cache for Discover cards.

Only official HTTPS provider images are fetched. Never download SVG, follow
redirects, run scripts or hand remote URLs directly to QML Image. Downloads
happen in a QThread after the initial cards have appeared; fall back to the
first letter when no trusted picture exists.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import os
from pathlib import Path
import stat
import struct
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from catalog_metadata import qualified_id

MAX_IMAGE_BYTES = 350 * 1024
MAX_PIXELS = 1024 * 1024
MAX_ICON_SIDE = 1024
MAX_CACHE_BYTES = 32 * 1024 * 1024
MAX_CACHE_FILES = 160
MAX_FETCHES = 16
CACHE_TTL = 7 * 24 * 3600
TIMEOUT = 6


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def trusted_url(source, url):
    """No mixed-origin icon mapping; source identity is always explicit."""
    if source not in ("Flatpak", "AppImage", "DEB", "RPM"):
        return False
    if not isinstance(url, str) or len(url) > 1300 or not url:
        return False
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or port not in (None, 443) or parsed.query or parsed.fragment):
        return False
    path = urllib.parse.unquote(parsed.path)
    segments = path.split("/")
    if (".." in segments or "." in segments or "\\" in path
            or any(ord(c) < 32 for c in path)
            or not path.lower().endswith((".png", ".webp"))):
        return False
    allowed = {
        "Flatpak": (("dl.flathub.org", "/media/"),),
        "AppImage": (("appimage.github.io", "/database/"),),
        "DEB": (("appstream.debian.org", "/media/pool/"),),
        # Fedora catalogs commonly provide cached/stock icons which are paths
        # *inside the container*. Do not borrow unrelated Debian artwork.
        "RPM": (("cdn.fedoraproject.org", "/pub/"),),
    }
    return any(parsed.hostname == host and path.startswith(prefix)
               for host, prefix in allowed[source])


def _format(data):
    """Restrict to small PNG/WebP bitmaps and bounded decoded dimensions."""
    if not isinstance(data, bytes) or len(data) > MAX_IMAGE_BYTES:
        return ""
    if (len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n"
            and data[12:16] == b"IHDR"):
        width, height = struct.unpack(">II", data[16:24])
        if (0 < width <= MAX_ICON_SIDE and 0 < height <= MAX_ICON_SIDE
                and width * height <= MAX_PIXELS):
            return "png"
    if (len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
            and struct.unpack("<I", data[4:8])[0] + 8 == len(data)):
        chunk = data[12:16]
        if chunk == b"VP8X" and len(data) >= 30:
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
        elif chunk == b"VP8 " and len(data) >= 30:
            width = int.from_bytes(data[26:28], "little") & 0x3fff
            height = int.from_bytes(data[28:30], "little") & 0x3fff
        elif chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2f:
            bit = int.from_bytes(data[21:25], "little")
            width = 1 + (bit & 0x3fff)
            height = 1 + ((bit >> 14) & 0x3fff)
        else:
            return ""
        if (0 < width <= MAX_ICON_SIDE and 0 < height <= MAX_ICON_SIDE
                and width * height <= MAX_PIXELS):
            return "webp"
    return ""


def cache_dir():
    path = Path(os.environ.get("XDG_CACHE_HOME") or
                (Path.home() / ".cache")) / "appinstall" / "catalog-artwork"
    # An existing symlink is not an AppInstall-owned cache directory.
    for ancestor in (path.parent, path):
        if ancestor.is_symlink():
            raise OSError("Unsafe artwork cache link")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_uid != os.getuid():
        raise OSError("Artwork cache is not user-owned")
    return path


def _load(path):
    if not path.is_file() or path.is_symlink():
        return False
    try:
        if path.stat().st_uid != os.getuid() or path.stat().st_size > MAX_IMAGE_BYTES:
            return False
        return bool(_format(path.read_bytes()))
    except OSError:
        return False


def _prune(base):
    """Keep at most 160 user-owned regular files and 32 MiB."""
    try:
        files = sorted((p for p in base.iterdir() if p.is_file()
                        and not p.is_symlink() and p.suffix in (".png", ".webp")
                        and p.stat().st_uid == os.getuid()),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return
    bytes_used = 0
    for i, file in enumerate(files):
        try:
            size = file.stat().st_size
            bytes_used += size
            if i >= MAX_CACHE_FILES or bytes_used > MAX_CACHE_BYTES:
                file.unlink(missing_ok=True)
        except OSError:
            continue


def _download(url, *, opener=None):
    request = urllib.request.Request(
        url, headers={"Accept": "image/png,image/webp",
                      "User-Agent": "AppInstall/1.8 artwork"})
    if opener is None:
        opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(request, timeout=TIMEOUT) as response:
        if response.geturl() != url:
            return b""
        content_type = (response.headers.get("Content-Type", "")
                        .split(";", 1)[0].strip().lower())
        if content_type not in ("image/png", "image/webp"):
            return b""
        data = response.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        return b""
    suffix = _format(data)
    if suffix != content_type.removeprefix("image/"):
        return b""
    # Qt validates the full data stream before it can appear in QML.
    try:
        from qt_compat import QtCore, QtGui
        buffer = QtCore.QBuffer()
        buffer.setData(QtCore.QByteArray(data))
        if not buffer.open(QtCore.QIODevice.OpenModeFlag.ReadOnly):
            return b""
        reader = QtGui.QImageReader(buffer)
        reader.setAutoDetectImageFormat(True)
        if not reader.canRead():
            return b""
        size = reader.size()
        if not size.isValid() or size.width() > MAX_ICON_SIDE or size.height() > MAX_ICON_SIDE:
            return b""
        image = reader.read()
        if image.isNull():
            return b""
    except (ImportError, RuntimeError, AttributeError):
        return b""
    return data


def get(source, app_id, url, *, now=None, opener=None):
    """Return a local file:// URI only for successfully validated images."""
    if not trusted_url(source, url):
        return ""
    try:
        key = qualified_id(source, app_id)
        base = cache_dir()
    except (OSError, ValueError):
        return ""
    digest = hashlib.sha256((key + "\0" + url).encode("utf-8")).hexdigest()
    suffix = "." + url.split("?", 1)[0].rsplit(".", 1)[-1].lower()
    target = base / (digest + suffix)
    now = time.time() if now is None else now
    if _load(target) and now - target.stat().st_mtime < CACHE_TTL:
        return target.as_uri()
    try:
        data = _download(url, opener=opener)
    except (OSError, urllib.error.URLError, ValueError):
        data = b""
    if not data:
        return target.as_uri() if _load(target) else ""
    pending = None
    try:
        with tempfile.NamedTemporaryFile(
                prefix=".artwork-", dir=base, delete=False) as out:
            pending = Path(out.name)
            os.chmod(out.name, 0o600)
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        if target.is_symlink():
            return ""
        os.replace(pending, target)
        pending = None
        _prune(base)
        return target.as_uri()
    except OSError:
        return target.as_uri() if _load(target) else ""
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)


def cache_results(rows, limit=MAX_FETCHES):
    """Concurrent best-effort fetch, bounded and safe for worker thread use."""
    targets = []
    seen = set()
    limit = min(MAX_FETCHES, max(0, int(limit)))
    if not limit:
        return {}
    for row in rows:
        source, app_id, url = row.get("source", "Flatpak"), row.get("appId"), row.get("iconUrl")
        if (isinstance(app_id, str) and app_id not in seen
                and trusted_url(source, url)):
            seen.add(app_id)
            targets.append((source, app_id, url))
        if len(targets) >= limit:
            break
    icons = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(get, *item): item[1] for item in targets}
        for future in as_completed(futures):
            try:
                path = future.result()
                if path:
                    icons[futures[future]] = path
            except Exception:
                pass
    return icons
