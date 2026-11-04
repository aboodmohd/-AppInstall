#!/usr/bin/env python3
"""Make a self-identifying release candidate evidence bundle, without releasing it.

Read-only against the built Arch package and checkout. This script does not
install packages, create tags, alter applications, or approve human gates.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SHA_LINE = re.compile(r"^([0-9a-f]{64})  ([^\r\n]+)$")
SHA = re.compile(r"^[0-9a-f]{40}$")
REQUIRED = ("usr/bin/appinstall", "usr/share/licenses/appinstall/LICENSE")


def _expected_sha(package, sums_path):
    lines = sums_path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1:
        raise ValueError("Expected exactly one line in SHA256SUMS")
    match = SHA_LINE.fullmatch(lines[0])
    if match is None or match.group(2) != package.name:
        raise ValueError("SHA256SUMS must identify the exact archive filename")
    return match.group(1)


def verify_checksum(package, sums_path):
    if not package.is_file() or not sums_path.is_file():
        raise ValueError("Built package or SHA256SUMS is missing")
    expected = _expected_sha(package, sums_path)
    digest = hashlib.file_digest(package.open("rb"), "sha256").hexdigest()
    if digest != expected:
        raise ValueError(f"Checksum mismatch for {package.name}")
    return digest


def _pkg_version(pkgbuild):
    text = pkgbuild.read_text(encoding="utf-8")
    match_ver = re.search(r"(?m)^pkgver=([a-zA-Z0-9._+-]+)$", text)
    match_rel = re.search(r"(?m)^pkgrel=([a-zA-Z0-9._+-]+)$", text)
    if not match_ver or not match_rel:
        raise ValueError("Cannot determine version and release from PKGBUILD")
    return match_ver.group(1), match_rel.group(1)


def verify_package(package, pkgbuild):
    version, release = _pkg_version(pkgbuild)
    expected = f"appinstall-{version}-{release}-any.pkg.tar.zst"
    if package.name != expected:
        raise ValueError(f"Expected package {expected}, got {package.name}")
    result = subprocess.run(
        ["bsdtar", "-tf", str(package)], capture_output=True, text=True,
        check=True, timeout=30,
    )
    listed = {name.lstrip("./") for name in result.stdout.splitlines()}
    if not all(path in listed for path in REQUIRED):
        raise ValueError("Built package is missing CLI or installed LICENSE")
    if any(path.endswith(".png") or "evidence/phase4/" in path for path in listed):
        raise ValueError("Evidence screenshots unexpectedly shipped in binary package")
    result = subprocess.run(
        ["bsdtar", "-xOf", str(package), "usr/share/licenses/appinstall/LICENSE"],
        capture_output=True, check=True, timeout=30,
    )
    if result.stdout != (ROOT / "LICENSE").read_bytes():
        raise ValueError("Packaged LICENSE bytes differ from source LICENSE")
    return version, release


def build_report(evidence):
    rows = (
        ("Fresh disposable CachyOS KDE Wayland installation", "PENDING"),
        ("AppImage: review, cancel, install, launch, reinstall, remove", "PENDING"),
        ("Flatpak: review, cancel, install, launch, reinstall, remove", "PENDING"),
        ("DEB: review, cancel, install, launch, reinstall, remove", "PENDING"),
        ("RPM: review, cancel, install, launch, reinstall, remove", "PENDING"),
        ("Dolphin association and no duplicate launchers", "PENDING"),
        ("Unrelated user data/MIME defaults preserved and snapshot restored", "PENDING"),
        ("Failure diagnostics and missing-dependency behavior", "PENDING"),
        ("Source/snippet redistribution rights confirmed by owner", "PENDING"),
        ("All eight screenshot redistribution rights confirmed by owner", "PENDING"),
        ("Independent checksum of the exact candidate verified on spare host", "PENDING"),
        ("Explicit separate Stable 1.0 publication approval", "PENDING"),
    )
    lines = [
        "# AppInstall 1.0 — disposable release candidate evidence",
        "",
        "**Status: NO-GO. This CI document is not a release approval.**",
        "",
        "## Exact CI-built artifact",
        "",
        f"- Source commit: {evidence['source_commit']}",
        f"- GitHub Actions run: {evidence['workflow_url']}",
        f"- Archive filename: {evidence['package_filename']}",
        f"- SHA-256: {evidence['sha256']}",
        f"- Package version: {evidence['package_version']}",
        f"- Generated at (UTC): {evidence['generated_utc']}",
        "",
        "Only the exact archive above matches this checksum. Rebuilds and",
        "other runs may have different bytes and require new verification.",
        "",
        "## Human-only gates (none approved by CI)",
        "",
        "| Required acceptance | Status |",
        "| --- | --- |",
    ]
    lines += [f"| {label} | {status} |" for label, status in rows]
    lines += [
        "",
        "## How to use on a disposable test system",
        "",
        "1. Start a fresh CachyOS KDE Wayland VM or separate spare system,",
        "   create a snapshot, and confirm it is not the daily-use installation.",
        "2. Download this exact workflow artifact ZIP. Extract it only in",
        "   the disposable test environment; compare the displayed source",
        "   commit and GitHub run to the metadata above.",
        "3. Independently run sha256sum on the archive, compare it with",
        "   the printed SHA-256 above, and run sha256sum -c SHA256SUMS.",
        "4. Inspect archive contents with bsdtar -tf and pacman -Qip",
        "   before any installation. Stop on a mismatch.",
        "5. Perform all four format workflows manually in the disposable",
        "   KDE session. Record redacted evidence, outcomes, and reviewer.",
        "6. Revert the snapshot and separately confirm source/screenshot",
        "   redistribution rights; no CI result substitutes for this.",
        "",
        "GitHub Actions itself does NOT perform the CachyOS human acceptance",
        "steps above, and this evidence bundle must not be published as",
        "an official Stable 1.0 asset without explicit owner approval.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--sums", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if not SHA.fullmatch(args.source_sha):
        raise ValueError("Source commit must be a complete 40-character SHA")
    if not args.run_id.isdecimal() or not int(args.run_id):
        raise ValueError("GitHub run ID must be a positive integer")
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("Output directory must not contain existing files")
    digest = verify_checksum(args.package, args.sums)
    version, release = verify_package(args.package, ROOT / "PKGBUILD")
    evidence = {
        "schema": "appinstall-candidate-evidence-1",
        "release_decision": "NO-GO",
        "source_commit": args.source_sha,
        "workflow_url": f"https://github.com/aboodmohd/-AppInstall/actions/runs/{args.run_id}",
        "package_filename": args.package.name,
        "package_version": f"{version}-{release}",
        "sha256": digest,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "approval": {
            "disposable_cachyos_kde_full_acceptance": "PENDING",
            "source_and_screenshot_rights": "PENDING",
            "exact_final_release_asset_verification": "PENDING",
            "explicit_stable_publication": "PENDING",
        },
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "candidate-evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output / "MANUAL_ACCEPTANCE.md").write_text(
        build_report(evidence), encoding="utf-8"
    )
    print(f"PASS: package SHA256 and archive contents verified: {digest}", flush=True)
    print("PASS: isolated candidate evidence bundle generated (NO-GO)", flush=True)
    print("INFO: human approval, license ownership and CachyOS test still pending", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
