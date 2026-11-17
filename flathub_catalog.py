"""Read-only Flathub application discovery for the AppInstall QML store.

Search and featured lists are fetched from Flathub's public API, not from a
hand-maintained list. API responses are untrusted, size-limited JSON. Only
validated Flatpak application IDs may become install links, and the only
install destination is Flathub's canonical HTTPS .flatpakref URL.

This module NEVER starts a package manager, modifies a repository, executes
downloaded metadata, or installs anything. The existing UrlInstallDialog owns
download, review, confirmation, and installation.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import json
import re
import urllib.error
import urllib.parse
import urllib.request


API = "https://flathub.org/api/v2"
FEATURED_URL = API + "/collection/popular"
SEARCH_URL = API + "/search"
MAX_SEARCH_RESULTS = 240
MAX_DETAILS = 16
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT = 8
APP_ID_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+){2,}")


class CatalogError(RuntimeError):
    """A network, format, or trust-boundary failure in app discovery."""


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CatalogError("Flathub API redirected unexpectedly; search cancelled.")


def valid_app_id(value):
    """Conservative reverse-DNS application id; no paths, URLs or shell input."""
    return isinstance(value, str) and len(value) <= 200 and bool(APP_ID_RE.fullmatch(value))


def flathub_ref_url(app_id):
    """Canonical Flathub ref; only used after an explicit user install action."""
    if not valid_app_id(app_id):
        raise ValueError("Invalid Flathub application ID.")
    return "https://dl.flathub.org/repo/appstream/" + app_id + ".flatpakref"


def _json_request(url, payload=None):
    """One bounded request to a fixed Flathub API endpoint, with no redirects."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.netloc != "flathub.org" or not parts.path.startswith("/api/v2/"):
        raise CatalogError("Only Flathub's HTTPS API is accepted.")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise CatalogError("Flathub API URL contains unsupported components.")
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url, data=data,
        headers={"Accept": "application/json", "User-Agent": "AppInstall/1.7 Discover",
                 **({"Content-Type": "application/json"} if data is not None else {})},
        method="POST" if data is not None else "GET",
    )
    opener = urllib.request.build_opener(_RejectRedirects)
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT) as response:
            if response.geturl() != url:
                raise CatalogError("Flathub API response changed destination.")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        raise CatalogError("Could not connect to Flathub: " + str(error)) from error
    if len(raw) > MAX_RESPONSE_BYTES:
        raise CatalogError("Flathub API returned an oversized response.")
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise CatalogError("Flathub API returned invalid JSON.") from error


def _clean_text(value, limit=240):
    if not isinstance(value, str):
        return ""
    return "".join(c for c in value if c.isprintable()).strip()[:limit]


def _icon_url(value):
    if isinstance(value, dict):
        value = value.get("url") or value.get("src")
    if not isinstance(value, str):
        return ""
    parts = urllib.parse.urlsplit(value)
    if (parts.scheme == "https" and parts.netloc == "dl.flathub.org"
            and parts.path.startswith("/media/") and not parts.query
            and not parts.fragment and parts.path.lower().endswith((".png", ".webp", ".svg"))):
        return value
    return ""


def _row_id(row):
    if isinstance(row, str):
        return row
    if isinstance(row, dict):
        if isinstance(row.get("app"), dict):
            row = row["app"]
        return row.get("app_id") or row.get("id") or ""
    return ""


def _base_entries(body):
    if isinstance(body, list):
        hits = body
    elif isinstance(body, dict):
        hits = next((body[key] for key in ("hits", "apps", "results", "items")
                     if isinstance(body.get(key), list)), [])
    else:
        raise CatalogError("Flathub returned an unsupported catalog response.")
    seen = set()
    entries = []
    for hit in hits:
        app_id = _row_id(hit)
        if not valid_app_id(app_id) or app_id in seen:
            continue
        seen.add(app_id)
        row = hit.get("app", hit) if isinstance(hit, dict) else {}
        if not isinstance(row, dict):
            row = {}
        entries.append({
            "appId": app_id,
            "name": _clean_text(row.get("name"), 140) or app_id.split(".")[-1],
            "summary": _clean_text(row.get("summary"), 300),
            "iconUrl": _icon_url(row.get("icon") or row.get("icon_url")),
            "category": "",
            "developer": "", "license": "", "homepage": "", "version": "",
            "componentId": app_id,
        })
        if len(entries) >= MAX_SEARCH_RESULTS:
            break
    return entries


def _enrich(row):
    """Fetch official AppStream name, category, and real Flathub-hosted icon."""
    app_id = row["appId"]
    try:
        detail = _json_request(API + "/appstream/" + urllib.parse.quote(app_id, safe=""))
    except CatalogError:
        return row  # Search entries still work if details temporarily fail.
    if not isinstance(detail, dict):
        return row
    if detail.get("is_eol") is True:
        return None
    icon = _icon_url(detail.get("icon"))
    if not icon and isinstance(detail.get("icons"), list):
        for item in detail["icons"]:
            icon = _icon_url(item)
            if icon:
                break
    categories = detail.get("categories")
    cat = next((_clean_text(x, 55) for x in categories if isinstance(x, str)),
               "") if isinstance(categories, list) else ""
    developer = detail.get("developer_name") or detail.get("developer")
    if isinstance(developer, dict):
        developer = developer.get("name")
    urls = detail.get("urls")
    homepage = (urls.get("homepage") if isinstance(urls, dict)
                else detail.get("homepage"))
    return {
        **row,
        "name": _clean_text(detail.get("name"), 140) or row["name"],
        "summary": _clean_text(detail.get("summary"), 300) or row["summary"],
        "iconUrl": icon or row["iconUrl"],
        "category": cat,
        "developer": _clean_text(developer, 140),
        "license": _clean_text(
            detail.get("project_license") or detail.get("license"), 120),
        "homepage": _clean_text(homepage, 850),
        "version": _clean_text(detail.get("version"), 100),
        "componentId": app_id,
    }


def _discover(body):
    base = _base_entries(body)
    if not base:
        return []
    # Bound requests and parallelism. Never block the GUI; callers use a QThread.
    first = base[:MAX_DETAILS]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_enrich, row): i for i, row in enumerate(first)}
        for future in as_completed(futures):
            index = futures[future]
            try:
                first[index] = future.result()
            except Exception:  # One malformed metadata item must not hide other apps.
                pass
    return [row for row in first if row is not None] + base[MAX_DETAILS:]


def search(query):
    query = _clean_text(query, 90)
    if len(query) < 2:
        raise ValueError("Search requires at least two characters.")
    return _discover(_json_request(SEARCH_URL, {"query": query, "filters": []}))


def popular():
    """Dynamic Flathub collection, not a baked-in product list."""
    return _discover(_json_request(FEATURED_URL))


# ── Independent AppImageHub discovery (never treated as a Flathub install) ──
# AppImageHub's feed is community-maintained and contains many release-page
# links rather than direct AppImage artifacts. Never invent a download link.
APPIMAGE_FEED = "https://appimage.github.io/feed.json"
MAX_APPIMAGE_FEED_BYTES = 16 * 1024 * 1024


@lru_cache(maxsize=1)
def _appimage_feed():
    """Fetch bounded JSON once per session; do not run AppImages or scripts."""
    request = urllib.request.Request(
        APPIMAGE_FEED, headers={"Accept": "application/json",
                                "User-Agent": "AppInstall/1.7 Discover"})
    opener = urllib.request.build_opener(_RejectRedirects)
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT) as response:
            if response.geturl() != APPIMAGE_FEED:
                raise CatalogError("AppImageHub redirected unexpectedly.")
            body = response.read(MAX_APPIMAGE_FEED_BYTES + 1)
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        raise CatalogError("Could not reach AppImageHub: " + str(error)) from error
    if len(body) > MAX_APPIMAGE_FEED_BYTES:
        raise CatalogError("AppImageHub feed is too large.")
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise CatalogError("AppImageHub returned invalid JSON.") from error
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise CatalogError("AppImageHub returned an unsupported feed.")
    return data["items"]


def _appimage_icon(item):
    icons = item.get("icons", [])
    if not isinstance(icons, list):
        return ""
    for icon in icons:
        if not isinstance(icon, str) or len(icon) > 260 or not icon:
            continue
        if (icon.startswith("/") or "\\\\" in icon or "?" in icon or "#" in icon
                or any(piece in ("", ".", "..") for piece in icon.split("/"))
                or not icon.lower().endswith((".png", ".webp", ".svg"))):
            continue
        return "https://appimage.github.io/database/" + urllib.parse.quote(icon, safe="/")
    return ""


def _appimage_download(item):
    """Only direct HTTPS AppImage artifact URLs can enter review/install."""
    links = item.get("links", [])
    if not isinstance(links, list):
        return ""
    for link in links:
        if not isinstance(link, dict) or link.get("type") != "Download":
            continue
        url = link.get("url")
        if not isinstance(url, str) or len(url) > 1600:
            continue
        parts = urllib.parse.urlsplit(url)
        if (parts.scheme == "https"
                and parts.hostname in ("github.com", "gitlab.com", "codeberg.org")
                and not parts.username and not parts.password
                and not parts.query and not parts.fragment
                and parts.path.lower().endswith(".appimage")):
            return url
    return ""


def _appimage_rows(query=""):
    """Return actual AppImageHub results; browsing is not popularity ranked."""
    term = _clean_text(query, 90).casefold()
    rows = []
    seen = set()
    for item in _appimage_feed():
        if not isinstance(item, dict):
            continue
        raw_name = item.get("name")
        if not isinstance(raw_name, str) or not raw_name or len(raw_name) > 120:
            continue
        if any(c in raw_name for c in ("/", "\\\\", "?", "#")):
            continue
        name = _clean_text(raw_name, 120)
        if not name or name in seen:
            continue
        summary = _clean_text(item.get("description"), 300)
        if term and term not in name.casefold() and term not in summary.casefold():
            continue
        seen.add(name)
        categories = item.get("categories", [])
        category = (_clean_text(categories[0], 55) if isinstance(categories, list)
                    and categories and isinstance(categories[0], str) else "")
        author = item.get("authors")
        if isinstance(author, list):
            author = next((x for x in author if isinstance(x, str)), "")
        elif not isinstance(author, str):
            author = ""
        rows.append({
            "appId": name, "name": name.replace("_", " "),
            "summary": summary, "iconUrl": _appimage_icon(item),
            "category": category, "source": "AppImage",
            "developer": _clean_text(author, 140),
            "license": _clean_text(item.get("license"), 120),
            "version": _clean_text(item.get("version"), 100),
            "componentId": "",
            "sourceUrl": "https://appimage.github.io/apps/"
                         + urllib.parse.quote(name, safe=""),
            "installUrl": _appimage_download(item),
        })
        if len(rows) >= MAX_SEARCH_RESULTS:
            break
    return rows


def appimage_search(query):
    query = _clean_text(query, 90)
    if len(query) < 2:
        raise ValueError("Search requires at least two characters.")
    return _appimage_rows(query)


def appimage_browse():
    return _appimage_rows()
