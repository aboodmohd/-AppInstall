#!/usr/bin/env python3
"""Disposable real-file portable AppInstall upgrade/rollback acceptance.

CI runs this as a non-root test user after installing an official portable
candidate. A locally manufactured NEXT version is used solely as a fixture;
the script never calls the network or any host package manager. It exercises
the production apply_update + subprocess integration + SourceTransaction path.
"""
import hashlib
import io
import os
from pathlib import Path
import sys
import tarfile
import tempfile

if len(sys.argv) != 2:
    raise SystemExit("Usage: ci_portable_upgrade.py <extracted-portable-source-directory>")

source = Path(sys.argv[1]).resolve()
home = Path.home()
state = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local/share"))) / "appinstall"
config = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
launcher = home / ".local/bin/abood-appinstall"

if os.geteuid() == 0 or not (state / "portable_update.py").is_file():
    raise SystemExit("Run after a real non-root portable install.")
sys.path.insert(0, str(state))
import portable_update as updater  # noqa: E402
import settings  # noqa: E402

if Path(updater.__file__).resolve() != (state / "portable_update.py").resolve():
    raise SystemExit("Update helper was not loaded from the user installation.")

start_version = updater.installed_version(launcher)
parts = list(map(int, start_version.split(".")))
if len(parts) != 3:
    raise SystemExit("Bad installed version")
next_version = ".".join(map(str, (parts[0], parts[1], parts[2] + 1)))
fault_version = ".".join(map(str, (parts[0], parts[1], parts[2] + 2)))

# Genuine settings parser and MIME association record; preserve both and
# unrelated user-managed data through successful and failed updates.
settings.write({
    "theme": "dark",
    "favorites": ["flatpak:org.example.KeepFavorite"],
    "notifications": True,
    "uninstall_mode": "app_only",
})
keep = state / "user-keep-data.txt"
keep.write_text("user data must survive updates\n", encoding="utf-8")
mime = config / "mimeapps.list"
association = state / "associations.json"
if not mime.is_file() or not association.is_file():
    raise AssertionError("Initial installation failed to record MIME associations")
snapshot = {f: f.read_bytes() for f in (settings.settings_path(), keep, mime, association)}


def assert_preserved(expected_version):
    assert updater.installed_version(launcher) == expected_version
    assert (state / "portable_update.py").is_file()
    assert (state / "manager_ui/main.qml").is_file()
    assert settings.read()["theme"] == "dark"
    assert settings.read()["favorites"] == ["flatpak:org.example.KeepFavorite"]
    for path, old in snapshot.items():
        assert path.read_bytes() == old, f"User data changed during upgrade: {path}"
    assert not (state / ".source-update/journal.json").exists(), "Unrecovered transaction"


def archive_for(version, directory, inject_failure=False):
    """Construct a fully populated offline release fixture from the real source."""
    filename = f"appinstall-{version}-portable.tar.gz"
    output = directory / filename
    found_launcher = 0
    found_integration = 0
    with tarfile.open(output, "w:gz") as bundle:
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise AssertionError("Official portable input unexpectedly contains a link")
            if not path.is_file():
                continue
            relative = path.relative_to(source).as_posix()
            payload = path.read_bytes()
            if relative == "appinstall":
                original = ('VERSION="' + start_version + '"').encode()
                assert payload.count(original) == 1
                payload = payload.replace(original, ('VERSION="' + version + '"').encode())
                found_launcher += 1
            if relative == "integration.py" and inject_failure:
                anchor = b"from source_transaction import SourceTransaction\n"
                assert payload.count(anchor) == 1
                injection = (
                    b"\n# Test-only failure injected in this synthetic archive.\n"
                    b"_original_publish = SourceTransaction._publish\n"
                    b"def _ci_fail_during_publish(self, stage, target):\n"
                    b"    if Path(target).name == 'manager_qml.py':\n"
                    b"        raise OSError('CI injected rollback test after partial publication')\n"
                    b"    return _original_publish(self, stage, target)\n"
                    b"SourceTransaction._publish = _ci_fail_during_publish\n"
                )
                payload = payload.replace(anchor, anchor + injection)
                found_integration += 1
            entry = tarfile.TarInfo(f"appinstall-{version}/{relative}")
            entry.mode = 0o755 if relative in ("appinstall", "install-user.sh") else 0o644
            entry.size = len(payload)
            bundle.addfile(entry, io.BytesIO(payload))
    assert found_launcher == 1
    if inject_failure:
        assert found_integration == 1
    return output


def offline_release(archive, version, wrong_checksum=False):
    """Use the actual published-release field parser; intercept transport only."""
    tag = "v" + version
    filename = archive.name
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if wrong_checksum:
        digest = "0" * 64
    manifest = (digest + "  " + filename + "\n").encode()
    release = updater.parse_release({
        "tag_name": tag,
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": filename,
                "size": archive.stat().st_size,
                "browser_download_url":
                    f"https://github.com/{updater.REPO}/releases/download/{tag}/{filename}",
            },
            {
                "name": "SHA256SUMS",
                "size": len(manifest),
                "browser_download_url":
                    f"https://github.com/{updater.REPO}/releases/download/{tag}/SHA256SUMS",
            },
        ],
    })

    def downloader(url, destination=None, limit=None):
        if url == release[3]["url"] and destination is None:
            return manifest, hashlib.sha256(manifest).hexdigest(), len(manifest)
        if url == release[2]["url"] and destination is not None:
            data = archive.read_bytes()
            if limit is not None and len(data) > limit:
                raise AssertionError("Test archive exceeded updater's limit")
            destination.write_bytes(data)
            return None, hashlib.sha256(data).hexdigest(), len(data)
        raise AssertionError("Updater requested an unexpected or network URL")

    return release, downloader


installation = updater.require_user_install()
assert installation[0] == start_version
assert_preserved(start_version)

with tempfile.TemporaryDirectory(prefix="appinstall-real-upgrade-") as tmp:
    fixtures = Path(tmp)
    good = archive_for(next_version, fixtures)
    release, download = offline_release(good, next_version, wrong_checksum=True)
    try:
        updater.apply_update("v" + next_version, installation, release, downloader=download)
    except updater.PortableUpdateError:
        pass
    else:
        raise AssertionError("Bad SHA256SUMS must block the upgrade")
    assert_preserved(start_version)
    print("PASS: wrong checksum refused with no source/user data changes")

    release, download = offline_release(good, next_version)
    assert updater.apply_update(
        "v" + next_version, installation, release, downloader=download
    ) == "v" + next_version
    assert_preserved(next_version)
    print(f"PASS: verified real source transaction {start_version} -> {next_version}")

    bad = archive_for(fault_version, fixtures, inject_failure=True)
    release, download = offline_release(bad, fault_version)
    installation = updater.require_user_install()
    assert installation[0] == next_version
    try:
        updater.apply_update(
            "v" + fault_version, installation, release, downloader=download
        )
    except updater.PortableUpdateError as error:
        assert "Recoverable source update did not complete" in str(error)
    else:
        raise AssertionError("Injected filesystem publication failure must propagate")
    assert_preserved(next_version)
    print("PASS: partial multi-file update rolled back with settings/MIME preserved")

print("PASS: portable source upgrade/rollback on this disposable Linux image")
