"""v1.8 Phase 1 update discovery — mocked, side-effect-free provider tests."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import update_engine as updates
import container_backend as backend


def app(fmt="flatpak", name="org.example.App", **extra):
    raw = {"appid": name} if fmt == "flatpak" else {}
    raw.update(extra.pop("raw", {}))
    return {
        "key": fmt + ":" + name, "format": fmt, "name": name,
        "version": extra.pop("version", "1.0"), "status": "installed",
        "raw": raw, **extra,
    }


def repository_app(kind, name="gimp", **extra):
    container, image = backend.SPECS[kind]
    raw = dict(kind=kind, name=name, container=container,
               image=image, install_method="repository")
    raw.update(extra.pop("raw", {}))
    return app(kind, name, raw=raw, **extra)


class FakeRunner:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, argv, **kwargs):
        argv = list(argv)
        self.calls.append((argv, kwargs))
        key = tuple(argv)
        if key not in self.responses:
            raise AssertionError("Unexpected or dangerous subprocess: " + repr(argv))
        result = self.responses[key]
        if isinstance(result, Exception):
            raise result
        if isinstance(result, int):
            return subprocess.CompletedProcess(argv, result, "", "")
        if isinstance(result, tuple):
            out, rc = result
            return subprocess.CompletedProcess(argv, rc, out, "simulated error" if rc else "")
        return subprocess.CompletedProcess(argv, 0, result, "")


def container(kind, command):
    return tuple(["distrobox", "enter", "--name", backend.SPECS[kind][0],
                  "--no-tty", "--", *command])


class CandidateTests(unittest.TestCase):
    def test_candidate_serializes_with_stable_schema(self):
        c = updates.UpdateCandidate("flatpak:a", "flatpak", updates.UP_TO_DATE)
        self.assertEqual(c.to_dict()["state"], "up-to-date")
        self.assertEqual(c.to_dict()["available_version"], "")
        self.assertFalse(c.requires_review)

    def test_unsupported_and_missing_apps_have_no_side_effects(self):
        run = FakeRunner({})
        engine = updates.UpdateEngine(runner=run)
        x = engine.check_one(app("snap", "test"))
        self.assertEqual(x.state, updates.UNSUPPORTED)
        self.assertEqual(run.calls, [])
        broken = app()
        broken["status"] = "needs-repair"
        self.assertEqual(engine.check_one(broken).state, updates.ERROR)
        self.assertEqual(run.calls, [])

    def test_cache_and_force_refresh(self):
        origin = "flathub"
        ident = "org.example.App"
        ref = "app/org.example.App/x86_64/stable"
        responses = {
            ("flatpak", "info", "--user", "--show-ref", ident): ref,
            ("flatpak", "info", "--user", "--show-origin", ref): origin,
            ("flatpak", "info", "--user", "--show-commit", ref): "a" * 64,
            ("flatpak", "remote-info", "--user", "--show-commit", origin, ref): "a" * 64,
        }
        now = [100.0]
        run = FakeRunner(responses)
        engine = updates.UpdateEngine(runner=run, clock=lambda: now[0], ttl=900)
        a = app()
        self.assertEqual(engine.check_one(a).state, updates.UP_TO_DATE)
        self.assertEqual(len(run.calls), 4)
        engine.check_one(a)
        self.assertEqual(len(run.calls), 4)
        engine.check_one(a, force=True)
        self.assertEqual(len(run.calls), 8)
        now[0] += 901
        engine.check_one(a)
        self.assertEqual(len(run.calls), 12)

    def test_check_many_cancels_before_next_application(self):
        run = FakeRunner({})
        engine = updates.UpdateEngine(runner=run)
        total = [0]
        def cancel():
            total[0] += 1
            return total[0] > 1
        self.assertEqual(engine.check_many([app("snap", "one"), app("snap", "two")],
                                            cancelled=cancel), [])
        self.assertEqual(run.calls, [])

    def test_bounded_subprocess_timeout_and_no_shell(self):
        run = FakeRunner({("flatpak", "info", "--user", "--show-ref",
                            "org.example.App"): subprocess.TimeoutExpired("flatpak", 10)})
        eng = updates.UpdateEngine(runner=run)
        self.assertEqual(eng.check_one(app()).state, updates.ERROR)
        self.assertFalse(run.calls[0][1].get("shell", False))
        self.assertLessEqual(run.calls[0][1]["timeout"], 30)


class FlatpakUpdateTests(unittest.TestCase):
    ID = "org.example.App"
    REF = "app/org.example.App/x86_64/stable"

    def responses(self, upstream):
        return {
            ("flatpak", "info", "--user", "--show-ref", self.ID): self.REF,
            ("flatpak", "info", "--user", "--show-origin", self.REF): "flathub",
            ("flatpak", "info", "--user", "--show-commit", self.REF): "a" * 64,
            ("flatpak", "remote-info", "--user", "--show-commit",
             "flathub", self.REF): upstream,
        }

    def test_available_commit_is_reported_without_installing(self):
        run = FakeRunner(self.responses("b" * 64))
        value = updates.UpdateEngine(runner=run).check_one(app())
        self.assertEqual(value.state, updates.AVAILABLE)
        self.assertEqual(value.mechanism, "flatpak-ref")
        self.assertEqual(value.source, "flathub")
        self.assertEqual(value.available_version, "b" * 12)
        self.assertTrue(value.requires_review)
        self.assertEqual(len(run.calls), 4)
        self.assertFalse(any("install" in " ".join(cmd) or "update" in cmd
                             for cmd, _ in run.calls))

    def test_matching_commit_reports_up_to_date(self):
        run = FakeRunner(self.responses("a" * 64))
        value = updates.UpdateEngine(runner=run).check_one(app())
        self.assertEqual(value.state, updates.UP_TO_DATE)
        self.assertFalse(value.requires_review)

    def test_missing_or_forged_flatpak_identity_never_runs(self):
        for raw in ({"appid": "bad-app"}, {"appid": "--system"},
                    {"appid": "org.example.Wrong"}):
            runner = FakeRunner({})
            value = updates.UpdateEngine(runner=runner).check_one(app(raw=raw))
            self.assertEqual(value.state, updates.MANUAL_REQUIRED)
            self.assertEqual(runner.calls, [])

    def test_remote_and_reference_must_match_installed_identity(self):
        for index, payload in (
            (0, "runtime/org.example.App/x86_64/stable"),
            (0, "app/org.example.Other/x86_64/stable"),
            (1, "../../unsafe"),
            (2, "bad-commit"),
        ):
            responses = self.responses("b" * 64)
            target = list(responses)[index]
            responses[target] = payload
            value = updates.UpdateEngine(runner=FakeRunner(responses)).check_one(app())
            self.assertEqual(value.state, updates.ERROR)

    def test_offline_is_an_error_not_false_up_to_date(self):
        responses = self.responses("b" * 64)
        last = ("flatpak", "remote-info", "--user", "--show-commit",
                "flathub", self.REF)
        responses[last] = ("", 1)
        value = updates.UpdateEngine(runner=FakeRunner(responses)).check_one(app())
        self.assertEqual(value.state, updates.ERROR)
        self.assertIn("query failed", value.reason)


class DebianUpdateTests(unittest.TestCase):
    PKG = "gimp"
    POLICY = "gimp:\n  Installed: 3.0-1\n  Candidate: 3.1-1\n  Version table:\n"

    def test_repository_installs_use_apt_policy_and_dpkg_comparison(self):
        a = repository_app("deb", version="3.0-1")
        query = container("deb", ["apt-cache", "policy", self.PKG])
        compare = container("deb", ["dpkg", "--compare-versions", "3.0-1",
                                     "lt", "3.1-1"])
        run = FakeRunner({query: self.POLICY, compare: 0})
        with patch.object(updates.repository_catalog, "ready", return_value=True):
            value = updates.UpdateEngine(runner=run).check_one(a)
        self.assertEqual(value.state, updates.AVAILABLE)
        self.assertEqual(value.installed_version, "3.0-1")
        self.assertEqual(value.available_version, "3.1-1")
        self.assertEqual(value.source, "Debian 13")
        self.assertTrue(value.requires_review)
        self.assertEqual(len(run.calls), 2)
        self.assertTrue(all("--" in argv for argv, _ in run.calls))
        self.assertFalse(any("sudo" in argv for argv, _ in run.calls))

    def test_false_version_comparison_is_a_normal_up_to_date_result(self):
        a = repository_app("deb", version="3.0-1")
        query = container("deb", ["apt-cache", "policy", "gimp"])
        compare = container("deb", ["dpkg", "--compare-versions", "3.0-1", "lt", "3.1-1"])
        run = FakeRunner({query: self.POLICY, compare: 1})
        with patch.object(updates.repository_catalog, "ready", return_value=True):
            value = updates.UpdateEngine(runner=run).check_one(a)
        self.assertEqual(value.state, updates.UP_TO_DATE)

    def test_imported_deb_cannot_be_silently_switched_to_apt(self):
        run = FakeRunner({})
        value = updates.UpdateEngine(runner=run).check_one(app("deb", "gimp"))
        self.assertEqual(value.state, updates.MANUAL_REQUIRED)
        self.assertEqual(run.calls, [])

    def test_forged_container_image_is_not_considered_an_official_source(self):
        a = repository_app("deb", raw={"image": "example/unknown:latest"})
        run = FakeRunner({})
        value = updates.UpdateEngine(runner=run).check_one(a)
        self.assertEqual(value.state, updates.MANUAL_REQUIRED)
        self.assertEqual(run.calls, [])

    def test_unprepared_container_cannot_be_created_by_read_only_scan(self):
        a = repository_app("deb", version="3.0-1")
        run = FakeRunner({})
        with patch.object(updates.repository_catalog, "ready", return_value=False), \
             patch.object(backend, "Engine") as engine:
            value = updates.UpdateEngine(runner=run).check_one(a)
        self.assertEqual(value.state, updates.ERROR)
        engine.assert_not_called()
        self.assertEqual(run.calls, [])

    def test_unexpected_installed_version_is_error(self):
        a = repository_app("deb", version="7.5")
        run = FakeRunner({container("deb", ["apt-cache", "policy", "gimp"]): self.POLICY})
        with patch.object(updates.repository_catalog, "ready", return_value=True):
            value = updates.UpdateEngine(runner=run).check_one(a)
        self.assertEqual(value.state, updates.ERROR)
        self.assertIn("differs", value.reason)

    def test_candidate_none_is_manual_required(self):
        a = repository_app("deb", version="3.0-1")
        policy = "gimp:\n  Installed: 3.0-1\n  Candidate: (none)\n"
        run = FakeRunner({container("deb", ["apt-cache", "policy", "gimp"]): policy})
        with patch.object(updates.repository_catalog, "ready", return_value=True):
            result = updates.UpdateEngine(runner=run).check_one(a)
        self.assertEqual(result.state, updates.MANUAL_REQUIRED)


class FedoraUpdateTests(unittest.TestCase):
    def test_dnf5_upgrades_are_separated_and_exact(self):
        a = repository_app("rpm", version="3.0-1")
        rpm = container("rpm", ["rpm", "-q", "--qf",
                                 "%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\n", "gimp"])
        dnf = container("rpm", ["dnf", "repoquery", "--upgrades", "--latest-limit=1",
                                 "--queryformat=%{name}\t%{version}-%{release}\t%{arch}\\n", "gimp"])
        run = FakeRunner({rpm: "gimp\t3.0-1\tx86_64\n",
                          dnf: "gimp\t3.1-1\tx86_64\n"})
        with patch.object(updates.repository_catalog, "ready", return_value=True):
            result = updates.UpdateEngine(runner=run).check_one(a)
        self.assertEqual(result.state, updates.AVAILABLE)
        self.assertEqual(result.available_version, "3.1-1")
        self.assertTrue(dnf[-2].endswith("\\n"))
        self.assertNotIn("sudo", str(run.calls))

    def test_dnf5_no_upgrades_means_up_to_date(self):
        a = repository_app("rpm", version="3.0-1")
        rpm = container("rpm", ["rpm", "-q", "--qf",
                                 "%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\n", "gimp"])
        dnf = container("rpm", ["dnf", "repoquery", "--upgrades", "--latest-limit=1",
                                 "--queryformat=%{name}\t%{version}-%{release}\t%{arch}\\n", "gimp"])
        run = FakeRunner({rpm: "gimp\t3.0-1\tx86_64\n", dnf: ""})
        with patch.object(updates.repository_catalog, "ready", return_value=True):
            result = updates.UpdateEngine(runner=run).check_one(a)
        self.assertEqual(result.state, updates.UP_TO_DATE)

    def test_imported_rpm_and_changed_identity_are_manual_required(self):
        run = FakeRunner({})
        engine = updates.UpdateEngine(runner=run)
        self.assertEqual(engine.check_one(app("rpm", "gimp")).state, updates.MANUAL_REQUIRED)
        a = repository_app("rpm", raw={"container": "foreign"})
        self.assertEqual(engine.check_one(a).state, updates.MANUAL_REQUIRED)
        self.assertEqual(run.calls, [])

    def test_changed_installed_version_needs_manual_review(self):
        a = repository_app("rpm", version="2.0-1")
        rpm = container("rpm", ["rpm", "-q", "--qf",
                                 "%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\n", "gimp"])
        run = FakeRunner({rpm: "gimp\t3.0-1\tx86_64\n"})
        with patch.object(updates.repository_catalog, "ready", return_value=True):
            value = updates.UpdateEngine(runner=run).check_one(a)
        self.assertEqual(value.state, updates.ERROR)


class AppImageUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.target = Path(self.temp.name) / "Example.AppImage"
        self.target.write_bytes(b"\x7fELF" + b"\0" * 128)

    def tearDown(self):
        self.temp.cleanup()

    def test_passive_embedded_zsync_detection_does_not_claim_available(self):
        a = app("appimage", "example", target=str(self.target))
        read = ("readelf", "--string-dump=.upd_info", str(self.target))
        run = FakeRunner({read: "String dump of section '.upd_info':\n[ 0] zsync|https://example.org/app.zsync\n"})
        with patch.object(updates.shutil, "which", return_value="/usr/bin/readelf"):
            result = updates.UpdateEngine(runner=run).check_one(a)
        self.assertEqual(result.state, updates.MANUAL_REQUIRED)
        self.assertEqual(result.mechanism, "appimage-upd-info")
        self.assertEqual(run.calls[0][0][0], "readelf")
        self.assertFalse(result.requires_review)

    def test_without_embedded_update_info_requires_manual_review(self):
        a = app("appimage", "example", target=str(self.target))
        run = FakeRunner({("readelf", "--string-dump=.upd_info",
                           str(self.target)): ("", 1)})
        with patch.object(updates.shutil, "which", return_value="/usr/bin/readelf"):
            result = updates.UpdateEngine(runner=run).check_one(a)
        self.assertEqual(result.state, updates.MANUAL_REQUIRED)
        self.assertFalse(result.requires_review)

    def test_missing_or_symlinked_appimage_is_not_scanned(self):
        symlink = self.target.parent / "Other.AppImage"
        symlink.symlink_to(self.target)
        run = FakeRunner({})
        engine = updates.UpdateEngine(runner=run)
        self.assertEqual(engine.check_one(app("appimage", "missing",
                         target="/nonexistent/app.AppImage")).state, updates.MANUAL_REQUIRED)
        self.assertEqual(engine.check_one(app("appimage", "other",
                         target=str(symlink))).state, updates.MANUAL_REQUIRED)
        self.assertEqual(run.calls, [])


if __name__ == "__main__":
    unittest.main()
