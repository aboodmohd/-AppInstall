"""Read-only searches of AppInstall-owned Debian/Fedora repository indexes.

Package records come from APT/DNF within the user's rootless Distrobox
containers, never from guessed download URLs or a hand-written app list.
No container is created merely by browsing. First-time preparation requires
an explicit confirmation in the UI, and all install operations have their
own transaction-review step in container_ui.Workflow.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import urllib.parse

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
    if not isinstance(query, str) or not SEARCH_RE.fullmatch(query.strip()):
        raise ValueError("Enter at least two letters or numbers to search packages.")
    query = query.strip()
    if kind == "deb":
        # APT accepts regexes; escape user input before passing as argv.
        output = _run(kind, ["apt-cache", "search", "--names-only", re.escape(query)])
    else:
        # The glob is a single argv element, never passed through a shell.
        output = _run(kind, [
            "dnf", "repoquery", "--available", "--latest-limit=1",
            "--queryformat=%{name}\\t%{summary}\\t%{version}\\t%{arch}",
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
                           "--queryformat=%{name}\\t%{version}-%{release}\\t%{arch}\\t%{summary}",
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
