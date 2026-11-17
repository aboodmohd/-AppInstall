"""Offline security and transaction tests for portable self-update on Linux."""
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import portable_update as portable


def stable(version="1.8.1"):
    tag = "v" + version
    archive = "appinstall-" + version + "-portable.tar.gz"
    return {
        "tag_name": tag, "draft": False, "prerelease": False,
        "assets": [
            {"name": archive, "size": 500,
             "browser_download_url":
             "https://github.com/aboodmohd/-AppInstall/releases/download/" + tag + "/" + archive},
            {"name": "SHA256SUMS", "size": 100,
             "browser_download_url":
             "https://github.com/aboodmohd/-AppInstall/releases/download/" + tag + "/SHA256SUMS"},
        ],
    }


def launcher(version):
    return ('#!/usr/bin/env bash\nVERSION="' + version + '"\n').encode()


def archive_bytes(version, extra=None):
    required = {
        "appinstall": launcher(version),
        "integration.py": b"# test installer\n",
        "source_transaction.py": b"# test transaction\n",
        "portable_update.py": b"# test updater\n",
        "manager_qml.py": b"# test manager\n",
        "manager_ui/main.qml": b"// test qml\n",
        "appinstall.desktop": b"[Desktop Entry]\n",
        "appinstall-appimage-review.desktop": b"[Desktop Entry]\n",
    }
    required.update(extra or {})
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as out:
        for name, contents in required.items():
            record = tarfile.TarInfo("appinstall-" + version + "/" + name)
            record.size = len(contents)
            out.addfile(record, io.BytesIO(contents))
    return stream.getvalue()


class PortableReleaseTests(unittest.TestCase):
    def test_exact_official_assets_and_published_stable_only(self):
        value = portable.parse_release(stable())
        self.assertEqual(value[0:2], ("1.8.1", "v1.8.1"))
        self.assertEqual(value[2]["name"], "appinstall-1.8.1-portable.tar.gz")
        for mutate in (
            lambda x: x.update(draft=True),
            lambda x: x.update(prerelease=True),
            lambda x: x.update(tag_name="v1.8.1rc1"),
            lambda x: x["assets"][0].update(
                browser_download_url="https://evil.invalid/app.tar.gz"),
            lambda x: x["assets"].append(dict(x["assets"][0])),
            lambda x: x["assets"][0].update(size=portable.MAX_ARCHIVE + 1),
            lambda x: x["assets"].pop(),
        ):
            with self.subTest(mutate=mutate):
                data = stable()
                mutate(data)
                with self.assertRaises(portable.PortableUpdateError):
                    portable.parse_release(data)

    def test_manifest_requires_single_exact_matching_checksum(self):
        digest = "a" * 64
        manifest = (digest + "  appinstall-1.8.1-portable.tar.gz\n").encode()
        self.assertEqual(portable.expected_digest(
            manifest, "appinstall-1.8.1-portable.tar.gz"), digest)
        for bad in (b"", manifest + manifest,
                    b"X" + manifest, digest.encode() + b"  ../bad\n",
                    (digest + "  appinstall-1.8.2-portable.tar.gz\n").encode()):
            with self.subTest(bad=bad):
                with self.assertRaises(portable.PortableUpdateError):
                    portable.expected_digest(bad, "appinstall-1.8.1-portable.tar.gz")

    def test_version_comparison_is_numeric_and_strict(self):
        self.assertGreater(portable._version("1.10.0"), portable._version("1.9.9"))
        for bad in ("1.8.0-rc1", "", "v1.8.0", "1.8"):
            with self.assertRaises(portable.PortableUpdateError):
                portable._version(bad)


class PortableInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.state = self.home / ".local/share/appinstall"
        self.bin = self.home / ".local/bin"
        self.state.mkdir(parents=True)
        self.bin.mkdir(parents=True)
        (self.state / "integration.py").write_text("# user installed\n")
        (self.bin / "appinstall").write_bytes(launcher("1.8.0"))
        self.homePatch = patch.object(portable.Path, "home", return_value=self.home)
        self.homePatch.start()
        self.addCleanup(self.homePatch.stop)
        self.xdgPatch = patch.dict(os.environ, {"XDG_DATA_HOME": str(self.home / ".local/share")})
        self.xdgPatch.start()
        self.addCleanup(self.xdgPatch.stop)
        self.rootPatch = patch.object(portable.os, "geteuid", return_value=1000)
        self.rootPatch.start()
        self.addCleanup(self.rootPatch.stop)
        self.nativePatch = patch.object(portable, "native_package_present", return_value=False)
        self.nativePatch.start()
        self.addCleanup(self.nativePatch.stop)

    def test_installed_source_is_verified_read_only(self):
        self.assertEqual(portable.require_user_install(
            state=self.state, home=self.home)[0], "1.8.0")
        self.assertEqual(portable.installed_version(self.bin / "appinstall"), "1.8.0")
        with self.assertRaises(portable.PortableUpdateError):
            portable.require_user_install(state=self.home, home=self.home)
        (self.bin / "appinstall").unlink()
        (self.bin / "appinstall").symlink_to(self.state / "integration.py")
        with self.assertRaises(portable.PortableUpdateError):
            portable.require_user_install(state=self.state, home=self.home)

    def test_native_install_and_root_are_not_overwritten(self):
        with patch.object(portable, "native_package_present", return_value=True):
            with self.assertRaises(portable.PortableUpdateError):
                portable.require_user_install(state=self.state, home=self.home)
        with patch.object(portable.os, "geteuid", return_value=0):
            with self.assertRaises(portable.PortableUpdateError):
                portable.require_user_install(state=self.state, home=self.home)

    def test_unpacks_only_regular_files_below_expected_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "valid.tar.gz"
            path.write_bytes(archive_bytes("1.8.1"))
            folder = portable.unpack_archive(path, Path(tmp), "1.8.1")
            self.assertEqual(portable.installed_version(folder / "appinstall"), "1.8.1")
            self.assertTrue((folder / "manager_ui/main.qml").is_file())

            for unsafe in ("../escape", "appinstall-1.8.1/../../escape"):
                bad = Path(tmp) / "unsafe.tar.gz"
                with tarfile.open(bad, "w:gz") as out:
                    item = tarfile.TarInfo(unsafe)
                    item.size = 3
                    out.addfile(item, io.BytesIO(b"bad"))
                with self.assertRaises(portable.PortableUpdateError):
                    portable.unpack_archive(bad, Path(tmp), "1.8.1")
            symlink = Path(tmp) / "symlink.tar.gz"
            with tarfile.open(symlink, "w:gz") as out:
                item = tarfile.TarInfo("appinstall-1.8.1/external")
                item.type = tarfile.SYMTYPE
                item.linkname = "/etc/passwd"
                out.addfile(item)
            with self.assertRaises(portable.PortableUpdateError):
                portable.unpack_archive(symlink, Path(tmp), "1.8.1")

    def test_valid_update_runs_existing_transaction_with_verified_input(self):
        content = archive_bytes("1.8.1")
        digest = hashlib.sha256(content).hexdigest()
        filename = "appinstall-1.8.1-portable.tar.gz"
        manifest = (digest + "  " + filename + "\n").encode()
        release = portable.parse_release(stable())
        release[2]["size"] = len(content)
        release[3]["size"] = len(manifest)
        calls = []
        def downloader(url, destination=None, limit=0):
            calls.append(url)
            if destination is None:
                return manifest, hashlib.sha256(manifest).hexdigest(), len(manifest)
            destination.write_bytes(content)
            return None, digest, len(content)

        def run(cmd, **kwargs):
            self.assertEqual(Path(cmd[1]).name, "integration.py")
            self.assertEqual(Path(cmd[1]).parent, Path(kwargs["cwd"]))
            (self.bin / "appinstall").write_bytes(launcher("1.8.1"))
            return type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

        current = ("1.8.0", self.bin / "appinstall", self.state)
        with patch.object(portable, "require_user_install", return_value=current), \
             patch.object(portable.subprocess, "run", side_effect=run):
            self.assertEqual(portable.apply_update("v1.8.1", current, release, downloader),
                             "v1.8.1")
        self.assertEqual(len(calls), 2)
        self.assertEqual(portable.installed_version(self.bin / "appinstall"), "1.8.1")

    def test_bad_digest_or_tag_cannot_call_install(self):
        release = portable.parse_release(stable())
        archive = archive_bytes("1.8.1")
        release[2]["size"] = len(archive)
        manifest = ("0" * 64 + "  appinstall-1.8.1-portable.tar.gz\n").encode()
        release[3]["size"] = len(manifest)
        def downloader(url, destination=None, limit=0):
            if destination is None:
                return manifest, "", len(manifest)
            destination.write_bytes(archive)
            return None, hashlib.sha256(archive).hexdigest(), len(archive)
        installation = ("1.8.0", self.bin / "appinstall", self.state)
        with patch.object(portable.subprocess, "run") as runner:
            with self.assertRaises(portable.PortableUpdateError):
                portable.apply_update("v1.8.1", installation, release, downloader)
            with self.assertRaises(portable.PortableUpdateError):
                portable.apply_update("v1.8.2", installation, release, downloader)
            runner.assert_not_called()

    def test_main_check_has_no_install_side_effect(self):
        fake = stable("1.8.1")
        response = portable.parse_release(fake)
        with patch.object(portable, "require_user_install",
                          return_value=("1.8.0", self.bin / "appinstall", self.state)), \
             patch.object(portable, "current_release", return_value=response), \
             patch.object(portable, "apply_update") as installer:
            self.assertEqual(portable.main(["--desktop-check"]), 0)
            installer.assert_not_called()
        self.assertEqual(portable.installed_version(self.bin / "appinstall"), "1.8.0")


if __name__ == "__main__":
    unittest.main()
