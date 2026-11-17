"""Review-first DEB/RPM upgrades inside existing AppInstall-owned Distroboxes.

Never update a host package, refresh a repository, create a container, infer a
repository for a local package file, or run a command from user-controlled text.
An update must have a fresh plan, an explicit GUI approval, and a second matching
plan under the registry operation lock immediately before applying it.

This module deliberately does not use Engine.ensure(), which can create/update
containers, or operate on packages outside the AppInstall registry.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess

import container_backend as backend
import repository_catalog
from update_engine import AVAILABLE, UpdateEngine, _package_identity

PREVIEW_TIMEOUT = 150
APPLY_TIMEOUT = 900
MAX_OUTPUT = 96 * 1024
VERSION_RE = re.compile(r"[0-9][A-Za-z0-9._+~:^:-]{0,159}\Z")
REMOVE_RE = re.compile(
    r"(?im)^\s*(?:Remv|Purg|Removing(?:\s+dependent\s+packages)?|"
    r"Obsoleting|Replacing|Downgrading)\b")
APT_INSTALL_RE = re.compile(r"(?m)^Inst\s+([A-Za-z0-9][A-Za-z0-9+_.-]*)\s+")
DNF_REVIEW_RE = re.compile(r"(?im)^\s*(?:Upgrading|Transaction Summary)\s*:?")
DNF_ABORT_RE = re.compile(r"(?i)Operation aborted|Is this ok|Operation cancelled")


class UpgradeBlocked(RuntimeError):
    """No upgrade was started (or a change was not verified)."""


@dataclass(frozen=True)
class UpgradePlan:
    key: str
    kind: str
    name: str
    container: str
    image: str
    installed_version: str
    target_version: str
    architecture: str
    preview: str
    preview_sha256: str
    package_spec: str


@dataclass(frozen=True)
class UpgradeResult:
    key: str
    version: str
    status: str
    message: str
    output: str = ""


def _name_and_record(app):
    if not isinstance(app, dict) or app.get("format") not in ("deb", "rpm"):
        raise UpgradeBlocked("Only managed DEB/RPM applications support repository updates.")
    kind = app["format"]
    name = _package_identity(app, kind)
    if not name or app.get("source") != "container-registry":
        raise UpgradeBlocked("Imported or unverified package: provide a new reviewed file instead.")
    if app.get("status") != "installed":
        raise UpgradeBlocked("Repair the managed application before updating it.")
    registry_file = backend.state_dir() / "registry.json"
    try:
        root = json.loads(registry_file.read_text(encoding="utf-8"))
        record = root[kind + ":" + name]
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise UpgradeBlocked("Managed container registry is missing or invalid.") from exc
    if not isinstance(root, dict) or not isinstance(record, dict):
        raise UpgradeBlocked("Invalid managed application registry record.")
    container, image = backend.SPECS[kind]
    if (record.get("status") != "installed"
            or record.get("kind") != kind or record.get("name") != name
            or record.get("container") != container
            or record.get("image") != image
            or record.get("install_method") != "repository"):
        raise UpgradeBlocked("Registered package origin, container or state changed.")
    if (record.get("version") != app.get("version")
            or app.get("raw") != record):
        raise UpgradeBlocked("Managed application record changed; refresh before updating.")
    return kind, name, record


class RepositoryUpgradeService:
    """All commands use the explicitly registered Distrobox and argv arrays."""

    def __init__(self, runner=None, engine_factory=None):
        self.runner = runner if runner is not None else subprocess.run
        self.engine_factory = engine_factory if engine_factory is not None else backend.Engine

    def _enter(self, kind, args, *, allowed_abort=False, timeout=PREVIEW_TIMEOUT):
        container = backend.SPECS[kind][0]
        argv = ["distrobox", "enter", "--name", container, "--no-tty", "--", *args]
        try:
            result = self.runner(argv, env=dict(backend.ENV), capture_output=True,
                                 text=True, errors="replace", timeout=timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            raise UpgradeBlocked("Distrobox command failed: " + str(exc)) from exc
        out = (result.stdout or "") + (result.stderr or "")
        if len(out) > MAX_OUTPUT:
            raise UpgradeBlocked("Package manager output exceeds the review limit.")
        if result.returncode and not allowed_abort:
            raise UpgradeBlocked("Container command failed: " + out[-1200:])
        return result.returncode, out

    def _trusted_repositories(self, kind):
        """Read-only check of the same repository allowlist used by setup."""
        if not repository_catalog.ready(kind):
            raise UpgradeBlocked("The AppInstall-owned container is not prepared.")
        if kind == "deb":
            _, files = self._enter(
                kind, ["find", "/etc/apt", "-maxdepth", "2", "-type", "f"])
            known = [line.strip() for line in files.splitlines()
                     if line.startswith("/etc/apt/")
                     and line.endswith((".sources", ".list"))]
            if not known:
                raise UpgradeBlocked("No verifiable Debian sources found.")
            for file in known:
                _, source = self._enter(kind, ["cat", file])
                backend.validate_apt_sources(source)
        else:
            _, output = self._enter(kind, ["dnf", "repolist", "--enabled"])
            ids = [line.split()[0] for line in output.splitlines()
                   if line.strip() and not line.lower().startswith(
                       ("repo id", "updating", "repositories"))]
            if not ids or any(i not in ("fedora", "updates", "fedora-cisco-openh264")
                              for i in ids):
                raise UpgradeBlocked(
                    "Fedora repository configuration changed; inspect it manually.")

    @staticmethod
    def _parse_apt_preview(output, name, version):
        if REMOVE_RE.search(output):
            raise UpgradeBlocked("APT proposes removal or replacement of a package; update blocked.")
        upgraded = APT_INSTALL_RE.findall(output)
        if name not in upgraded or version not in output:
            raise UpgradeBlocked("APT preview did not include the requested exact upgrade.")
        return output

    @staticmethod
    def _parse_dnf_preview(output, name, version, code):
        if REMOVE_RE.search(output):
            raise UpgradeBlocked("DNF proposes removal, replacement or downgrade; update blocked.")
        if (not DNF_REVIEW_RE.search(output) or not DNF_ABORT_RE.search(output)
                or name not in output or version not in output
                or code not in (0, 1)):
            raise UpgradeBlocked("DNF could not produce a trustworthy aborted upgrade preview.")
        return output

    def _preview(self, kind, name, installed, target, architecture):
        if (not VERSION_RE.fullmatch(target) or
                not VERSION_RE.fullmatch(installed)):
            raise UpgradeBlocked("Invalid package version in update metadata.")
        if kind == "deb":
            spec = name + "=" + target
            argv = ["apt-get", "--simulate", "--no-remove",
                    "--only-upgrade", "install", spec]
            code, output = self._enter(kind, argv)
            if code:
                raise UpgradeBlocked("APT simulation failed.")
            self._parse_apt_preview(output, name, target)
        else:
            if not re.fullmatch(r"(x86_64|aarch64|noarch)", architecture):
                raise UpgradeBlocked("Fedora package architecture is unknown.")
            spec = name + "-" + target + "." + architecture
            argv = ["dnf", "--assumeno", "--setopt=obsoletes=False",
                    "upgrade", spec]
            code, output = self._enter(kind, argv, allowed_abort=True)
            self._parse_dnf_preview(output, name, target, code)
        return spec, output

    def preview_update(self, app):
        """Never writes registry or packages. Fails closed on stale provenance."""
        kind, name, record = _name_and_record(app)
        self._trusted_repositories(kind)
        # This is a NEW engine and force=True: do not trust the UI's stale cache.
        scan = UpdateEngine(runner=self.runner).check_one(app, force=True)
        if scan.state != AVAILABLE or scan.format != kind:
            raise UpgradeBlocked("Fresh repository scan has no verified upgrade: "
                                 + scan.reason)
        target, installed = scan.available_version, scan.installed_version
        if installed != record["version"]:
            raise UpgradeBlocked("Installed version changed; restart the update review.")
        spec, preview = self._preview(kind, name, installed, target,
                                      record.get("architecture", ""))
        return UpgradePlan(
            key=app["key"], kind=kind, name=name,
            container=record["container"], image=record["image"],
            installed_version=installed, target_version=target,
            architecture=record.get("architecture", ""),
            preview=preview, preview_sha256=hashlib.sha256(
                preview.encode("utf-8")).hexdigest(), package_spec=spec)

    def _installed_version(self, plan):
        if plan.kind == "deb":
            _, output = self._enter(
                "deb", ["apt-cache", "policy", plan.name])
            from update_engine import UpdateEngine
            version, _ = UpdateEngine._deb_policy(output, plan.name)
            return version
        _, output = self._enter(
            "rpm", ["rpm", "-q", "--qf",
                    "%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\\n", plan.name])
        # RPM expands the literal newline escape in --qf.
        rows = [line.split("\t") for line in output.splitlines()]
        matches = [row[1] for row in rows if len(row) == 3
                   and row[0] == plan.name and row[2] == plan.architecture]
        if len(matches) != 1:
            raise UpgradeBlocked("RPM cannot verify installed version after upgrade.")
        return matches[0]

    def apply_update(self, plan, app, progress=None):
        """Called only AFTER explicit user approval on a worker thread.

        Holds AppInstall's registry lock through the operation. A changed plan
        aborts BEFORE any sudo command. Failure after the install begins keeps
        the registry in needs-repair, and never erases launcher ownership.
        """
        if not isinstance(plan, UpgradePlan) or not isinstance(app, dict):
            raise UpgradeBlocked("Missing reviewed update transaction.")
        notify = progress or (lambda _: None)
        engine = self.engine_factory()
        started = False
        record = None
        try:
            kind, name, _ = _name_and_record(app)
            if (kind != plan.kind or name != plan.name
                    or plan.key != app["key"]):
                raise UpgradeBlocked("Update target changed; inspect again.")
            record = engine.registry.get(plan.key)
            if (not isinstance(record, dict) or record.get("status") != "installed"
                    or record.get("version") != plan.installed_version
                    or record.get("install_method") != "repository"):
                raise UpgradeBlocked("Registry changed since preview; no update started.")
            notify("Rechecking package provenance and dependency transaction…")
            fresh = self.preview_update(app)
            if fresh != plan:
                raise UpgradeBlocked("Update candidate or dependency preview changed. "
                                     "No packages were changed; review again.")
            # Engine owns the per-container registry lock until completion.
            engine.registry[plan.key]["status"] = "updating"
            engine.save()
            started = True
            if kind == "deb":
                cmd = ["sudo", "env", "DEBIAN_FRONTEND=noninteractive",
                       "apt-get", "--assume-yes", "--no-remove", "--only-upgrade",
                       "install", plan.package_spec]
            else:
                cmd = ["sudo", "dnf", "--assumeyes",
                       "--setopt=obsoletes=False", "upgrade", plan.package_spec]
            notify("Applying approved " + kind.upper() +
                   " package update in " + plan.container + "…")
            code, output = self._enter(kind, cmd, allowed_abort=True,
                                       timeout=APPLY_TIMEOUT)
            if code:
                raise UpgradeBlocked("Container upgrade failed: " + output[-1200:])
            notify("Verifying installed package version and managed launchers…")
            actual = self._installed_version(plan)
            if actual != plan.target_version:
                raise UpgradeBlocked(
                    "Package manager completed, but installed version differs: " + actual)
            # Do not delete or blindly regenerate user desktop launchers.
            for item in record.get("exports", []):
                if not isinstance(item, dict) or not Path(item.get("path", "")).is_file():
                    raise UpgradeBlocked(
                        "An AppInstall-owned launcher is missing; repair is required.")
            engine.registry[plan.key]["version"] = actual
            engine.registry[plan.key]["status"] = "installed"
            engine.registry[plan.key]["last_upgrade_version"] = actual
            engine.save()
            return UpgradeResult(
                key=plan.key, version=actual, status="installed",
                message="Verified package update. AppInstall-managed launchers preserved.",
                output=output[-4000:])
        except BaseException as exc:
            if started and record is not None and plan.key in engine.registry:
                engine.registry[plan.key]["status"] = "needs-repair"
                engine.registry[plan.key]["last_upgrade_error"] = str(exc)[:500]
                engine.save()
            raise
        finally:
            engine.close()
