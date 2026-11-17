#!/usr/bin/env python3
"""Review-initiated self-updates for AppInstall *portable user installations*.

Works without a host package manager. Downloads ONLY the latest published
stable source archive and SHA256SUMS from the official GitHub release.
SourceTransaction in integration.py owns recoverable publication. The release
checksum is an integrity check, NOT a maintainer signature.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request

REPO = "aboodmohd/-AppInstall"
API_URL = "https://api.github.com/repos/" + REPO + "/releases/latest"
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
MAX_JSON = 1024 * 1024
MAX_ARCHIVE = 100 * 1024 * 1024
MAX_UNPACKED = 180 * 1024 * 1024
MAX_MEMBERS = 4096
ALLOWED_HOSTS = frozenset((
    "api.github.com", "github.com", "release-assets.githubusercontent.com",
    "objects.githubusercontent.com",
))


class PortableUpdateError(Exception):
    """A safe refusal: do not change the installed application."""


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
            raise PortableUpdateError("Release download redirected outside the approved GitHub hosts.")
        if parsed.username or parsed.password or parsed.port not in (None, 443):
            raise PortableUpdateError("Release download redirected to an unexpected address.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url, destination=None, limit=MAX_JSON):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise PortableUpdateError("Refusing a non-GitHub or non-HTTPS download.")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise PortableUpdateError("Unexpected release address.")
    opener = urllib.request.build_opener(SafeRedirect())
    request = urllib.request.Request(url, headers={
        "User-Agent": "AppInstall-portable-update/1.8",
        "Accept": "application/vnd.github+json" if url == API_URL else "application/octet-stream",
    })
    try:
        with opener.open(request, timeout=25) as response:
            total = 0
            digest = hashlib.sha256()
            parts = [] if destination is None else None
            sink = destination.open("xb") if destination is not None else None
            try:
                while True:
                    part = response.read(128 * 1024)
                    if not part:
                        break
                    total += len(part)
                    if total > limit:
                        raise PortableUpdateError("Release asset exceeds the bounded download limit.")
                    digest.update(part)
                    if sink:
                        sink.write(part)
                    else:
                        parts.append(part)
                if sink:
                    sink.flush()
                    os.fsync(sink.fileno())
            finally:
                if sink:
                    sink.close()
            return (b"".join(parts) if parts is not None else None, digest.hexdigest(), total)
    except (OSError, ValueError, urllib.error.URLError) as error:
        raise PortableUpdateError("Could not securely download release data: " + str(error)) from error


def parse_release(data):
    """Return (version, tag, archive_asset, manifest_asset) from stable metadata."""
    if not isinstance(data, dict) or data.get("draft") is not False or data.get("prerelease") is not False:
        raise PortableUpdateError("Only an official, published stable release is supported.")
    tag = data.get("tag_name", "")
    if not isinstance(tag, str) or not tag.startswith("v") or not VERSION.fullmatch(tag[1:]):
        raise PortableUpdateError("Invalid stable release version.")
    version = tag[1:]
    archive_name = "appinstall-" + version + "-portable.tar.gz"
    names = (archive_name, "SHA256SUMS")
    assets = data.get("assets")
    if not isinstance(assets, list):
        raise PortableUpdateError("Release assets are missing.")
    selected = {}
    for asset in assets:
        if not isinstance(asset, dict) or asset.get("name") not in names:
            continue
        name = asset["name"]
        if name in selected:
            raise PortableUpdateError("Duplicate release asset: " + name)
        url = asset.get("browser_download_url")
        expected = f"https://github.com/{REPO}/releases/download/{tag}/{name}"
        size = asset.get("size")
        if url != expected or type(size) is not int or not (0 < size <= (MAX_ARCHIVE if name == archive_name else MAX_JSON)):
            raise PortableUpdateError("Release asset URL or size is not trusted: " + name)
        selected[name] = {"name": name, "url": url, "size": size}
    if any(name not in selected for name in names):
        raise PortableUpdateError("This release does not include the verified portable source asset.")
    return version, tag, selected[archive_name], selected["SHA256SUMS"]


def current_release():
    payload, _, _ = _fetch(API_URL, limit=MAX_JSON)
    try:
        return parse_release(json.loads(payload.decode("utf-8")))
    except (ValueError, UnicodeError, TypeError) as error:
        raise PortableUpdateError("Invalid GitHub stable release response.") from error


def _version(text):
    if not isinstance(text, str) or not VERSION.fullmatch(text):
        raise PortableUpdateError("Invalid installed AppInstall version.")
    return tuple(int(part) for part in text.split("."))


def installed_version(launcher):
    if launcher.is_symlink() or not launcher.is_file():
        raise PortableUpdateError("Portable AppInstall user launcher is missing or is a symlink.")
    match = re.search(rb'(?m)^VERSION="([0-9]+\.[0-9]+\.[0-9]+)"$', launcher.read_bytes()[:128 * 1024])
    if not match:
        raise PortableUpdateError("Portable launcher has no recognizable release version.")
    result = match[1].decode("ascii")
    _version(result)
    return result


def native_package_present():
    """Do not create a shadow update over an existing native installation."""
    checks = (
        ("pacman", ("pacman", "-Qq", "appinstall")),
        ("dpkg-query", ("dpkg-query", "-W", "-f=\${Status}", "appinstall")),
        ("rpm", ("rpm", "-q", "appinstall")),
    )
    for binary, args in checks:
        if not shutil.which(binary):
            continue
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise PortableUpdateError("Could not verify native package ownership.") from error
        if result.returncode == 0:
            if binary != "dpkg-query" or result.stdout.strip() == "install ok installed":
                return True
    return False


def require_user_install(state=None, home=None):
    if os.geteuid() == 0:
        raise PortableUpdateError("Run the portable updater as the regular desktop user, not root.")
    home = Path.home() if home is None else Path(home)
    data = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    expected = data / "appinstall"
    actual = Path(__file__).resolve().parent if state is None else Path(state)
    if actual.resolve() != expected.resolve():
        raise PortableUpdateError("Portable updates are available only for an installed user-source copy.")
    if actual.is_symlink() or not (actual / "integration.py").is_file() or (actual / "integration.py").is_symlink():
        raise PortableUpdateError("No intact portable source installation was found.")
    launcher = home / ".local/bin/appinstall"
    version = installed_version(launcher)
    if native_package_present():
        raise PortableUpdateError("Native AppInstall package detected; use the distro's package update instead.")
    return version, launcher, actual


def expected_digest(manifest, filename):
    try:
        lines = manifest.decode("utf-8").splitlines()
    except UnicodeError as error:
        raise PortableUpdateError("Checksum manifest is not UTF-8.") from error
    hashes = []
    for line in lines:
        match = re.fullmatch(r"([0-9a-fA-F]{64})  ([A-Za-z0-9._-]+)", line)
        if not match:
            raise PortableUpdateError("Checksum manifest contains an invalid entry.")
        if match[2] == filename:
            hashes.append(match[1].lower())
    if len(hashes) != 1:
        raise PortableUpdateError("Checksum manifest does not identify the archive exactly once.")
    return hashes[0]


def unpack_archive(archive, directory, version):
    """Extract regular files only, with bounded total expanded size and no links."""
    prefix = "appinstall-" + version
    folder = directory / prefix
    count = 0
    total = 0
    seen = set()
    try:
        with tarfile.open(archive, mode="r:gz") as bundle:
            for item in bundle:
                count += 1
                if count > MAX_MEMBERS:
                    raise PortableUpdateError("Portable archive contains too many entries.")
                rel = PurePosixPath(item.name)
                if (rel.is_absolute() or not rel.parts or rel.parts[0] != prefix
                        or any(x in ("", ".", "..") for x in item.name.split("/"))
                        or item.name in seen or (not item.isfile() and not item.isdir())):
                    raise PortableUpdateError("Portable archive includes an unsafe path or entry.")
                seen.add(item.name)
                target = directory.joinpath(*rel.parts)
                if item.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if item.size < 0 or item.size > MAX_UNPACKED:
                    raise PortableUpdateError("Portable file exceeds the extraction limit.")
                total += item.size
                if total > MAX_UNPACKED:
                    raise PortableUpdateError("Portable archive expands beyond its limit.")
                target.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(item)
                if source is None:
                    raise PortableUpdateError("Portable archive file could not be read.")
                with target.open("xb") as dest, source:
                    copied = shutil.copyfileobj(source, dest, length=128 * 1024)
                if target.stat().st_size != item.size:
                    raise PortableUpdateError("Portable archive entry length is invalid.")
                target.chmod(0o755 if rel.as_posix() in (
                    prefix + "/appinstall", prefix + "/install-user.sh") else 0o644)
    except (tarfile.TarError, EOFError, OSError) as error:
        raise PortableUpdateError("Could not unpack the verified portable archive: " + str(error)) from error
    required = ("appinstall", "integration.py", "source_transaction.py",
                "portable_update.py", "manager_qml.py", "manager_ui/main.qml",
                "appinstall.desktop", "appinstall-appimage-review.desktop")
    if any(not (folder / name).is_file() for name in required):
        raise PortableUpdateError("Portable archive lacks required installation files.")
    if installed_version(folder / "appinstall") != version:
        raise PortableUpdateError("Archive launcher version does not match the release.")
    return folder


def apply_update(tag, installation, release, downloader=_fetch):
    """Install verified user-source files via the existing recoverable transaction."""
    version, release_tag, archive, manifest = release
    if tag != release_tag:
        raise PortableUpdateError("Published release changed; check for updates again.")
    current, launcher, state = installation
    if _version(version) <= _version(current):
        raise PortableUpdateError("Refusing to reinstall or downgrade an existing version.")
    with tempfile.TemporaryDirectory(prefix="appinstall-portable-update-") as temp:
        directory = Path(temp)
        checksum, _, checksum_size = downloader(manifest["url"], limit=MAX_JSON)
        if checksum_size != manifest["size"]:
            raise PortableUpdateError("Checksum manifest length changed during download.")
        wanted = expected_digest(checksum, archive["name"])
        archive_file = directory / archive["name"]
        _, received, archive_size = downloader(archive["url"], destination=archive_file, limit=MAX_ARCHIVE)
        if archive_size != archive["size"] or received != wanted:
            raise PortableUpdateError("Archive hash or size does not match SHA256SUMS.")
        folder = unpack_archive(archive_file, directory, version)
        # The installed source may have changed while downloading. Do not
        # update a different installation or replace a concurrently newer one.
        again, actual_launcher, actual_state = require_user_install()
        if (again != current or actual_launcher.resolve() != launcher.resolve()
                or actual_state.resolve() != state.resolve()):
            raise PortableUpdateError("Installed portable version changed; check again.")
        result = subprocess.run([sys.executable, str(folder / "integration.py")],
                                cwd=str(folder), capture_output=True, text=True,
                                timeout=180)
        if result.returncode != 0:
            raise PortableUpdateError(
                "Recoverable source update did not complete: " +
                (result.stderr or result.stdout)[-1200:])
        if installed_version(launcher) != version:
            raise PortableUpdateError("Updated launcher version could not be verified.")
    return release_tag


def main(argv=None):
    parser = argparse.ArgumentParser(description="AppInstall portable user-source updater (published stable only)")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--desktop-check", "--check", action="store_true")
    actions.add_argument("--desktop-update", "--update", metavar="VERSION_TAG")
    options = parser.parse_args(argv)
    try:
        installation = require_user_install()
        release = current_release()
        current = _version(installation[0])
        latest = _version(release[0])
        if options.desktop_check:
            if latest > current:
                print("APPINSTALL_UPDATE=" + release[1])
            return 0
        if latest <= current:
            raise PortableUpdateError("No newer published stable release is available.")
        tag = apply_update(options.desktop_update, installation, release)
        print("APPINSTALL_UPDATED=" + tag)
        return 0
    except (PortableUpdateError, subprocess.TimeoutExpired) as error:
        print("AppInstall portable update refused: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
