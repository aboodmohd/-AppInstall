"""Source-qualified, read-only application metadata for Discover (v1.8).

AppStream IDs are NOT package names. Only copy AppStream component data from
the *same* Debian/Fedora container when its <pkgname> exactly identifies the
requested package. Missing tools/catalogs simply leave original package rows.
No package installation, repository refresh, or guessed cross-distro artwork.
"""
from dataclasses import dataclass, asdict
import re
import urllib.parse
import xml.etree.ElementTree as ET

import repository_catalog

SOURCES = frozenset(("Flatpak", "AppImage", "DEB", "RPM"))
COMPONENT_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{2,180}\Z")
IDENTIFIER = re.compile(r"(?im)^\s*Identifier:\s*([A-Za-z0-9_.-]{3,180})\b")
MAX_XML_BYTES = 1024 * 1024
MAX_REPO_LOOKUPS = 8
MAX_COMPONENTS = 3
FIELDS = ("name", "summary", "developer", "version", "license", "homepage",
          "category", "componentId", "iconUrl", "providerKey")


def text(value, limit=200):
    if not isinstance(value, str):
        return ""
    return "".join(c for c in value if c.isprintable()).strip()[:limit]


def qualified_id(source, app_id):
    """Catalog identity cannot be shared across different package formats."""
    if source not in SOURCES or not isinstance(app_id, str):
        raise ValueError("Unknown source or missing application ID")
    key = app_id.strip()
    if not key or len(key) > 200 or any(c in key for c in "/\\\0\r\n"):
        raise ValueError("Invalid source-qualified application ID")
    if source in ("DEB", "RPM"):
        repository_catalog.validate_name(key)
    return source.lower() + ":" + key


@dataclass(frozen=True)
class AppMetadata:
    provider_key: str
    source: str
    app_id: str
    name: str
    summary: str = ""
    developer: str = ""
    version: str = ""
    license: str = ""
    homepage: str = ""
    category: str = ""
    component_id: str = ""
    icon_url: str = ""

    def to_dict(self):
        return asdict(self)


def normalize(row):
    """Normalize provider fields without converting package identity."""
    if not isinstance(row, dict):
        raise ValueError("Metadata row must be a dictionary.")
    source = row.get("source", "Flatpak")
    app_id = row.get("appId", "")
    key = qualified_id(source, app_id)
    homepage = text(row.get("homepage"), 900)
    if homepage:
        parts = urllib.parse.urlsplit(homepage)
        if (parts.scheme != "https" or not parts.hostname
                or parts.username or parts.password or parts.fragment
                or len(homepage) > 900):
            homepage = ""
    return {
        **row,
        "providerKey": key,
        "name": text(row.get("name"), 140) or app_id,
        "summary": text(row.get("summary"), 300),
        "developer": text(row.get("developer"), 140),
        "version": text(row.get("version"), 100),
        "license": text(row.get("license"), 120),
        "homepage": homepage,
        "category": text(row.get("category"), 70),
        "componentId": text(row.get("componentId"), 180),
        "iconUrl": text(row.get("iconUrl"), 1100),
        "source": source,
        "appId": app_id,
    }


def normalize_rows(rows):
    result = []
    seen = set()
    for row in rows[:240]:
        try:
            item = normalize(row)
        except (ValueError, TypeError):
            continue
        if item["providerKey"] not in seen:
            seen.add(item["providerKey"])
            result.append(item)
    return result


def _tag(element):
    return element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""


def _children(component, tag):
    return [child for child in component if _tag(child) == tag]


def _one(component, tag):
    for element in _children(component, tag):
        if not element.attrib.get("{http://www.w3.org/XML/1998/namespace}lang"):
            return text(" ".join(element.itertext()), 350)
    return ""


def _site(value):
    if not value:
        return ""
    url = urllib.parse.urlsplit(value)
    if (url.scheme == "https" and url.hostname and not url.username
            and not url.password and not url.fragment and len(value) <= 850):
        return value
    return ""


def parse_appstream_xml(body, package_name, source):
    """Exact <pkgname> only; never fuzzy component->package attribution."""
    repository_catalog.validate_name(package_name)
    if source not in ("DEB", "RPM"):
        return {}
    if not isinstance(body, str) or not body or len(body.encode("utf-8")) > MAX_XML_BYTES:
        return {}
    if "<!DOCTYPE" in body.upper() or "<!ENTITY" in body.upper():
        return {}
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return {}
    components = ([root] if _tag(root) == "component"
                  else [c for c in root if _tag(c) == "component"])
    matched = []
    for component in components[:100]:
        packages = [text(node.text, 160) for node in _children(component, "pkgname")]
        if package_name not in packages:
            continue
        component_id = _one(component, "id")
        if not COMPONENT_ID.fullmatch(component_id):
            continue
        name = _one(component, "name")
        summary = _one(component, "summary")
        developer = _one(component, "developer_name")
        if not developer:
            for parent in _children(component, "developer"):
                developer = _one(parent, "name")
                if developer:
                    break
        category = ""
        for container in _children(component, "categories"):
            for item in _children(container, "category"):
                category = text(item.text, 70)
                if category:
                    break
        homepage = ""
        for node in _children(component, "url"):
            if node.attrib.get("type") == "homepage":
                homepage = _site(text(node.text, 850))
                break
        license_name = _one(component, "project_license")
        # AppStream cached/stock icons belong to the *container*, not to
        # the host. Only HTTPS remote artwork can be requested on the host.
        icon_url = ""
        for node in _children(component, "icon"):
            if node.attrib.get("type") == "remote":
                icon_url = text(node.text, 1100)
                break
        matched.append({
            "name": name, "summary": summary, "developer": developer,
            "category": category, "license": license_name,
            "homepage": homepage, "componentId": component_id,
            "iconUrl": icon_url,
        })
    # Multiple components can share a source package: do not guess a match.
    return matched[0] if len(matched) == 1 else {}


def _component_ids(search_text):
    found = []
    for match in IDENTIFIER.finditer(search_text[:16000]):
        value = match.group(1)
        if COMPONENT_ID.fullmatch(value) and value not in found:
            found.append(value)
            if len(found) >= MAX_COMPONENTS:
                break
    return found


def repo_enrichment(kind, rows):
    """Bounded metadata lookup inside an already-existing container.

    appstreamcli is optional, not installed/initialized here. An unavailable
    index/tool yields empty enhancements; package browser keeps working.
    """
    if kind not in ("deb", "rpm") or not rows:
        return {}
    output = {}
    candidates = []
    for row in rows:
        name = row.get("appId")
        if (repository_catalog._is_visual_package(name)
                and name not in candidates):
            candidates.append(name)
        if len(candidates) >= MAX_REPO_LOOKUPS:
            break
    for name in candidates:
        try:
            search = repository_catalog._run(
                kind, ["appstreamcli", "--no-color", "search", name],
                timeout=10)
        except (OSError, RuntimeError, ValueError):
            # Optional CLI may be missing in minimal Debian/Fedora images.
            break
        for component_id in _component_ids(search):
            try:
                xml = repository_catalog._run(
                    kind, ["appstreamcli", "--no-color", "dump", component_id],
                    timeout=10)
            except (OSError, RuntimeError, ValueError):
                continue
            match = parse_appstream_xml(xml, name, kind.upper())
            if match:
                output[name] = match
                break
    return output
