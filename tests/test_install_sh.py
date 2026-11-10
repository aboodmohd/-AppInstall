"""Unit tests for the one-command installer (install.sh).

Run without network access and without touching the real user HOME: every
test sources install.sh inside a throwaway bash with a stubbed environment
and PATH shims for external tools (xdg-mime). The pacman/podman/kde paths
exercise no privileged actions here; the full pacman -U flow is covered by
the Arch-container integration job in .github/workflows/installer-tests.yml.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "install.sh"

ALL_MIMES = [
    "application/vnd.debian.binary-package",
    "application/x-deb",
    "application/x-rpm",
    "application/vnd.flatpak",
    "application/vnd.flatpak.ref",
    "application/vnd.flatpak.repo",
    "application/vnd.appimage",
    "application/x-iso9660-appimage",
    "application/x-quickdrop-appimage",
]


def run_sourced(snippet, env_extra=None, home=None, path_prepend=None):
    """Run `bash -c 'source install.sh; <snippet>'` and return (rc, out, err)."""
    env = os.environ.copy()
    home = home or tempfile.mkdtemp(prefix="appinstall-inst-tests-")
    env["HOME"] = str(home)
    # Keep test output deterministic and never let tests touch the real user
    # desktop configuration via XDG overrides.
    env["XDG_DATA_HOME"] = str(Path(home) / ".local" / "share")
    env["XDG_CONFIG_HOME"] = str(Path(home) / ".config")
    if path_prepend:
        env["PATH"] = str(path_prepend) + os.pathsep + env["PATH"]
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        ["bash", "-c", f"source '{SCRIPT}'; {snippet}"],
        capture_output=True, text=True, env=env, timeout=120,
    )
    return proc.returncode, proc.stdout, proc.stderr


def write_os_release(tmp, content):
    f = Path(tmp) / "os-release"
    f.write_text(content)
    return str(f)


class DistroDetectionTests(unittest.TestCase):
    CASES = {
        "arch": ("arch", "ID=arch\n"),
        "cachyos": ("arch", "NAME=CachyOS Linux\nID=cachyos\nID_LIKE=arch\n"),
        "endeavouros": ("arch", "ID=endeavouros\nID_LIKE=arch\n"),
        "ubuntu": ("debian", "NAME=Ubuntu\nID=ubuntu\nID_LIKE=debian\n"),
        "fedora": ("fedora", "NAME=Fedora Linux\nID=fedora\n"),
        "opensuse-leap": (
            "opensuse",
            "NAME=openSUSE Leap\nID=opensuse-leap\nID_LIKE=\"suse opensuse\"\n",
        ),
        "unknown-id": ("unknown", "NAME=Mystery\nID=mysteryos\n"),
        "no-id": ("unknown", "NAME=Broken\n"),
        "missing-file": ("unknown", None),
    }

    def test_family_mapping_is_exact(self):
        for name, (expected, content) in self.CASES.items():
            with self.subTest(distro=name):
                with tempfile.TemporaryDirectory() as tmp:
                    env = {}
                    if content is None:
                        env["APPINSTALL_TEST_OS_RELEASE"] = str(
                            Path(tmp) / "does-not-exist"
                        )
                    else:
                        env["APPINSTALL_TEST_OS_RELEASE"] = write_os_release(
                            tmp, content
                        )
                    rc, out, err = run_sourced("detect_family", env_extra=env)
                    self.assertEqual((rc, out.strip()), (0, expected))

    def test_distro_id_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "APPINSTALL_TEST_OS_RELEASE": write_os_release(
                    tmp, "ID=cachyos\nID_LIKE=arch\n"
                )
            }
            rc, out, _ = run_sourced("detect_distro_id", env_extra=env)
            self.assertEqual((rc, out.strip()), (0, "cachyos"))


class ReleaseResolutionTests(unittest.TestCase):
    RELEASE_JSON = {
        "tag_name": "v1.0.0",
        "prerelease": False,
        "draft": False,
        "assets": [
            {"name": "appinstall-1.0.0-1-any.pkg.tar.zst",
             "browser_download_url":
                 "https://github.com/aboodmohd/-AppInstall/releases/download/"
                 "v1.0.0/appinstall-1.0.0-1-any.pkg.tar.zst"},
            {"name": "SHA256SUMS",
             "browser_download_url":
                 "https://github.com/aboodmohd/-AppInstall/releases/download/"
                 "v1.0.0/SHA256SUMS"},
            {"name": "RELEASE_VERIFICATION.txt",
             "browser_download_url":
                 "https://github.com/aboodmohd/-AppInstall/releases/download/"
                 "v1.0.0/RELEASE_VERIFICATION.txt"},
        ],
    }

    def resolve(self, obj_or_none):
        with tempfile.TemporaryDirectory() as tmp:
            if obj_or_none is None:
                env = {}
            else:
                path = Path(tmp) / "releases.json"
                path.write_text(json.dumps(obj_or_none))
                env = {"APPINSTALL_TEST_RELEASES_JSON": str(path)}
            rc, out, err = run_sourced("resolve_release", env_extra=env)
            return rc, out.strip(), err.strip()

    def test_resolves_tag_and_asset_urls(self):
        rc, line, err = self.resolve(self.RELEASE_JSON)
        self.assertEqual(rc, 0)
        tag, pkg_url, sums_url, pkg_name = line.split("|")
        self.assertEqual(tag, "v1.0.0")
        self.assertEqual(pkg_name, "appinstall-1.0.0-1-any.pkg.tar.zst")
        self.assertTrue(pkg_url.endswith("appinstall-1.0.0-1-any.pkg.tar.zst"))
        self.assertTrue(sums_url.endswith("SHA256SUMS"))

    def test_signature_assets_are_not_picked_as_package(self):
        data = json.loads(json.dumps(self.RELEASE_JSON))
        data["assets"][0]["browser_download_url"] += ".sig"
        data["assets"].append(
            {"name": "appinstall-1.0.0-1-any.pkg.tar.zst.sig",
             "browser_download_url":
                 "https://x/y/appinstall-1.0.0-1-any.pkg.tar.zst.sig"})
        rc, line, _ = self.resolve(data)
        self.assertNotEqual(rc, 0, "a .sig file must never satisfy the package slot")

    def test_missing_sums_asset_fails(self):
        data = json.loads(json.dumps(self.RELEASE_JSON))
        data["assets"] = data["assets"][:1]
        rc, _, _ = self.resolve(data)
        self.assertNotEqual(rc, 0)

    def test_no_release_at_all_fails(self):
        data = {"message": "Not Found"}
        rc, _, _ = self.resolve(data)
        self.assertNotEqual(rc, 0)

    def test_rejects_unstable_or_untrusted_assets(self):
        import copy
        for mutation in ("draft", "prerelease", "url", "duplicate", "tag"):
            data = copy.deepcopy(self.RELEASE_JSON)
            if mutation in ("draft", "prerelease"):
                data[mutation] = True
            elif mutation == "url":
                data["assets"][0]["browser_download_url"] = "https://example.com/package"
            elif mutation == "duplicate":
                data["assets"].append(data["assets"][0])
            else:
                data["tag_name"] = "v1|injected"
            with self.subTest(mutation=mutation):
                rc, _, _ = self.resolve(data)
                self.assertEqual(rc, 4)



class ChecksumVerificationTests(unittest.TestCase):
    PKG_NAME = "appinstall-1.0.0-1-any.pkg.tar.zst"

    def make_dir(self, raw=b"payload-bytes"):
        tmp = tempfile.mkdtemp(prefix="appinstall-checksum-")
        pkg = Path(tmp) / self.PKG_NAME
        pkg.write_bytes(raw)
        return tmp, raw

    def sums_line(self, raw):
        import hashlib
        return f"{hashlib.sha256(raw).hexdigest()}  {self.PKG_NAME}\n"

    def test_matching_checksum_passes(self):
        tmp, raw = self.make_dir()
        (Path(tmp) / "SHA256SUMS").write_text(self.sums_line(raw))
        rc, out, err = run_sourced(f"verify_checksums '{tmp}' '{self.PKG_NAME}'")
        self.assertEqual(rc, 0)

    def test_tampered_package_fails(self):
        tmp, raw = self.make_dir()
        (Path(tmp) / "SHA256SUMS").write_text(self.sums_line(raw))
        (Path(tmp) / self.PKG_NAME).write_bytes(raw + b"tampered")
        rc, out, err = run_sourced(f"verify_checksums '{tmp}' '{self.PKG_NAME}'")
        self.assertEqual(rc, 3)

    def test_missing_manifest_line_fails(self):
        tmp, raw = self.make_dir()
        (Path(tmp) / "SHA256SUMS").write_text(
            f"{self.sums_line(raw)} references-none  no-such-file\n"
        )
        # Manifest contains no line for the package at all.
        (Path(tmp) / "SHA256SUMS").write_text(
            "aa  some-unrelated-file\n"
        )
        rc, _, _ = run_sourced(f"verify_checksums '{tmp}' '{self.PKG_NAME}'")
        self.assertEqual(rc, 3)

    def test_duplicated_manifest_lines_fail(self):
        tmp, raw = self.make_dir()
        (Path(tmp) / "SHA256SUMS").write_text(self.sums_line(raw) * 2)
        rc, _, _ = run_sourced(f"verify_checksums '{tmp}' '{self.PKG_NAME}'")
        self.assertEqual(rc, 3)

    def test_manifest_with_other_release_assets_passes(self):
        tmp, raw = self.make_dir()
        (Path(tmp) / "SHA256SUMS").write_text(
            self.sums_line(raw) + "0" * 64 + "  unavailable-source.tar.gz\n")
        rc, _, _ = run_sourced(f"verify_checksums '{tmp}' '{self.PKG_NAME}'")
        self.assertEqual(rc, 0)



class PackageVersionTests(unittest.TestCase):
    def test_version_extraction(self):
        cases = {
            "appinstall-1.0.0-1-any.pkg.tar.zst": "1.0.0-1",
            "appinstall-1.2.3-1-any.pkg.tar.zst": "1.2.3-1",
            "appinstall-1.0.0b1-1-any.pkg.tar.zst": "1.0.0b1-1",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                rc, out, _ = run_sourced(f"package_version_from_asset '{name}'")
                self.assertEqual((rc, out.strip()), (0, expected))


class MimeStateTests(unittest.TestCase):
    """Per-user MIME default management: backup → set → restore round trip,
    with a mimeapps.list-file-driven xdg-mime shim (mirrors real xdg-mime
    semantics: defaults live in $XDG_CONFIG_HOME/mimeapps.list under
    [Default Applications]) so the real desktop configuration is never touched."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="appinstall-mime-"))
        self.bin = self.home / "bin"
        self.bin.mkdir()
        self.config = self.home / ".config"
        self.mimeapps = self.config / "mimeapps.list"
        self.shim = self.bin / "xdg-mime"
        self.shim.write_text(self.SHIM_BODY)
        self.shim.chmod(0o755)

    SHIM_BODY = r"""#!/usr/bin/env python3
import os
import sys

mimeapps = os.path.join(
    os.environ.get("XDG_CONFIG_HOME",
                   os.path.join(os.environ["HOME"], ".config")),
    "mimeapps.list")

args = sys.argv[1:]


def query_default(mime):
    if not os.path.exists(mimeapps):
        print("")
        return
    insec = False
    for line in open(mimeapps, encoding="utf-8"):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            insec = s == "[Default Applications]"
            continue
        if insec and "=" in s:
            key, val = s.split("=", 1)
            if key.strip() == mime:
                print(val.strip().rstrip(";").strip())
                return
    print("")


def set_default(handler, mimes):
    os.makedirs(os.path.dirname(mimeapps), exist_ok=True)
    data = ""
    if os.path.exists(mimeapps):
        data = open(mimeapps, encoding="utf-8").read()
    out_lines = []
    insec = False
    remaining = list(mimes)
    saw_default = False
    for orig in data.splitlines():
        s = orig.strip()
        if s.startswith("[") and s.endswith("]"):
            if saw_default:
                # leaving the Default section: flush any inserts here
                for m in remaining:
                    out_lines.append(f"{m}={handler}")
                remaining = []
            insec = s == "[Default Applications]"
            if insec:
                saw_default = True
            out_lines.append(orig)
            continue
        if insec and "=" in s:
            key = s.split("=", 1)[0].strip()
            if key in mimes:
                out_lines.append(f"{key}={handler}")
                remaining.remove(key)
                continue
        out_lines.append(orig)
    if not saw_default:
        out_lines.append("[Default Applications]")
    for m in remaining:
        out_lines.append(f"{m}={handler}")
    open(mimeapps, "w", encoding="utf-8").write("\n".join(out_lines) + "\n")


if not args:
    sys.exit(1)
if args[0] == "query":
    query_default(args[2] if args[1] == "default" else args[1])
elif args[0] == "default":
    mimes = args[2:]
    if not mimes:
        sys.exit(1)
    set_default(args[1], mimes)
else:
    sys.exit(1)
"""

    def env_for(self):
        return {
            "XDG_CONFIG_HOME": str(self.config),
            "HOME": str(self.home),
        }

    def query(self, mime):
        """Query through the shim (mirrors xdg-mime query default semantics)."""
        env = self.env_for()
        env["PATH"] = str(self.bin) + os.pathsep + os.environ["PATH"]
        proc = subprocess.run(
            [str(self.bin / "xdg-mime"), "query", "default", mime],
            capture_output=True, text=True, env=env,
        )
        return proc.stdout.strip()

    def seed_previous_defaults(self, mapping):
        """Write a starting mimeapps.list exactly as the desktop would leave it."""
        self.config.mkdir(parents=True, exist_ok=True)
        lines = ["[Default Applications]"]
        for mime, handler in mapping.items():
            if handler is not None:
                lines.append(f"{mime}={handler}")
        self.mimeapps.write_text("\n".join(lines) + "\n")

    def run_snippet(self, snippet):
        return run_sourced(
            snippet, env_extra=self.env_for(), home=str(self.home),
            path_prepend=self.bin,
        )

    def read_backup_tsv(self):
        path = self.home / ".local" / "share" / "appinstall" / "installer" / \
            "previous-mime-defaults.tsv"
        self.assertTrue(path.is_file(), f"backup TSV missing: {path}")
        rows = {}
        for line in path.read_text().splitlines():
            if "\t" in line:
                mime, val = line.split("\t", 1)
                rows[mime] = val
        return rows

    def test_backup_set_restore_roundtrip(self):
        previous = {
            "application/x-deb": "other-deb-handler.desktop",
            "application/vnd.appimage": None,
        }
        self.seed_previous_defaults(previous)

        # 1) backup + set defaults + drop console noise
        snippet = (
            "backup_mime_defaults >/dev/null; "
            "write_restore_script; "
            "set_mime_defaults >/dev/null 2>&1"
        )
        rc, _, err = self.run_snippet(snippet)
        self.assertEqual(rc, 0, f"set_mime_defaults failed: {err}")

        # 2) every advertised MIME now points at AppInstall per-user
        for mime in ALL_MIMES:
            self.assertEqual(self.query(mime), "appinstall.desktop", mime)

        # 3) backup preserved the previous state exactly,
        #    including the *unset* entry
        saved = self.read_backup_tsv()
        self.assertIn("application/x-deb", saved)
        self.assertEqual(saved["application/x-deb"], "other-deb-handler.desktop")
        self.assertIn("application/vnd.appimage", saved)
        self.assertEqual(saved["application/vnd.appimage"], "")

        # 4) restore script exists at the documented path
        restore = self.home / ".local" / "share" / "appinstall" / "installer" / \
            "restore-mime-defaults.sh"
        self.assertTrue(restore.is_file())
        self.assertTrue(os.access(restore, os.X_OK))

        # 5) run the restore script in a fresh shell (same fake env)
        env = self.env_for()
        env["PATH"] = str(self.bin) + os.pathsep + os.environ["PATH"]
        env["HOME"] = str(self.home)
        proc = subprocess.run([str(restore)], capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)

        # 6) previous state fully restored: known handler back, unset stays unset
        self.assertEqual(
            self.query("application/x-deb"), "other-deb-handler.desktop"
        )
        self.assertEqual(self.query("application/vnd.appimage"), "")
        for mime in ALL_MIMES:
            if mime in previous and previous[mime] is None:
                self.assertEqual(self.query(mime), "", mime)

    def test_backup_is_idempotent(self):
        # First backup wins; running the flow twice must not overwrite it.
        self.seed_previous_defaults({"application/x-rpm": "first-owner.desktop"})
        rc1, _, _ = self.run_snippet("backup_mime_defaults >/dev/null")
        self.assertEqual(rc1, 0)
        saved1 = self.read_backup_tsv()
        self.assertEqual(saved1["application/x-rpm"], "first-owner.desktop")

        # Simulate later defaults changing (as after set_mime_defaults):
        rc2, _, _ = self.run_snippet("backup_mime_defaults >/dev/null")
        self.assertEqual(rc2, 0)
        saved2 = self.read_backup_tsv()
        self.assertEqual(saved1, saved2, "second run must keep the FIRST backup")

    def test_restore_preserves_user_changes_after_installation(self):
        """After AppInstall sets defaults, if the user changes one MIME away
        from AppInstall, restore must keep that user change and only revert
        MIMEs where AppInstall is still the default."""
        previous = {
            "application/x-deb": "other-deb-handler.desktop",
            "application/vnd.appimage": None,
        }
        self.seed_previous_defaults(previous)

        snippet = (
            "backup_mime_defaults >/dev/null; "
            "write_restore_script; "
            "set_mime_defaults >/dev/null 2>&1"
        )
        rc, _, err = self.run_snippet(snippet)
        self.assertEqual(rc, 0, f"set_mime_defaults failed: {err}")
        for mime in ALL_MIMES:
            self.assertEqual(self.query(mime), "appinstall.desktop", mime)

        # User changes one MIME away from AppInstall AFTER installation.
        env = self.env_for()
        env["PATH"] = str(self.bin) + os.pathsep + os.environ["PATH"]
        env["HOME"] = str(self.home)
        subprocess.run(
            [str(self.bin / "xdg-mime"), "default", "user-picked.desktop",
             "application/vnd.appimage"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(
            self.query("application/vnd.appimage"), "user-picked.desktop"
        )

        # Restore: deb reverts to previous handler; appimage keeps user's pick.
        restore = self.home / ".local" / "share" / "appinstall" / "installer" / \
            "restore-mime-defaults.sh"
        proc = subprocess.run([str(restore)], capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            self.query("application/x-deb"), "other-deb-handler.desktop"
        )
        self.assertEqual(
            self.query("application/vnd.appimage"), "user-picked.desktop",
            "user-made change after installation must be preserved"
        )

    def test_restore_preserves_changed_handler_with_previous_default(self):
        self.seed_previous_defaults({"application/x-deb": "old.desktop"})
        rc, _, err = self.run_snippet(
            'backup_mime_defaults >/dev/null; write_restore_script; '
            'set_mime_defaults >/dev/null; '
            'xdg-mime default new.desktop application/x-deb; '
            '"$STATE_RESTORE_SCRIPT"')
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.query("application/x-deb"), "new.desktop")

    def test_yes_does_not_set_defaults(self):
        self.seed_previous_defaults({"application/x-deb": "old.desktop"})
        rc, _, err = self.run_snippet(
            'detect_family() { echo arch; }; ASSUME_YES=1; maybe_set_defaults')
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.query("application/x-deb"), "old.desktop")
        self.assertFalse((self.home / ".local/share/appinstall/installer").exists())

    def test_dry_run_with_explicit_flags_has_no_side_effects(self):
        self.seed_previous_defaults({"application/x-deb": "old.desktop"})
        original = self.mimeapps.read_bytes()
        rc, _, err = self.run_snippet(
            'DRY_RUN=1; SET_DEFAULTS=1; WITH_OPTIONAL=1; '
            'run_root() { exit 99; }; podman() { exit 98; }; '
            'maybe_set_defaults; audit_optional_backends; rootless_podman_report; '
            'uninstall_flow')
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.mimeapps.read_bytes(), original)
        self.assertFalse((self.home / ".local/share/appinstall/installer").exists())

    def test_restore_removes_added_associations_and_keeps_other_sections(self):
        self.seed_previous_defaults({"application/x-deb": "old.desktop"})
        rc, _, err = self.run_snippet(
            'backup_mime_defaults >/dev/null; write_restore_script; '
            'set_mime_defaults >/dev/null')
        self.assertEqual(rc, 0, err)
        with self.mimeapps.open("a") as stream:
            stream.write("[Added Associations]\napplication/x-deb=appinstall.desktop;other.desktop;\n"
                         "[Removed Associations]\napplication/x-deb=blocked.desktop;\n")
        rc, _, err = self.run_snippet('"$STATE_RESTORE_SCRIPT"')
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.query("application/x-deb"), "old.desktop")
        text = self.mimeapps.read_text()
        self.assertIn("application/x-deb=other.desktop;", text)
        self.assertIn("application/x-deb=blocked.desktop;", text)
        self.assertNotIn("appinstall.desktop", text)



class ShadowConflictTests(unittest.TestCase):
    """check_shadow_conflicts must never let --yes alone authorize removal
    of an existing user-local (source) installation."""

    def setup_shadow(self, home):
        bindir = Path(home) / ".local" / "bin"
        bindir.mkdir(parents=True, exist_ok=True)
        (bindir / "appinstall").write_text("#!/bin/sh\necho source-install\n")
        (bindir / "appinstall").chmod(0o755)

    def run_conflict(self, env_extra):
        home = tempfile.mkdtemp(prefix="appinstall-conflict-")
        self.setup_shadow(home)
        env = {
            "HOME": str(home),
            "XDG_DATA_HOME": str(Path(home) / ".local" / "share"),
            "XDG_CONFIG_HOME": str(Path(home) / ".config"),
        }
        env.update(env_extra)
        return run_sourced("check_shadow_conflicts", env_extra=env, home=home)

    def test_yes_alone_does_not_authorize_removal(self):
        rc, _, _ = self.run_conflict({"ASSUME_YES": "1", "DRY_RUN": "0"})
        self.assertEqual(rc, 2, "--yes must not remove a source install without --remove-source-install")

    def test_remove_source_install_flag_authorizes_removal_attempt(self):
        home = tempfile.mkdtemp(prefix="appinstall-remove-")
        self.setup_shadow(home)
        env = {
            "HOME": str(home),
            "XDG_DATA_HOME": str(Path(home) / ".local" / "share"),
            "XDG_CONFIG_HOME": str(Path(home) / ".config"),
            "REMOVE_SOURCE_INSTALL": "1",
            "DRY_RUN": "0",
        }
        # There is no appinstall-uninstall script, so removal attempts fail
        # gracefully but consent was granted (no exit-2 refusal).
        rc, _, err = run_sourced("check_shadow_conflicts", env_extra=env, home=home)
        self.assertNotEqual(rc, 2, "--remove-source-install must consent to removal")


class InstallerConsentTests(unittest.TestCase):
    def test_yes_requires_live_source_removal_confirmation(self):
        with tempfile.TemporaryDirectory() as home:
            ShadowConflictTests().setup_shadow(home)
            rc, _, _ = run_sourced(
                'ASSUME_YES=1; TTY_OK=1; tty_read_line() { echo n; }; '
                'check_shadow_conflicts', home=home)
            self.assertEqual(rc, 2)
            self.assertTrue((Path(home) / '.local/bin/appinstall').exists())

    def test_api_token_header_accepts_punctuation_without_argv_exposure(self):
        rc, out, err = run_sourced(
            'GITHUB_TOKEN="test.token-with+punctuation="; '
            'curl() { printf "ARG:%s\\n" "$@"; cat; }; api_get /example')
        self.assertEqual(rc, 0, err)
        self.assertIn('Authorization: Bearer test.token-with+punctuation=', out)
        self.assertNotIn('ARG:Authorization:', out)
        self.assertIn('ARG:@-', out)

    def test_api_rejects_header_injection(self):
        rc, _, _ = run_sourced("GITHUB_TOKEN=$'token\\r\\nInjected: header'; api_get /example")
        self.assertEqual(rc, 4)

    def test_optional_packages_are_explicit_and_noninteractive_with_yes(self):
        rc, out, err = run_sourced(
            'ASSUME_YES=1; WITH_OPTIONAL=1; '
            'missing_optional_pkgs() { printf "flatpak\\npodman\\n"; }; '
            'run_root() { printf "ARG:%s\\n" "$@"; }; '
            'audit_optional_backends')
        self.assertEqual(rc, 0, err)
        self.assertIn('ARG:--noconfirm', out)
        self.assertIn('ARG:flatpak', out)
        self.assertIn('ARG:podman', out)
        self.assertNotIn('ARG:--asdeps', out)


if __name__ == "__main__":
    unittest.main()
