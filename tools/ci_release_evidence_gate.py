#!/usr/bin/env python3
"""CI audit of release-evidence consistency, not a copyright certification.

Reads only repository files and the disposable CI-built Arch package. Never
installs, runs, removes or modifies an application or a user profile.
"""
import argparse
import hashlib
from pathlib import Path
import re
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "evidence" / "phase4"

# Deliberately an explicit inventory: new/removed images require review.
SCREENSHOTS = {
    "confirm.py review (light)": "confirm-review-light.png",
    "confirm.py review (forced dark)": "confirm-review-dark.png",
    "container_ui.py preview (light)": "container-preview-light.png",
    "container_ui.py preview (forced dark)": "container-preview-dark.png",
    "manager list (light)": "manager-list-light.png",
    "manager list (dark)": "manager-list-dark.png",
    "manager list (live KDE Wayland)": "manager-live-wayland.png",
    "manager details dialog": "manager-details.png",
}
SCRIPTED = set(SCREENSHOTS.values()) - {"manager-live-wayland.png"}
REPORT_ROW = re.compile(r"^- \*\*(.+?)\*\*: captured (\d+) bytes(?:\s.*)?$")


def verify_evidence():
    files = {p.name for p in EVIDENCE.glob("*.png")}
    expected = set(SCREENSHOTS.values())
    if files != expected:
        raise ValueError(
            f"Screenshot inventory differs: missing={sorted(expected - files)}, "
            f"unexpected={sorted(files - expected)}"
        )
    report = (EVIDENCE / "RESULTS.md").read_text()
    if "seven offscreen" not in report.lower() or "live kde wayland" not in report.lower():
        raise ValueError("Evidence report must distinguish seven offscreen captures from live KDE Wayland")
    rows = {}
    for line in report.splitlines():
        match = REPORT_ROW.fullmatch(line)
        if match:
            label, size = match.groups()
            if label in rows:
                raise ValueError(f"Duplicate evidence line: {label}")
            rows[label] = int(size)
    if set(rows) != set(SCREENSHOTS):
        raise ValueError(
            f"Report labels differ: missing={sorted(set(SCREENSHOTS) - set(rows))}; "
            f"unexpected={sorted(set(rows) - set(SCREENSHOTS))}"
        )

    capture_script = (ROOT / "tools" / "ui_evidence.py").read_text()
    for label, name in SCREENSHOTS.items():
        path = EVIDENCE / name
        data = path.read_bytes()
        if len(data) != rows[label]:
            raise ValueError(f"{name}: report lists {rows[label]} bytes, actual {len(data)}")
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise ValueError(f"{name} is not a valid PNG header")
        width, height = struct.unpack(">II", data[16:24])
        if not (0 < width <= 8192 and 0 < height <= 8192):
            raise ValueError(f"{name} has implausible image dimensions")
        if name in SCRIPTED and name not in capture_script:
            raise ValueError(f"{name} is not referenced by the capture script")
        print(f"PASS evidence: {name} ({len(data)} bytes; {width}x{height}; "
              f"sha256={hashlib.sha256(data).hexdigest()})")
    print("PASS: eight screenshot files match their documented byte sizes")
    print("INFO: screenshot history and file hashes do not prove redistribution rights")


def verify_package(package):
    pkgbuild = (ROOT / "PKGBUILD").read_text()
    source_block = re.search(r"(?ms)^source=\((.*?)^\)", pkgbuild)
    if not source_block:
        raise ValueError("Unable to find explicit PKGBUILD source list")
    sources = re.findall(r"'([^']+)'", source_block.group(1))
    if not sources or any("evidence/" in entry or entry.endswith(".png") for entry in sources):
        raise ValueError("PKGBUILD unexpectedly references evidence screenshots or image assets")

    if not package.is_file():
        raise ValueError(f"Missing built package: {package}")
    files = subprocess.run(
        ["bsdtar", "-tf", str(package)],
        check=True, text=True, capture_output=True, timeout=30
    ).stdout.splitlines()
    normalized = {p.lstrip("./") for p in files}
    if any(p.endswith(".png") or "evidence/phase4" in p for p in normalized):
        raise ValueError("Installable package unexpectedly includes screenshot/image evidence")
    license_path = "usr/share/licenses/appinstall/LICENSE"
    if license_path not in normalized:
        raise ValueError("Installable package is missing its MIT license copy")
    license_data = subprocess.run(
        ["bsdtar", "-xOf", str(package), license_path],
        check=True, capture_output=True, timeout=30
    ).stdout
    expected_license = (ROOT / "LICENSE").read_bytes()
    if not expected_license.startswith(b"MIT License\n"):
        raise ValueError("Project LICENSE file no longer contains its expected MIT notice")
    if expected_license != license_data:
        raise ValueError("Packaged MIT license differs from the checked-in LICENSE")
    print(f"PASS: package {package.name} excludes evidence screenshots")
    print("PASS: package MIT notice matches repository LICENSE bytes")
    print("INFO: dependency licensing, original source ownership and screenshots still need human sign-off")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True,
                        help="Path to freshly built, disposable CI package")
    args = parser.parse_args()
    verify_evidence()
    verify_package(args.package)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as err:
        print(f"FAIL: {err}", file=sys.stderr)
        sys.exit(1)
