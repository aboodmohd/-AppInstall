"""AppImage v1.8 PR #4: source validation, staging, atomic swap and recovery."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import appimage_updates as u
import launch_monitor
import update_engine


INFO = "gh-releases-zsync|ExampleOrg|ExampleProject|latest|Example-*-x86_64.AppImage.zsync"


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.data = self.home / "share"
        self.root = self.data / "appinstall"
        self.root.mkdir(parents=True)
        self.apps = self.data / "applications"
        self.apps.mkdir()
        self.dest = self.home / "Applications"
        self.dest.mkdir()
        self.gen = self.dest / ".appinstall-managed123"
        self.gen.mkdir(mode=0o700)
        self.target = self.gen / "Example.AppImage"
        self.original = b"\x7fELF" + b"AI\x02" + b"o" * 2048
        self.new = b"\x7fELF" + b"AI\x02" + b"n" * 4096
        self.target.write_bytes(self.original)
        self.target.chmod(0o755)
        self.desktop = self.apps / "example.desktop"
        self.desktop.write_text("[Desktop Entry]\nType=Application\nName=Example\n")
        self.manifest = self.root / "ab123.json"
        self.manifest.write_text(json.dumps({
            "target": str(self.target), "generation": str(self.gen),
            "fallback": "", "args": [], "desktop_exec": "AppRun",
        }))
        self.raw = {"format": "appimage", "name": "Example",
                    "manifest": str(self.manifest), "desktop": str(self.desktop),
                    "status": "installed"}
        self.app = {"key": "appimage:ab123", "source": "launch-monitor",
                    "format": "appimage", "name": "Example", "version": "unknown",
                    "status": "installed", "target": str(self.target),
                    "raw": self.raw}
        self.patches = [
            patch.object(launch_monitor, "data_root", return_value=self.root),
            patch.object(launch_monitor, "registry",
                         return_value={"appimage:ab123": self.raw}),
            patch.object(u, "is_appimage", return_value=True),
            patch.object(u, "read_info", return_value=INFO),
            patch.object(u.shutil, "which", return_value="/usr/bin/updatertool"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)


class MetadataTests(unittest.TestCase):
    def test_gh_zsync_metadata_channel(self):
        self.assertEqual(u.validate_info(INFO), "GitHub Releases zsync")

    def test_gh_rejects_foreign_or_malformed_channels(self):
        invalid = [
            "gh-releases-zsync|owner|repo|latest",
            "gh-releases-zsync|../oops|repo|latest|App-*.AppImage.zsync",
            "gh-releases-zsync|owner|repo|latest|../../unsafe.AppImage.zsync",
            "gh-releases-zsync|owner|repo|latest|app.AppImage",
            "gh-releases-zsync|owner|repo|latest|app.AppImage.zsync|extra",
            "gh-releases-zsync|owner|repo|latest|app ; rm -rf *.AppImage.zsync",
            "file:///tmp/local.zsync",
            "https://example.com/file",
            "zsync|http://example.com/download.zsync",
            "zsync|https://127.0.0.1/down.zsync",
            "zsync|https://example.com/down.zsync#redirect",
            "zsync|https://example.com/down.zsync?token=secret",
        ]
        for info in invalid:
            with self.subTest(info=info), self.assertRaises(u.AppImageUpdateBlocked):
                u.validate_info(info, resolve=False)

    def test_valid_https_zsync_format_and_url_validation(self):
        info = "zsync|https://example.org/releases/Example.AppImage.zsync"
        with patch.object(u, "validate_url") as web:
            self.assertEqual(u.validate_info(info), "zsync")
        web.assert_called_once_with("https://example.org/releases/Example.AppImage.zsync")

    def test_duplicate_embedded_metadata_is_not_trusted(self):
        same = "[ 1] " + INFO + "\n[ 2] " + INFO
        self.assertEqual(u.parse_update_info(same), INFO)
        different = same + "\n[ 3] zsync|https://example.com/app.zsync"
        self.assertIsNone(u.parse_update_info(different))

    def test_check_exit_one_means_available_zero_means_current(self):
        with patch.object(u.shutil, "which", return_value="/bin/appimageupdatetool"):
            for code, expected in [(0, False), (1, True)]:
                calls = []
                def runner(args, **kwargs):
                    calls.append(args)
                    return subprocess.CompletedProcess(args, code, "", "")
                self.assertEqual(u.check_upstream("/tmp/App.AppImage", runner), expected)
                self.assertEqual(
                    calls, [["appimageupdatetool", "--check-for-update",
                             "--", "/tmp/App.AppImage"]])

    def test_check_return_error_not_treated_as_available(self):
        with patch.object(u.shutil, "which", return_value="/bin/appimageupdatetool"):
            run = lambda args, **kwargs: subprocess.CompletedProcess(args, 2, "", "offline")
            with self.assertRaisesRegex(u.AppImageUpdateBlocked, "code 2"):
                u.check_upstream("/tmp/app.AppImage", run)


class StageAndCommitTests(Fixture):
    def runner(self, args, **kw):
        if args[:2] == ["appimageupdatetool", "--check-for-update"]:
            return subprocess.CompletedProcess(args, 1, "", "")
        if args[:2] == ["appimageupdatetool", "--overwrite"]:
            staged = Path(args[-1])
            self.assertNotEqual(staged, self.target)
            self.assertTrue(staged.parent.name.startswith(".appinstall-update-"))
            staged.write_bytes(self.new)
            return subprocess.CompletedProcess(args, 0, "100%", "")
        raise AssertionError("Unexpected subprocess: " + repr(args))

    def expected(self):
        return update_engine.UpdateCandidate(
            key=self.app["key"], format="appimage", state="available",
            mechanism="appimage-zsync", reference=INFO,
            installed_revision=u.sha256_file(self.target),
            available_version="New upstream build", requires_review=True)

    def test_managed_identity_is_verified(self):
        target, manifest = u.verify_owned(self.app)
        self.assertEqual(target, self.target)
        self.assertEqual(manifest, self.manifest)

    def test_unmanaged_or_changed_registry_refused(self):
        for change in (
            {"source": "foreign"},
            {"status": "needs-repair"},
            {"raw": {**self.raw, "manifest": "/tmp/not-owned.json"}},
            {"key": "appimage:other"},
            {"target": str(self.home / "unrelated.AppImage")},
        ):
            with self.subTest(change=change), self.assertRaises(u.AppImageUpdateBlocked):
                u.verify_owned({**self.app, **change})

    def test_symlinked_target_and_unowned_generation_refused(self):
        self.target.unlink()
        other = self.home / "Other.AppImage"
        other.write_bytes(self.original)
        self.target.symlink_to(other)
        with self.assertRaises(u.AppImageUpdateBlocked):
            u.verify_owned(self.app)

    def test_stage_and_atomic_swap_preserve_manifest_launcher_and_backup(self):
        service = u.AppImageUpgradeService(runner=self.runner)
        old_manifest = self.manifest.read_bytes()
        old_desktop = self.desktop.read_bytes()
        plan = service.prepare(self.app, self.expected())
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual(Path(plan.staged_file).read_bytes(), self.new)
        self.assertEqual(plan.original_sha256, u.sha256_file(self.target))
        self.assertEqual(plan.candidate_size, len(self.new))
        self.assertEqual(plan.update_information, INFO)
        self.assertTrue(Path(plan.staging).is_dir())
        result = service.apply(plan, self.app)
        self.assertEqual(self.target.read_bytes(), self.new)
        self.assertEqual(Path(result.backup).read_bytes(), self.original)
        self.assertFalse(Path(plan.staging).exists())
        self.assertEqual(self.manifest.read_bytes(), old_manifest)
        self.assertEqual(self.desktop.read_bytes(), old_desktop)
        self.assertEqual(self.target.stat().st_mode & 0o111, 0o111)

    def test_declined_review_cleanup_keeps_original(self):
        service = u.AppImageUpgradeService(runner=self.runner)
        plan = service.prepare(self.app, self.expected())
        u.cleanup_plan(plan)
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertFalse(Path(plan.staging).exists())

    def test_stale_original_digest_rejected_without_replacement(self):
        service = u.AppImageUpgradeService(runner=self.runner)
        plan = service.prepare(self.app, self.expected())
        self.target.write_bytes(self.original + b"changed")
        with self.assertRaisesRegex(u.AppImageUpdateBlocked, "changed"):
            service.apply(plan, self.app)
        self.assertEqual(self.target.read_bytes(), self.original + b"changed")
        u.cleanup_plan(plan)

    def test_stale_scan_revision_refused_without_download(self):
        service = u.AppImageUpgradeService(runner=self.runner)
        wrong = update_engine.UpdateCandidate(
            **{**self.expected().to_dict(), "installed_revision": "a" * 64})
        with self.assertRaisesRegex(u.AppImageUpdateBlocked, "changed"):
            service.prepare(self.app, wrong)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_failed_download_leaves_installed_image_unchanged(self):
        def fail(args, **kwargs):
            if "--check-for-update" in args:
                return subprocess.CompletedProcess(args, 1, "", "")
            return subprocess.CompletedProcess(args, 2, "", "network failure")
        with self.assertRaisesRegex(u.AppImageUpdateBlocked, "updater failed"):
            u.AppImageUpgradeService(runner=fail).prepare(self.app, self.expected())
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual(list(self.gen.glob(".appinstall-update-*")), [])

    def test_rewritten_update_channel_is_rejected(self):
        def fake_info(path, *args):
            return INFO if Path(path) == self.target else (
                "gh-releases-zsync|Different|App|latest|App-*.AppImage.zsync")
        with patch.object(u, "read_info", side_effect=fake_info):
            with self.assertRaisesRegex(u.AppImageUpdateBlocked, "changed its update channel"):
                u.AppImageUpgradeService(runner=self.runner).prepare(self.app, self.expected())
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_installed_check_exposes_only_trusted_owned_image(self):
        with patch.object(u, "read_info", return_value=INFO), \
             patch.object(u, "check_upstream", return_value=True), \
             patch.object(u, "sha256_file", wraps=u.sha256_file):
            engine = update_engine.UpdateEngine(runner=lambda *args, **kwargs: None)
            result = engine.check_one(self.app, force=True)
        self.assertEqual(result.state, update_engine.AVAILABLE)
        self.assertEqual(result.mechanism, "appimage-zsync")
        self.assertEqual(result.reference, INFO)
        self.assertEqual(result.installed_revision, u.sha256_file(self.target))
        self.assertTrue(result.requires_review)


if __name__ == "__main__":
    unittest.main()
