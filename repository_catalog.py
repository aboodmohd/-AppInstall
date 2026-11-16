"""Read-only searches of AppInstall-owned Debian/Fedora repository indexes.

Package records come from APT/DNF within the user's rootless Distrobox
containers, never from guessed download URLs or a hand-written app list.
No container is created merely by browsing. First-time preparation requires
an explicit confirmation in the UI, and all install operations have their
own transaction-review step in container_ui.Workflow.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from html.parser import HTMLParser
import json
import os
import platform
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

import container_backend as backend

SEARCH_LIMIT = 240
PACKAGE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+_.-]{0,127}\Z")
SEARCH_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _+.-]{1,79}\Z")


class CatalogNotReady(RuntimeError):
    """The user has not prepared this AppInstall-managed package repository."""


def kind_for(source):
    try:
        return {"DEB": "deb", "RPM": "rpm"}[source]
    except KeyError as error:
        raise ValueError("Unknown repository format.") from error


def validate_name(name):
    if not isinstance(name, str) or not PACKAGE_RE.fullmatch(name):
        raise ValueError("Invalid repository package name.")
    return name


def _identity(kind):
    if kind not in backend.SPECS:
        raise ValueError("Unsupported repository format.")
    container, image = backend.SPECS[kind]
    return {"kind": kind, "container": container, "image": image}


def ready(kind):
    """Only query a previously owned container; never create or pull it."""
    info = _identity(kind)
    ownership = backend.state_dir() / (info["container"] + ".json")
    if not ownership.is_file() or not shutil.which("podman") or not shutil.which("distrobox"):
        return False
    try:
        if json.loads(ownership.read_text()).get("image") != info["image"]:
            return False
        result = subprocess.run(["podman", "container", "exists", info["container"]],
                                env=backend.ENV, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=10)
        return result.returncode == 0
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def _run(kind, args, timeout=65):
    info = _identity(kind)
    if not ready(kind):
        raise CatalogNotReady(
            "Prepare the " + ("Debian" if kind == "deb" else "Fedora")
            + " repository to enable searchable results.")
    argv = ["distrobox", "enter", "--name", info["container"],
            "--no-tty", "--", *args]
    try:
        result = subprocess.run(argv, env=backend.ENV, capture_output=True,
                                text=True, errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("Repository query failed: " + str(error)) from error
    if result.returncode:
        raise RuntimeError("Repository query failed: " + (result.stdout + result.stderr)[-2000:])
    if len(result.stdout) > 4 * 1024 * 1024:
        raise RuntimeError("Repository returned too much metadata.")
    return result.stdout


def prepare(kind):
    """Explicitly authorized setup; package index refresh runs in a worker."""
    info = _identity(kind)
    engine = backend.Engine()
    try:
        engine.ensure(info)  # Rootless ownership and repository validation.
        if kind == "deb":
            engine.enter(info, ["sudo", "apt-get", "update"])
        else:
            engine.enter(info, ["sudo", "dnf", "makecache", "--refresh"])
    finally:
        engine.close()
    if not ready(kind):
        raise RuntimeError("Container setup did not complete.")


def _rows(kind, content):
    """Normalize package manager output; never interpret text as shell input."""
    results, seen = [], set()
    for line in content.splitlines():
        if kind == "deb":
            if " - " not in line:
                continue
            name, summary = line.split(" - ", 1)
            version, arch = "", ""
        else:
            cols = line.split("\t")
            if len(cols) != 4:
                continue
            name, summary, version, arch = cols
            if arch not in ("x86_64", "aarch64", "noarch"):
                continue
        if not PACKAGE_RE.fullmatch(name) or name in seen:
            continue
        seen.add(name)
        source = "DEB" if kind == "deb" else "RPM"
        results.append({
            "appId": name, "name": name,
            "summary": " ".join(summary.split())[:300],
            "iconUrl": "", "category": "Debian 13" if kind == "deb" else "Fedora 44",
            "source": source, "installUrl": "", "version": version,
            "sourceUrl": ("https://packages.debian.org/trixie/" + urllib.parse.quote(name)
                          if kind == "deb" else
                          "https://packages.fedoraproject.org/pkgs/" + urllib.parse.quote(name) + "/"),
        })
        if len(results) >= SEARCH_LIMIT:
            break
    return results


def search(kind, query):
    _identity(kind)
    if not ready(kind):
        raise CatalogNotReady("Repository not yet prepared. Select Enable repository.")
    if (not isinstance(query, str) or "\n" in query or "\r" in query
            or not SEARCH_RE.fullmatch(query.strip())):
        raise ValueError("Enter at least two letters or numbers to search packages.")
    query = query.strip()
    if kind == "deb":
        # APT accepts regexes; escape user input before passing as argv.
        output = _run(kind, ["apt-cache", "search", "--names-only", re.escape(query)])
    else:
        # The glob is a single argv element, never passed through a shell.
        output = _run(kind, [
            "dnf", "repoquery", "--available", "--latest-limit=1",
            "--queryformat=%{name}\t%{summary}\t%{version}\t%{arch}",
            "*" + query + "*"])
    return _rows(kind, output)


def package_info(kind, name):
    """Re-query the exact package from the same repository as the transaction."""
    info = _identity(kind)
    validate_name(name)
    arch = platform.machine()
    allowed = {"x86_64": {"amd64", "all", "x86_64", "noarch"},
               "aarch64": {"arm64", "all", "aarch64", "noarch"}}.get(arch, set())
    if not allowed:
        raise RuntimeError("Unsupported host architecture.")
    if kind == "deb":
        text = _run(kind, ["apt-cache", "show", "--no-all-versions", name])
        fields, last = {}, None
        for line in text.splitlines():
            if not line.strip() and fields:
                break
            if line[:1].isspace() and last:
                fields[last] += " " + line.strip()
            elif ": " in line:
                last, value = line.split(": ", 1)
                fields[last] = value
        if fields.get("Package") != name or not fields.get("Version"):
            raise RuntimeError("The Debian package is not available.")
        version = fields["Version"]
        pkg_arch = fields.get("Architecture", "unknown")
        summary = fields.get("Description", "")
        deps = fields.get("Depends", "")
        maintainer = fields.get("Maintainer", "")
    else:
        text = _run(kind, ["dnf", "repoquery", "--available", "--latest-limit=1",
                           "--queryformat=%{name}\t%{version}-%{release}\t%{arch}\t%{summary}",
                           name])
        matches = [parts for line in text.splitlines()
                   if len(parts := line.split("\t", 3)) == 4
                   and parts[0] == name and parts[2] in allowed]
        if not matches:
            raise RuntimeError("The Fedora package is not available.")
        _, version, pkg_arch, summary = matches[0]
        deps, maintainer = "", ""
    if pkg_arch not in allowed:
        raise RuntimeError("This package has an incompatible architecture: " + pkg_arch)
    return {
        **info, "name": name, "application_name": name, "version": version,
        "architecture": pkg_arch, "description": summary[:300],
        "dependencies": deps[:500], "maintainer": maintainer[:160],
        "icon": "", "icon_name": "package-x-generic",
        "source": "Debian 13 repositories" if kind == "deb" else "Fedora 44 repositories",
        "install_method": "repository",
    }


# AppStream artwork is optional metadata only. Search/install must never rely on
# a logo being available. Debian's generated package pages contain matching
# component icons; many development/library/CLI packages have no AppStream icon.
APPSTREAM_BASE = "https://appstream.debian.org"
ICON_LOOKUP_LIMIT = 12
ICON_REQUEST_TIMEOUT = 3
MAX_METADATA_BYTES = 1024 * 1024
_NO_ICON_PARTS = ("-dev", "-dbg", "-dbgsym", "-doc", "-docs", "-data",
                  "-common", "-help", "-l10n", "-locale", "-lang", "-i18n",
                  "-translations", "-headers", "-test", "-tests")
_NO_ICON_PREFIXES = ("lib", "gir1.", "python3-", "perl-", "ruby-", "fonts-",
                     "golang-", "node-", "texlive-", "firmware-", "kernel-")


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected AppStream redirect")


def _is_visual_package(name):
    """Heuristic for *artwork lookups*, not a claim that a package is a GUI."""
    if not isinstance(name, str) or not PACKAGE_RE.fullmatch(name):
        return False
    if name.lower().startswith(_NO_ICON_PREFIXES) and not name.lower().startswith("libreoffice"):
        return False
    parts = ("-" + name.lower() + "-")
    return not any(piece in parts for piece in (
        "-data-", "-dev-", "-dbg-", "-dbgsym-", "-doc-", "-docs-",
        "-common-", "-help-", "-locale-", "-l10n-", "-lang-",
        "-i18n-", "-translations-", "-headers-", "-tests-",
        "-test-", "-devel-", "-static-"
    ))


def _trusted_icon_url(src):
    if not isinstance(src, str) or len(src) > 850 or not src:
        return ""
    url = urllib.parse.urljoin(APPSTREAM_BASE + "/", src)
    parts = urllib.parse.urlsplit(url)
    # Never display arbitrary links embedded in untrusted HTML.
    if (parts.scheme != "https" or parts.netloc != "appstream.debian.org"
            or parts.username or parts.password or parts.query or parts.fragment):
        return ""
    pieces = parts.path.split("/")
    if (".." in pieces or "." in pieces
            or not parts.path.startswith("/media/pool/")
            or "/icons/" not in parts.path
            or not parts.path.lower().endswith(".png")):
        return ""
    return url


class _AppStreamIconHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.icons = []

    def handle_starttag(self, tag, attrs):
        if tag != "img":
            return
        data = dict(attrs)
        url = _trusted_icon_url(data.get("src"))
        if url:
            self.icons.append(url)


@lru_cache(maxsize=768)
def _debian_appstream_icon(name):
    """Official Debian AppStream metadata for an *exact* package name.

    Fail closed and silently keep the letter if the metadata/icon is missing.
    No response can redirect to a different host or exceed the size cap.
    """
    if not _is_visual_package(name):
        return ""
    url = APPSTREAM_BASE + "/trixie/main/metainfo/" + urllib.parse.quote(name, safe="") + ".html"
    request = urllib.request.Request(
        url, headers={"Accept": "text/html", "User-Agent": "AppInstall/1.7 Discover icons"})
    try:
        opener = urllib.request.build_opener(_NoRedirects)
        with opener.open(request, timeout=ICON_REQUEST_TIMEOUT) as response:
            if response.geturl() != url:
                return ""
            data = response.read(MAX_METADATA_BYTES + 1)
        if len(data) > MAX_METADATA_BYTES:
            return ""
        parser = _AppStreamIconHTML()
        parser.feed(data.decode("utf-8"))
    except (OSError, ValueError, UnicodeError, urllib.error.URLError):
        return ""
    # 128x128 first if the service supplies it; PNG reliably works in Qt.
    return sorted(parser.icons, key=lambda x: ("128x128" not in x, "64x64" not in x))[0] if parser.icons else ""


def icons_for_results(rows):
    """Read-only best-effort artwork enrichment, bounded and off the GUI thread.

    Fedora entries use an icon only when the same named upstream application
    has a Debian AppStream icon; we do not assume package format equivalence.
    """
    candidates = []
    for row in rows:
        name = row.get("appId", "")
        if _is_visual_package(name) and name not in candidates:
            candidates.append(name)
        if len(candidates) == ICON_LOOKUP_LIMIT:
            break
    if not candidates:
        return {}
    icons = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        tasks = {executor.submit(_debian_appstream_icon, name): name
                 for name in candidates}
        for future in as_completed(tasks):
            try:
                url = future.result()
                if url:
                    icons[tasks[future]] = url
            except Exception:
                pass
    return icons
