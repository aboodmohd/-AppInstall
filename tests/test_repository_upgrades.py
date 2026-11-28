"""Repository upgrades: provenance, simulation, approval and recovery gates."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import container_backend as backend
import repository_upgrades as upgrades
import update_engine


def managed(kind="deb", name="gimp", version="3.0-1", method="repository"):
    container, image = backend.SPECS[kind]
    raw = {
        "kind": kind, "name": name, "version": version,
        "status": "installed", "architecture": "amd64" if kind == "deb" else "x86_64",
        "container": container, "image": image, "install_method": method,
        "exports": [], "desktop": "/usr/share/applications/gimp.desktop",
    }
    app = {
        "key": kind + ":" + name, "format": kind,
        "source": "container-registry", "version": version, "status": "installed",
        "name": name, "raw": raw.copy(),
    }
    return app, raw


def available(app, version="3.2-1"):
    return update_engine.UpdateCandidate(
        key=app["key"], format=app["format"], state=update_engine.AVAILABLE,
        installed_version=app["version"], available_version=version,
        source="Debian 13" if app["format"] == "deb" else "Fedora 44",
        mechanism="apt-repository" if app["format"] == "deb" else "dnf-repository",
        requires_review=True)


class RegistryFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Some integration suites import separate backend references before
        # these tests run. Isolate the real XDG registry path as well as the
        # module function mock, so import order cannot leak into ~/.local.
        self.root = Path(self.tmp.name) / "appinstall" / "containers"
        self.root.mkdir(parents=True)
        env = patch.dict(os.environ, {"XDG_DATA_HOME": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.mock_root = patch.object(backend, "state_dir", return_value=self.root)
        self.mock_root.start()
        self.addCleanup(self.mock_root.stop)

    def store(self, key, raw):
        (self.root / "registry.json").write_text(json.dumps({key: raw}))


class ProvenanceTests(RegistryFixture):
    def test_no_registry_record_fails_before_any_container_command(self):
        app, _ = managed()
        runner = Mock(side_effect=AssertionError("no subprocess should run"))
        with self.assertRaises(upgrades.UpgradeBlocked):
            upgrades.RepositoryUpgradeService(runner=runner).preview_update(app)
        runner.assert_not_called()

    def test_file_import_never_switches_to_a_repository(self):
        for fmt in ("deb", "rpm"):
            app, raw = managed(fmt, method="local-file")
            self.store(app["key"], raw)
            with self.subTest(fmt=fmt), self.assertRaises(upgrades.UpgradeBlocked):
                upgrades.RepositoryUpgradeService(runner=Mock()).preview_update(app)

    def test_foreign_source_or_changed_container_rejected(self):
        app, raw = managed("rpm")
        self.store(app["key"], raw)
        for change in ({"source": "launch-monitor"}, {"raw": {**raw, "image": "evil"}},
                       {"status": "needs-repair"}, {"version": "old"}):
            forged = {**app, **change}
            with self.subTest(change=change), self.assertRaises(upgrades.UpgradeBlocked):
                upgrades.RepositoryUpgradeService(runner=Mock()).preview_update(forged)

    def test_registry_changed_but_ui_has_stale_record(self):
        app, raw = managed()
        self.store(app["key"], {**raw, "version": "99"})
        with self.assertRaises(upgrades.UpgradeBlocked):
            upgrades.RepositoryUpgradeService(runner=Mock()).preview_update(app)


class ReviewTests(RegistryFixture):
    def setUp(self):
        super().setUp()
        self.app, raw = managed()
        self.store(self.app["key"], raw)
        self.service = upgrades.RepositoryUpgradeService(runner=Mock())

    def test_apt_review_only_exact_target_and_dependencies(self):
        sim = ("Reading package lists...\n"
               "The following packages will be upgraded:\n"
               "  gimp\n"
               "1 upgraded, 0 newly installed, 0 to remove.\n"
               "Inst gimp [3.0-1] (3.2-1 Debian:13/stable [amd64])\n"
               "Conf gimp (3.2-1 Debian:13/stable [amd64])\n")
        with patch.object(self.service, "_trusted_repositories"), \
             patch.object(upgrades, "UpdateEngine") as cls, \
             patch.object(self.service, "_enter", return_value=(0, sim)) as query:
            cls.return_value.check_one.return_value = available(self.app)
            plan = self.service.preview_update(self.app)
        self.assertEqual(plan.key, "deb:gimp")
        self.assertEqual(plan.target_version, "3.2-1")
        self.assertEqual(plan.package_spec, "gimp=3.2-1")
        self.assertEqual(plan.preview, sim)
        self.assertEqual(query.call_args.args,
                         ("deb", ["apt-get", "--simulate", "--no-remove",
                                  "--only-upgrade", "install", "gimp=3.2-1"]))
        cls.return_value.check_one.assert_called_once_with(self.app, force=True)

    def test_apt_blocks_removed_dependencies_and_replacement(self):
        sample = "Remv otherpkg [1.0]\nInst gimp [3.0-1] (3.2-1 repo)\n"
        with self.assertRaisesRegex(upgrades.UpgradeBlocked, "removal"):
            upgrades.RepositoryUpgradeService._parse_apt_preview(
                sample, "gimp", "3.2-1")
        for payload in ("Inst otherpkg [1] (3.2-1)\n", "Inst gimp [1] (2.0)\n"):
            with self.assertRaises(upgrades.UpgradeBlocked):
                upgrades.RepositoryUpgradeService._parse_apt_preview(
                    payload, "gimp", "3.2-1")

    def test_dnf_exact_spec_and_no_removals(self):
        app, raw = managed("rpm")
        self.store(app["key"], raw)
        sim = ("Upgrading:\n"
               " gimp x86_64 3.2-1 updates\n"
               "Transaction Summary\n"
               "Upgrading: 1 package\n"
               "Is this ok [y/N]: Operation aborted\n")
        with patch.object(self.service, "_trusted_repositories"), \
             patch.object(upgrades, "UpdateEngine") as cls, \
             patch.object(self.service, "_enter", return_value=(1, sim)) as query:
            cls.return_value.check_one.return_value = available(app)
            plan = self.service.preview_update(app)
        self.assertEqual(plan.package_spec, "gimp-3.2-1.x86_64")
        self.assertEqual(query.call_args.args,
                         ("rpm", ["dnf", "--assumeno",
                                  "--setopt=obsoletes=False",
                                  "upgrade", "gimp-3.2-1.x86_64"]))
        self.assertEqual(plan.kind, "rpm")

    def test_dnf_blocks_obsoletes_or_missing_preview(self):
        for text in ("Replacing:\n old-pkg\n", "Removing:\n libfoo\n",
                     "Downgrading:\n gimp\n"):
            with self.subTest(text=text), self.assertRaises(upgrades.UpgradeBlocked):
                upgrades.RepositoryUpgradeService._parse_dnf_preview(
                    text + "gimp 3.2-1 Transaction Summary\nOperation aborted\n",
                    "gimp", "3.2-1", 1)
        with self.assertRaises(upgrades.UpgradeBlocked):
            upgrades.RepositoryUpgradeService._parse_dnf_preview(
                "Nothing to do", "gimp", "3.2-1", 0)

    def test_invalid_versions_rejected(self):
        for version in ("1; sudo rm -rf /", "../hack", "", "--foo"):
            with self.subTest(version=version), self.assertRaises(upgrades.UpgradeBlocked):
                self.service._preview("deb", "gimp", "3.0-1", version, "amd64")

    def test_foreign_architecture_from_registry_is_rejected(self):
        with patch.object(upgrades.platform, "machine", return_value="aarch64"):
            for architecture in ("amd64", "x86_64", "unknown"):
                with self.subTest(architecture=architecture), \
                     self.assertRaises(upgrades.UpgradeBlocked):
                    self.service._preview("rpm", "gimp", "3.0-1", "3.2-1",
                                          architecture)

    def test_unknown_repositories_fail_closed(self):
        with patch.object(upgrades.repository_catalog, "ready", return_value=True), \
             patch.object(self.service, "_enter",
                          return_value=(0, "copr:somebody repo\n")):
            with self.assertRaises(upgrades.UpgradeBlocked):
                self.service._trusted_repositories("rpm")

    def test_apt_foreign_source_rejected(self):
        def query(kind, args, **kwargs):
            if args[0] == "find":
                return 0, "/etc/apt/sources.list.d/test.sources\n"
            return 0, "Types: deb\nURIs: https://example.com/repo\n"
        with patch.object(upgrades.repository_catalog, "ready", return_value=True), \
             patch.object(self.service, "_enter", side_effect=query):
            with self.assertRaises(RuntimeError):
                self.service._trusted_repositories("deb")


class FakeEngine:
    def __init__(self, registry):
        self.registry = registry
        self.saves = []
        self.closed = False

    def save(self):
        self.saves.append({key: dict(value) for key, value in self.registry.items()})

    def close(self):
        self.closed = True


class ApplyTests(RegistryFixture):
    def setUp(self):
        super().setUp()
        self.app, raw = managed()
        self.store(self.app["key"], raw)
        self.registry = {"deb:gimp": dict(raw)}
        self.engine = FakeEngine(self.registry)
        self.plan = upgrades.UpgradePlan(
            key="deb:gimp", kind="deb", name="gimp",
            container=backend.SPECS["deb"][0], image=backend.SPECS["deb"][1],
            installed_version="3.0-1", target_version="3.2-1",
            architecture="amd64", package_spec="gimp=3.2-1",
            preview="Inst gimp [3.0-1] (3.2-1)\n",
            preview_sha256="fake-plan-hash")
        self.svc = upgrades.RepositoryUpgradeService(
            runner=Mock(), engine_factory=lambda: self.engine)

    def test_apply_requires_identical_second_review(self):
        with patch.object(self.svc, "preview_update",
                          return_value=upgrades.UpgradePlan(
                              **{**self.plan.__dict__, "preview": "changed deps"})), \
             patch.object(self.svc, "_enter") as command:
            with self.assertRaisesRegex(upgrades.UpgradeBlocked, "changed"):
                self.svc.apply_update(self.plan, self.app)
        command.assert_not_called()
        self.assertEqual(self.registry["deb:gimp"]["status"], "installed")
        self.assertTrue(self.engine.closed)

    def test_success_pins_version_and_preserves_registry_exports(self):
        self.registry["deb:gimp"]["exports"] = []
        with patch.object(self.svc, "preview_update", return_value=self.plan), \
             patch.object(self.svc, "_enter", return_value=(0, "success")) as exec_cmd, \
             patch.object(self.svc, "_installed_version", return_value="3.2-1"):
            result = self.svc.apply_update(self.plan, self.app)
        self.assertEqual(result.status, "installed")
        self.assertEqual(result.version, "3.2-1")
        self.assertEqual(self.registry["deb:gimp"]["version"], "3.2-1")
        self.assertEqual(self.registry["deb:gimp"]["status"], "installed")
        self.assertTrue(self.engine.closed)
        self.assertEqual(exec_cmd.call_args.args, (
            "deb", ["sudo", "env", "DEBIAN_FRONTEND=noninteractive",
                    "apt-get", "--assume-yes", "--no-remove",
                    "--only-upgrade", "install", "gimp=3.2-1"]))

    def test_failed_container_command_marks_needs_repair(self):
        with patch.object(self.svc, "preview_update", return_value=self.plan), \
             patch.object(self.svc, "_enter", return_value=(100, "failed")), \
             patch.object(self.svc, "_installed_version") as verifier:
            with self.assertRaises(upgrades.UpgradeBlocked):
                self.svc.apply_update(self.plan, self.app)
        verifier.assert_not_called()
        self.assertEqual(self.registry["deb:gimp"]["status"], "needs-repair")
        self.assertTrue(self.engine.closed)

    def test_verification_mismatch_marks_needs_repair(self):
        with patch.object(self.svc, "preview_update", return_value=self.plan), \
             patch.object(self.svc, "_enter", return_value=(0, "installed")), \
             patch.object(self.svc, "_installed_version", return_value="3.1-1"):
            with self.assertRaises(upgrades.UpgradeBlocked):
                self.svc.apply_update(self.plan, self.app)
        self.assertEqual(self.registry["deb:gimp"]["status"], "needs-repair")

    def test_rpm_apply_only_selected_repo_package(self):
        app, raw = managed("rpm")
        self.store(app["key"], raw)
        engine = FakeEngine({"rpm:gimp": dict(raw)})
        spec = "gimp-3.2-1.x86_64"
        plan = upgrades.UpgradePlan(
            key=app["key"], kind="rpm", name="gimp",
            container=backend.SPECS["rpm"][0], image=backend.SPECS["rpm"][1],
            installed_version="3.0-1", target_version="3.2-1",
            architecture="x86_64", preview="Upgrading gimp",
            preview_sha256="sha", package_spec=spec)
        svc = upgrades.RepositoryUpgradeService(
            runner=Mock(), engine_factory=lambda: engine)
        with patch.object(svc, "preview_update", return_value=plan), \
             patch.object(svc, "_enter", return_value=(0, "ok")) as run, \
             patch.object(svc, "_installed_version", return_value="3.2-1"):
            svc.apply_update(plan, app)
        self.assertEqual(run.call_args.args, (
            "rpm", ["sudo", "dnf", "--assumeyes",
                    "--setopt=obsoletes=False", "upgrade", spec]))
        self.assertEqual(engine.registry["rpm:gimp"]["version"], "3.2-1")


if __name__ == "__main__":
    unittest.main()
