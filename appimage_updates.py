"""Optional AppImage updates: strict ownership, staged download, reviewed atomic swap.

This is a conservative wrapper around an independently installed
appimageupdatetool. The AppImage binary itself is never executed during
discovery, preparation, or publication. A .zsync checksum is *not* an
upstream signature; the UI must disclose this before approval.
"""
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from urllib.parse import urlsplit

import appimage_backend
import launch_monitor
from url_install import validate_url, DownloadError

MAX_SIZE = 2 * 1024 * 1024 * 1024
MAX_OUTPUT = 128 * 1024
CHECK_TIMEOUT = 75
DOWNLOAD_TIMEOUT = 900
GH_PART = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")
GH_ASSET = re.compile(r"[A-Za-z0-9_.\-\*]{1,240}\.AppImage\.zsync\Z", re.I)
INFO_LINE = re.compile(r"\]\s*((?:zsync|gh-releases-zsync)\|[^\r\n]{1,600})")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class AppImageUpdateBlocked(RuntimeError):
    """A requested update cannot safely be checked, staged or installed."""


@dataclass(frozen=True)
class AppImagePlan:
    key: str
    target: str
    staging: str
    staged_file: str
    original_sha256: str
    candidate_sha256: str
    original_size: int
    candidate_size: int
    update_information: str
    source: str


@dataclass(frozen=True)
class AppImageResult:
    key: str
    target: str
    sha256: str
    backup: str
    message: str


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_appimage(path):
    """Passive ELF + AppImage type-2 header and SquashFS metadata check."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        return False
    size = path.stat().st_size
    if size < 1024 or size > MAX_SIZE:
        return False
    with path.open("rb") as stream:
        head = stream.read(16)
    if head[:4] != b"\x7fELF" or head[8:11] != b"AI\x02":
        return False
    return appimage_backend.squashfs_offset(path) is not None


def parse_update_info(output):
    """Extract a single embedded update transport, with no code execution."""
    matches = [m.group(1).strip() for m in INFO_LINE.finditer(output or "")]
    unique = list(dict.fromkeys(matches))
    if len(unique) != 1:
        return None
    return unique[0]


def validate_info(value, *, resolve=True):
    """Only HTTPS zsync or well-formed GitHub Releases zsync channels."""
    if not isinstance(value, str) or not value or len(value) > 600:
        raise AppImageUpdateBlocked("Missing or oversized embedded AppImage update data.")
    if any(ord(ch) < 33 or ord(ch) > 126 for ch in value):
        raise AppImageUpdateBlocked("Invalid characters in embedded update metadata.")
    parts = value.split("|")
    if len(parts) == 2 and parts[0] == "zsync":
        uri = parts[1]
        try:
            parsed = urlsplit(uri)
        except ValueError as exc:
            raise AppImageUpdateBlocked("Invalid zsync URL.") from exc
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.fragment or parsed.query
                or not parsed.path.endswith(".zsync")):
            raise AppImageUpdateBlocked("AppImage zsync updates require an HTTPS .zsync URL.")
        # validate_url rejects IP literals pointing into private networks and
        # mixed/public-private DNS answers. The third-party updater manages its
        # own connections; this precheck does not pin DNS after lookup.
        if resolve:
            try:
                validate_url(uri)
            except DownloadError as exc:
                raise AppImageUpdateBlocked("Untrusted AppImage update source: " + str(exc)) from exc
        return "zsync"
    if (len(parts) == 5 and parts[0] == "gh-releases-zsync"
            and all(GH_PART.fullmatch(x) and x not in (".", "..")
                    for x in parts[1:4])
            and GH_ASSET.fullmatch(parts[4])
            and ".." not in parts[4]):
        return "GitHub Releases zsync"
    raise AppImageUpdateBlocked(
        "Unsupported embedded AppImage update source; manual replacement required.")


def read_info(path, runner=None):
    """Read both widely used ELF update-section names, without running image."""
    runner = runner if runner is not None else subprocess.run
    if not shutil.which("readelf"):
        return None
    for section in (".upd_info", ".upd-info"):
        argv = ["readelf", "--string-dump=" + section, str(path)]
        try:
            proc = runner(argv, capture_output=True, text=True,
                          errors="replace", timeout=15)
        except (OSError, subprocess.SubprocessError):
            return None
        output = proc.stdout or ""
        if proc.returncode == 0 and len(output) <= MAX_OUTPUT:
            value = parse_update_info(output)
            if value:
                return value
    return None


def verify_owned(app):
    """Require current launch-monitor registry, manifest, and generation."""
    if not isinstance(app, dict) or app.get("format") != "appimage":
        raise AppImageUpdateBlocked("Only managed AppImages support this update path.")
    if app.get("source") != "launch-monitor" or app.get("status") != "installed":
        raise AppImageUpdateBlocked("AppImage registration or health must be repaired.")
    key = app.get("key")
    raw = app.get("raw")
    if not isinstance(raw, dict) or not isinstance(key, str):
        raise AppImageUpdateBlocked("Invalid application registry record.")
    manifest_name = raw.get("manifest")
    if not isinstance(manifest_name, str) or not manifest_name:
        raise AppImageUpdateBlocked("AppImage does not have an AppInstall-owned manifest.")
    manifest = Path(manifest_name)
    root = launch_monitor.data_root()
    if (not manifest.is_absolute() or manifest.is_symlink()
            or manifest.parent != root or manifest.suffix != ".json"
            or key != "appimage:" + manifest.stem):
        raise AppImageUpdateBlocked("AppImage manifest identity is not owned by AppInstall.")
    try:
        current = launch_monitor.registry()[key]
        info = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise AppImageUpdateBlocked("AppImage launcher or manifest is missing.") from exc
    if current != raw or not isinstance(info, dict):
        raise AppImageUpdateBlocked("AppImage launcher registry changed. Refresh applications.")
    if info.get("fallback"):
        raise AppImageUpdateBlocked(
            "Extracted AppImage launchers need manual replacement; binary-only update unsafe.")
    target_name = info.get("target")
    generation_name = info.get("generation")
    if not isinstance(target_name, str) or not isinstance(generation_name, str):
        raise AppImageUpdateBlocked("Incomplete AppImage generation record.")
    target, generation = Path(target_name), Path(generation_name)
    if (not target.is_absolute() or not generation.is_absolute()
            or generation.is_symlink() or target.is_symlink()
            or generation != target.parent
            or not generation.name.startswith(".appinstall-")
            or target.suffix.lower() != ".appimage"
            or not target.is_file()
            or str(target) != app.get("target")):
        raise AppImageUpdateBlocked("AppImage target is not an unchanged managed generation.")
    stat_info = generation.stat()
    file_info = target.stat()
    if (stat_info.st_uid != os.getuid() or file_info.st_uid != os.getuid()
            or stat_info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)):
        raise AppImageUpdateBlocked("AppImage generation ownership or permissions are unsafe.")
    desktop_name = raw.get("desktop")
    desktop = Path(desktop_name) if isinstance(desktop_name, str) else None
    if (desktop is None or desktop.is_symlink() or not desktop.is_file()
            or current.get("manifest") != str(manifest)):
        raise AppImageUpdateBlocked("AppImage desktop launcher is missing or untrusted.")
    if not is_appimage(target):
        raise AppImageUpdateBlocked("Installed file is not a validated type-2 AppImage.")
    return target, manifest


def check_upstream(target, runner=None, *, cancelled=None):
    """Read-only check: 0 = current, 1 = newer, any other code = failure."""
    if cancelled is not None and cancelled():
        raise AppImageUpdateBlocked("Update check cancelled.")
    if not shutil.which("appimageupdatetool"):
        raise AppImageUpdateBlocked(
            "Optional appimageupdatetool is not installed; manual replacement required.")
    runner = runner if runner is not None else subprocess.run
    argv = ["appimageupdatetool", "--check-for-update", "--", str(target)]
    try:
        proc = runner(argv, capture_output=True, text=True,
                      errors="replace", timeout=CHECK_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        raise AppImageUpdateBlocked("AppImage update check failed: " + str(exc)) from exc
    if cancelled is not None and cancelled():
        raise AppImageUpdateBlocked("Update check cancelled.")
    if (len(proc.stdout or "") + len(proc.stderr or "")) > MAX_OUTPUT:
        raise AppImageUpdateBlocked("AppImage update tool output exceeds limit.")
    if proc.returncode not in (0, 1):
        raise AppImageUpdateBlocked("AppImage update check failed (code "
                                    + str(proc.returncode) + ").")
    return proc.returncode == 1


def cleanup_plan(plan):
    if not isinstance(plan, AppImagePlan):
        return
    staging = Path(plan.staging)
    target = Path(plan.target)
    if (staging.name.startswith(".appinstall-update-")
            and staging.parent == target.parent and not staging.is_symlink()):
        shutil.rmtree(staging, ignore_errors=True)


class AppImageUpgradeService:
    def __init__(self, runner=None):
        self.runner = runner if runner is not None else subprocess.run

    def prepare(self, app, expected, progress=None):
        """Download into private staging; never touch the registered executable."""
        notify = progress or (lambda _: None)
        target, _ = verify_owned(app)
        original = sha256_file(target)
        info = read_info(target, self.runner)
        if not info:
            raise AppImageUpdateBlocked("No embedded AppImage update information.")
        source = validate_info(info)
        if (not expected or expected.state != "available"
                or expected.mechanism != "appimage-zsync"
                or expected.key != app["key"] or expected.reference != info
                or expected.installed_revision != original):
            raise AppImageUpdateBlocked("AppImage update metadata changed; check again.")
        notify("Rechecking upstream AppImage update availability…")
        if not check_upstream(target, self.runner):
            raise AppImageUpdateBlocked("AppImage is already up to date.")
        if not shutil.which("appimageupdatetool"):
            raise AppImageUpdateBlocked("AppImage update tool is missing.")
        directory = Path(tempfile.mkdtemp(
            prefix=".appinstall-update-", dir=target.parent))
        staged = directory / target.name
        try:
            shutil.copyfile(target, staged)
            staged.chmod(0o700)
            if sha256_file(staged) != original:
                raise AppImageUpdateBlocked("Staged AppImage differs from the installed version.")
            notify("Downloading upstream zsync delta into private staging (checksum is not a signature)…")
            try:
                proc = self.runner(
                    ["appimageupdatetool", "--overwrite", "--", str(staged)],
                    cwd=str(directory), capture_output=True, text=True,
                    errors="replace", timeout=DOWNLOAD_TIMEOUT)
            except (OSError, subprocess.SubprocessError) as exc:
                raise AppImageUpdateBlocked("AppImage staging failed: " + str(exc)) from exc
            if proc.returncode != 0:
                raise AppImageUpdateBlocked(
                    "AppImage updater failed: " + (proc.stderr or proc.stdout or "")[-600:])
            if (not is_appimage(staged) or
                    staged.stat().st_size > MAX_SIZE or
                    staged.stat().st_uid != os.getuid()):
                raise AppImageUpdateBlocked("Downloaded AppImage failed passive validation.")
            new_info = read_info(staged, self.runner)
            if new_info != info:
                raise AppImageUpdateBlocked(
                    "Downloaded AppImage changed its update channel; manual review required.")
            digest = sha256_file(staged)
            if digest == original:
                raise AppImageUpdateBlocked("Updater returned the same image; nothing to replace.")
            # No arbitrary additional files are expected in this private stage.
            if set(directory.iterdir()) != {staged}:
                raise AppImageUpdateBlocked("Updater produced unexpected staging files.")
            notify("New AppImage downloaded and checked; awaiting explicit approval.")
            return AppImagePlan(
                key=app["key"], target=str(target), staging=str(directory),
                staged_file=str(staged), original_sha256=original,
                candidate_sha256=digest, original_size=target.stat().st_size,
                candidate_size=staged.stat().st_size,
                update_information=info, source=source)
        except BaseException:
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def apply(self, plan, app):
        """Commit one approved staged payload, keeping old hardlink for recovery."""
        if not isinstance(plan, AppImagePlan):
            raise AppImageUpdateBlocked("No approved AppImage update plan.")
        target, _ = verify_owned(app)
        if plan.key != app["key"] or str(target) != plan.target:
            raise AppImageUpdateBlocked("AppImage identity changed since review.")
        staged, directory = Path(plan.staged_file), Path(plan.staging)
        if (directory.parent != target.parent or
                not directory.name.startswith(".appinstall-update-") or
                staged.parent != directory or staged.name != target.name or
                directory.is_symlink() or staged.is_symlink() or
                not staged.is_file()):
            raise AppImageUpdateBlocked("Staged update is not AppInstall-owned.")
        if not SHA256.fullmatch(plan.original_sha256) or not SHA256.fullmatch(plan.candidate_sha256):
            raise AppImageUpdateBlocked("Update plan has an invalid SHA-256 digest.")
        lock = launch_monitor.data_root() / "appimage-updates.lock"
        lock.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        backup = target.parent / (".appinstall-previous-" +
                                  plan.original_sha256[:20] + ".AppImage")
        with lock.open("a") as lockfile:
            fcntl.flock(lockfile, fcntl.LOCK_EX)
            verify_owned(app)
            if (sha256_file(target) != plan.original_sha256
                    or target.stat().st_size != plan.original_size
                    or sha256_file(staged) != plan.candidate_sha256
                    or staged.stat().st_size != plan.candidate_size
                    or read_info(target, self.runner) != plan.update_information
                    or read_info(staged, self.runner) != plan.update_information
                    or not is_appimage(staged)):
                raise AppImageUpdateBlocked(
                    "AppImage source or staged artifact changed. No files were replaced.")
            # Never overwrite someone else's recovery file, even if its name
            # matches the current SHA prefix. Hardlink is atomic and in-place.
            if backup.exists() or backup.is_symlink():
                if backup.is_symlink() or sha256_file(backup) != plan.original_sha256:
                    raise AppImageUpdateBlocked("Existing recovery copy conflicts with this update.")
            else:
                os.link(target, backup, follow_symlinks=False)
            try:
                # Installed launcher/manifest contains an unchanged absolute
                # path, so settings, file associations and desktop IDs persist.
                os.replace(staged, target)
                target.chmod(0o755)
            except BaseException:
                # A previous image remains addressable by backup after any
                # failure; the managed path was never deliberately removed.
                raise
        cleanup_plan(plan)
        return AppImageResult(
            key=app["key"], target=str(target), sha256=plan.candidate_sha256,
            backup=str(backup),
            message=("AppImage updated in place. Previous executable kept at "
                     + str(backup) + " for recovery."))
