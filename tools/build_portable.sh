#!/usr/bin/env bash
# Distro-neutral, versioned AppInstall source bundle. Git metadata not required.
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
output="${1:-$root/dist}"
version="$(sed -n 's/^pkgver=//p' "$root/PKGBUILD")"
cli_version="$(sed -n 's/^VERSION="\([^"]*\)"$/\1/p' "$root/appinstall")"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    echo "Invalid version in PKGBUILD" >&2; exit 1;
}
[[ "$version" == "$cli_version" ]] || {
    echo "PKGBUILD and appinstall versions disagree" >&2; exit 1;
}
for cmd in python3 tar gzip sha256sum; do
    command -v "$cmd" >/dev/null || { echo "Missing prerequisite: $cmd" >&2; exit 1; }
done
mkdir -p -- "$output"
output="$(cd -- "$output" && pwd)"
archive="$output/appinstall-$version-portable.tar.gz"
temp="$(mktemp "$output/.appinstall-portable-XXXXXXXX")"
trap 'rm -f -- "$temp"' EXIT

# Get the exact installed Python modules and QML resources from static literals
# in integration.py. Parsing does NOT import/run integration.py. Only known
# root-level entrypoints/docs and manifest files are included in the archive.
python3 - "$root" "$version" <<'PYTHON' | gzip -n -9 >"$temp"
import ast
from pathlib import Path
import sys
import tarfile

root = Path(sys.argv[1]).resolve()
version = sys.argv[2]
tree = ast.parse((root / "integration.py").read_text(encoding="utf-8"))
values = {}
for node in tree.body:
    if not isinstance(node, ast.Assign):
        continue
    for target in node.targets:
        if isinstance(target, ast.Name) and target.id in ("modules", "qml_sources", "ICON_SIZES"):
            values[target.id] = ast.literal_eval(node.value)
for required in ("modules", "qml_sources", "ICON_SIZES"):
    if required not in values:
        raise SystemExit("Missing source manifest entry: " + required)
names = {
    "appinstall", "install-user.sh", "appinstall.desktop",
    "appinstall-appimage-review.desktop", "LICENSE",
    "README.md", "INSTALL.md", "RELEASE_NOTES.md", "CHANGELOG.md",
    "KNOWN_LIMITATIONS.md", "SECURITY_REVIEW.md",
}
names.update(values["modules"])
names.update(values["qml_sources"])
names.update(f"appinstall-{size}.png" for size in values["ICON_SIZES"])
# Do not recursively archive a checkout, user files, .git, or untracked data.
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as bundle:
    for name in sorted(names):
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts:
            raise SystemExit("Unsafe source path: " + name)
        path = root / rel
        if not path.is_file() or path.is_symlink():
            raise SystemExit("Missing or unsafe portable source: " + name)
        info = bundle.gettarinfo(str(path), arcname=f"appinstall-{version}/{rel.as_posix()}")
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        info.mtime = 0
        with path.open("rb") as source:
            bundle.addfile(info, source)
PYTHON

tar -tzf "$temp" | grep -Fx "appinstall-$version/install-user.sh" >/dev/null || {
    echo "Archive lacks installer" >&2; exit 1;
}
tar -tzf "$temp" | grep -Fx "appinstall-$version/manager_ui/main.qml" >/dev/null || {
    echo "Archive lacks Discover Apps UI" >&2; exit 1;
}
mv -f -- "$temp" "$archive"
trap - EXIT
sha256sum -- "$archive"
echo "Portable AppInstall source bundle: $archive"
