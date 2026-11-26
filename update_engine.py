"""Read-only application update discovery for AppInstall v1.8 (phase 1).

This module discovers candidates; it NEVER installs, creates containers,
refreshes package indexes, updates launchers, or modifies a package registry.
UI/transaction review and actual upgrades belong to later approved PRs.
Run check_many() on a worker thread, not the Qt GUI thread.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

import container_backend
import repository_catalog

AVAILABLE = "available"
UP_TO_DATE = "up-to-date"
MANUAL_REQUIRED = "manual-required"
UNSUPPORTED = "unsupported"
ERROR = "error"
CHECKING = "checking"
STATES = frozenset((AVAILABLE, UP_TO_DATE, MANUAL_REQUIRED,
                    UNSUPPORTED, ERROR, CHECKING))

COMMIT_RE = re.compile(r"[a-fA-F0-9]{64}\Z")
APP_ID_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+){2,}\Z")
ORIGIN_RE = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")
REF_RE = re.compile(r"app/([A-Za-z_][A-Za-z0-9_.-]+)/([A-Za-z0-9_-]+)/([A-Za-z0-9_.-]+)\Z")
RPM_LINE = re.compile(r"([A-Za-z0-9][A-Za-z0-9+_.-]{0,127})\t([^\t\n]+)\t(x86_64|aarch64|noarch)\Z")
MAX_OUTPUT = 256 * 1024
QUERY_TIMEOUT = 30
CACHE_TTL_SECONDS = 15 * 60
MAX_APPS = 512


class UpdateCancelled(RuntimeError):
    """The caller cancelled a multi-application update scan."""


@dataclass(frozen=True)
class UpdateCandidate:
    key: str
    format: str
    state: str
    installed_version: str = ""
    available_version: str = ""
    source: str = ""
    mechanism: str = ""
    reason: str = ""
    requires_review: bool = False
    reference: str = ""
    installed_revision: str = ""
    available_revision: str = ""

    def to_dict(self):
        return asdict(self)


def classify_update_failure(output):
    """Return (category, title, action) for a failed AppInstall update check."""
    text = output or ""
    marker = re.search(r'^APPINSTALL_UPDATE_ERROR=([a-z-]+):\s*(.+)$', text, re.M)
    if marker:
        category, detail = marker[1], marker[2]
    elif re.search(r'rate limit|HTTP 403', text, re.I):
        category, detail = 'api-limit', 'GitHub rate limit reached.'
    elif re.search(r'timed out|timeout', text, re.I):
        category, detail = 'timeout', 'The update service did not respond in time.'
    elif re.search(r'could not resolve|failed to connect|proxy|network|unreachable', text, re.I):
        category, detail = 'network', 'The update service could not be reached.'
    elif re.search(r'not found|not installed|unavailable|missing command', text, re.I):
        category, detail = 'dependency', 'A required update dependency is missing.'
    else:
        category, detail = 'backend', 'The update backend reported a failure.'
    titles = {
        'network': 'Network problem', 'timeout': 'Update check timed out',
        'http': 'GitHub API error', 'api-limit': 'GitHub rate limit reached',
        'tls': 'Certificate problem', 'dependency': 'Missing update dependency',
        'unsupported': 'Unsupported installation', 'backend': 'Update check failed',
    }
    actions = {
        'network': 'Check your internet connection, DNS, firewall and proxy settings, then try again.',
        'timeout': 'Wait a moment and try again. If it repeats, check your network or GitHub status.',
        'http': 'Check GitHub API rate limits and try again later.',
        'api-limit': 'Wait for the GitHub rate limit to reset, then try again.',
        'tls': 'Check your system time and CA certificates, then try again.',
        'dependency': 'Install the missing update dependency from your distribution, then try again.',
        'unsupported': 'Use a verified installation path for automatic updates.',
        'backend': 'Review the diagnostic details below and try again.',
    }
    return category, titles.get(category, 'Update check failed'), \
        actions.get(category, actions['backend']) + '\n\n' + detail


def _clean(value):
    return str(value).strip()[:240] if value is not None else ""


def backend_error_reason(fmt, exc):
    """Turn a provider exception into a short, actionable backend message."""
    names = {
        "flatpak": "Flatpak", "deb": "APT/DEB",
        "rpm": "DNF/RPM", "appimage": "AppImage",
    }
    name = names.get(fmt, fmt)
    if isinstance(exc, subprocess.TimeoutExpired):
        return (name + " update check timed out. Check the backend and try again.")
    if isinstance(exc, FileNotFoundError):
        return (name + " update backend is not installed (" +
                str(getattr(exc, "filename", "missing command")) + ").")
    if isinstance(exc, subprocess.SubprocessError):
        return (name + " update backend failed: " + _clean(exc)[:180])
    return (name + " update check failed: " + _clean(exc)[:180])


def _package_identity(app, kind):
    """Refuse guessed sources, changed containers, and imported local files."""
    raw = app.get("raw") if isinstance(app.get("raw"), dict) else {}
    key = app.get("key", "")
    name = raw.get("name")
    if not isinstance(key, str):
        return None
    if raw.get("kind") != kind or raw.get("install_method") != "repository":
        return None
    try:
        name = repository_catalog.validate_name(name)
    except ValueError:
        return None
    if key != kind + ":" + name:
        return None
    container, image = container_backend.SPECS[kind]
    if raw.get("container") != container or raw.get("image") != image:
        return None
    return name


class UpdateEngine:
    """Synchronous, bounded, cacheable discovery with injectable I/O for tests.

    Only query commands are permitted. Commands are argument lists, never
    shell strings, and errors are reported as update states. Use force=True
    for an explicit refresh. Cancellation is checked before/after each query
    and between applications.
    """

    def __init__(self, runner=None, clock=None, ttl=CACHE_TTL_SECONDS):
        self._runner = runner if runner is not None else subprocess.run
        self._clock = clock if clock is not None else time.monotonic
        self._ttl = max(0, float(ttl))
        self._cache = {}
        self._lock = threading.RLock()

    def _cancel(self, cancelled):
        if cancelled is not None and cancelled():
            raise UpdateCancelled("Update check cancelled.")

    def _query(self, args, cancelled=None, timeout=QUERY_TIMEOUT, container=False):
        self._cancel(cancelled)
        env = dict(container_backend.ENV)
        try:
            proc = self._runner(
                list(args), capture_output=True, text=True, errors="replace",
                env=env, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError("Update query could not run: " + str(exc)) from exc
        self._cancel(cancelled)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        if len(stdout) > MAX_OUTPUT or len(stderr) > MAX_OUTPUT:
            raise RuntimeError("Update query returned excessive output.")
        if proc.returncode:
            raise RuntimeError("Update query failed: " + (stderr or stdout)[-700:])
        return stdout.strip()

    def _container(self, kind, args, cancelled):
        if not repository_catalog.ready(kind):
            raise RuntimeError("AppInstall-owned " + kind.upper() +
                               " repository container is not prepared.")
        container = container_backend.SPECS[kind][0]
        return self._query(
            ["distrobox", "enter", "--name", container, "--no-tty", "--", *args],
            cancelled, container=True)

    @staticmethod
    def _candidate(app, state, **extra):
        default_version = (app.get("version")
                           if app.get("version") not in (None, "unknown") else "")
        fields = {
            "key": _clean(app.get("key")), "format": _clean(app.get("format")),
            "state": state, "installed_version": _clean(default_version),
        }
        fields.update(extra)
        return UpdateCandidate(**fields)

    def _flatpak(self, app, cancelled):
        key = app.get("key", "")
        raw = app.get("raw") if isinstance(app.get("raw"), dict) else {}
        app_id = raw.get("appid") or (key.removeprefix("flatpak:") if isinstance(key, str) else "")
        if (not isinstance(key, str) or key != "flatpak:" + str(app_id)
                or not isinstance(app_id, str) or not APP_ID_RE.fullmatch(app_id)):
            return self._candidate(app, MANUAL_REQUIRED,
                                   reason="Cannot verify the installed Flatpak application ID.")
        # Ask the installed app for its exact ref and actual originating remote.
        # Never assume every Flatpak came from Flathub or query system scope.
        ref = self._query(["flatpak", "info", "--user", "--show-ref", app_id], cancelled)
        match = REF_RE.fullmatch(ref)
        if not match or match.group(1) != app_id:
            raise RuntimeError("Installed Flatpak reference does not match this application.")
        origin = self._query(["flatpak", "info", "--user", "--show-origin", ref], cancelled)
        if not ORIGIN_RE.fullmatch(origin):
            raise RuntimeError("Flatpak origin cannot be verified.")
        local = self._query(["flatpak", "info", "--user", "--show-commit", ref], cancelled)
        if not COMMIT_RE.fullmatch(local):
            raise RuntimeError("Installed Flatpak commit is invalid.")
        remote = self._query(["flatpak", "remote-info", "--user", "--show-commit",
                              origin, ref], cancelled)
        if not COMMIT_RE.fullmatch(remote):
            raise RuntimeError("Remote Flatpak commit is invalid.")
        state = AVAILABLE if local.lower() != remote.lower() else UP_TO_DATE
        return self._candidate(
            app, state, source=origin, mechanism="flatpak-ref",
            installed_version=_clean(app.get("version")) if app.get("version") not in (None, "unknown") else local[:12],
            available_version=remote[:12] if state == AVAILABLE else "",
            reason=("New commit available for " + ref if state == AVAILABLE
                    else "Installed Flatpak commit matches the remote."),
            requires_review=state == AVAILABLE,
            reference=ref, installed_revision=local.lower(),
            available_revision=remote.lower() if state == AVAILABLE else "")

    @staticmethod
    def _deb_policy(text, name):
        # apt-cache policy OUTPUT uses Installed: and Candidate: sections.
        # A malicious/changed package name cannot be passed as an option.
        installed = re.search(r"(?m)^\s*Installed:\s*(\S+)\s*$", text)
        candidate = re.search(r"(?m)^\s*Candidate:\s*(\S+)\s*$", text)
        if not installed or not candidate:
            raise RuntimeError("APT did not provide installed and candidate versions.")
        return installed.group(1), candidate.group(1)

    def _deb(self, app, cancelled):
        name = _package_identity(app, "deb")
        if not name:
            return self._candidate(
                app, MANUAL_REQUIRED,
                reason="Imported DEB or unknown provenance: choose and review a newer package file.")
        policy = self._container("deb", ["apt-cache", "policy", name], cancelled)
        installed, candidate = self._deb_policy(policy, name)
        if installed == "(none)":
            raise RuntimeError("APT reports the tracked Debian package is not installed.")
        if app.get("version") not in (None, "unknown", installed):
            raise RuntimeError("Installed Debian version differs from the managed record; inspect the container.")
        if candidate == "(none)":
            return self._candidate(app, MANUAL_REQUIRED, installed_version=installed,
                                   source="Debian 13", mechanism="apt-repository",
                                   reason="No candidate in the configured Debian repository.")
        # dpkg understands Debian epoch, tilde, and revision semantics.
        # The comparison returns 1 for a *normal* false condition.
        self._cancel(cancelled)
        container = container_backend.SPECS["deb"][0]
        argv = ["distrobox", "enter", "--name", container, "--no-tty", "--",
                "dpkg", "--compare-versions", installed, "lt", candidate]
        try:
            proc = self._runner(argv, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, text=True,
                                errors="replace", env=dict(container_backend.ENV),
                                timeout=QUERY_TIMEOUT)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError("dpkg version comparison failed: " + str(exc)) from exc
        self._cancel(cancelled)
        if proc.returncode not in (0, 1):
            raise RuntimeError("dpkg could not compare candidate package versions.")
        state = AVAILABLE if proc.returncode == 0 else UP_TO_DATE
        return self._candidate(
            app, state, installed_version=installed,
            available_version=candidate if state == AVAILABLE else "",
            source="Debian 13", mechanism="apt-repository",
            reason="Debian repository candidate checked with dpkg version semantics.",
            requires_review=state == AVAILABLE)

    def _rpm(self, app, cancelled):
        name = _package_identity(app, "rpm")
        if not name:
            return self._candidate(
                app, MANUAL_REQUIRED,
                reason="Imported RPM or unknown provenance: choose and review a newer package file.")
        installed_text = self._container(
            "rpm", ["rpm", "-q", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\n", name],
            cancelled)
        installed = [m.groups() for line in installed_text.splitlines()
                     if (m := RPM_LINE.fullmatch(line)) and m.group(1) == name]
        if len(installed) != 1:
            raise RuntimeError("Installed Fedora package cannot be uniquely identified.")
        _, version, arch = installed[0]
        if app.get("version") not in (None, "unknown", version):
            raise RuntimeError("Installed Fedora version differs from the managed record; inspect the container.")
        upgrades_text = self._container(
            "rpm", ["dnf", "repoquery", "--upgrades", "--latest-limit=1",
                    "--queryformat=%{name}\t%{version}-%{release}\t%{arch}\\n", name],
            cancelled)
        matches = [m.groups() for line in upgrades_text.splitlines()
                   if (m := RPM_LINE.fullmatch(line))
                   and m.group(1) == name and m.group(3) == arch]
        if len(matches) > 1:
            raise RuntimeError("Fedora returned ambiguous upgrade candidates.")
        state = AVAILABLE if matches else UP_TO_DATE
        return self._candidate(
            app, state, installed_version=version,
            available_version=matches[0][1] if matches else "",
            source="Fedora 44", mechanism="dnf-repository",
            reason=("Newer package offered by DNF5." if matches
                    else "No newer version offered by Fedora repositories."),
            requires_review=state == AVAILABLE)

    def _appimage(self, app, cancelled):
        """Passive embedded-info discovery, then a *read-only* upstream check.

        Only managed, type-2 AppImages with a supported zsync transport and
        the optional appimageupdatetool may become actionable. Imported or
        unsupported images remain manually replaceable, never auto-updated.
        """
        import appimage_updates
        raw = app.get("raw") if isinstance(app.get("raw"), dict) else {}
        target = app.get("target") or raw.get("target")
        if not isinstance(target, str) or not target:
            return self._candidate(
                app, MANUAL_REQUIRED,
                reason="AppImage file is missing; replace it from a reviewed file or URL.")
        path = Path(target)
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            return self._candidate(
                app, MANUAL_REQUIRED, reason="AppImage update target cannot be verified.")
        info = appimage_updates.read_info(path, self._runner)
        if not info:
            return self._candidate(
                app, MANUAL_REQUIRED,
                reason="No recognized AppImage update information; manual replacement required.")
        source = "Embedded AppImage update metadata"
        if not shutil.which("appimageupdatetool"):
            return self._candidate(
                app, MANUAL_REQUIRED, source=source,
                mechanism="appimage-upd-info",
                reason="Embedded updater metadata found, but appimageupdatetool is not installed.")
        try:
            owned_target, _ = appimage_updates.verify_owned(app)
        except appimage_updates.AppImageUpdateBlocked as exc:
            return self._candidate(
                app, MANUAL_REQUIRED, source=source,
                mechanism="appimage-upd-info", reason=str(exc))
        if owned_target != path:
            return self._candidate(
                app, MANUAL_REQUIRED, source=source,
                mechanism="appimage-upd-info", reason="AppImage generation changed.")
        try:
            # Only resolve upstream hosts after ownership was verified.
            label = appimage_updates.validate_info(info)
        except appimage_updates.AppImageUpdateBlocked as exc:
            return self._candidate(
                app, MANUAL_REQUIRED, source=source,
                mechanism="appimage-upd-info", reason=str(exc))
        try:
            newer = appimage_updates.check_upstream(
                owned_target, runner=self._runner, cancelled=cancelled)
        except appimage_updates.AppImageUpdateBlocked as exc:
            if cancelled is not None and cancelled():
                raise UpdateCancelled("AppImage update check cancelled.") from exc
            return self._candidate(
                app, ERROR, source=label, mechanism="appimage-zsync",
                reason=str(exc))
        digest = appimage_updates.sha256_file(path)
        state = AVAILABLE if newer else UP_TO_DATE
        return self._candidate(
            app, state, source=label, mechanism="appimage-zsync",
            installed_version=_clean(app.get("version"))
            if app.get("version") not in (None, "unknown") else "",
            available_version="New upstream build" if newer else "",
            reason=("Upstream AppImage has changed; download and review the full "
                    "artifact before any replacement."
                    if newer else "Upstream AppImage has no newer build."),
            requires_review=newer, reference=info, installed_revision=digest)

    def check_one(self, app, *, cancelled=None, force=False):
        if not isinstance(app, dict):
            raise TypeError("An application record must be a dictionary.")
        self._cancel(cancelled)
        key, fmt = app.get("key", ""), app.get("format", "")
        if not isinstance(key, str) or not key or fmt not in ("flatpak", "deb", "rpm", "appimage"):
            return self._candidate(app, UNSUPPORTED, reason="Unsupported application record.")
        raw = app.get("raw") if isinstance(app.get("raw"), dict) else {}
        fingerprint = (key, fmt, app.get("version"), app.get("status"),
                       *(str(raw.get(k, "")) for k in
                         ("install_method", "kind", "name", "image", "container", "appid", "target")))
        # Avoid reusing an AppImage "available" result after the executable
        # changes on disk. This is read-only and handles disappeared files.
        if fmt == "appimage":
            path = app.get("target") or raw.get("target")
            try:
                stat = Path(path).stat() if isinstance(path, str) else None
                fingerprint += (stat.st_size, stat.st_mtime_ns, stat.st_ino) if stat else ("missing",)
            except OSError:
                fingerprint += ("missing",)
        now = self._clock()
        if not force:
            with self._lock:
                previous = self._cache.get(fingerprint)
            if previous and now - previous[0] < self._ttl:
                self._cancel(cancelled)
                return previous[1]
        if app.get("status", "installed") != "installed":
            result = self._candidate(app, ERROR,
                                     reason="Application requires repair before checking updates.")
        else:
            try:
                result = {
                    "flatpak": self._flatpak,
                    "deb": self._deb,
                    "rpm": self._rpm,
                    "appimage": self._appimage,
                }[fmt](app, cancelled)
            except UpdateCancelled:
                raise
            except Exception as exc:  # noqa: BLE001 - isolate every provider
                result = self._candidate(app, ERROR,
                                         reason=backend_error_reason(fmt, exc)[:360])
        if result.state != ERROR:
            with self._lock:
                if len(self._cache) >= MAX_APPS:
                    self._cache.clear()
                self._cache[fingerprint] = (now, result)
        return result

    def check_many(self, apps, *, cancelled=None, force=False):
        results = []
        for index, app in enumerate(apps):
            if index >= MAX_APPS:
                break
            if cancelled is not None and cancelled():
                break
            try:
                results.append(self.check_one(app, cancelled=cancelled, force=force))
            except UpdateCancelled:
                break
            except Exception as exc:  # noqa: BLE001 - one app must not stop the scan
                results.append(self._candidate(
                    app, ERROR, reason=backend_error_reason(
                        app.get("format", "unknown"), exc)[:360]))
        return results
