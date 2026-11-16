#!/usr/bin/env bash
# Build a portable *source* archive for distributions without a verified native
# AppInstall package. This does not bundle Qt, Python, distro libraries, or root.
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
output="${1:-$root/dist}"
version="$(sed -n 's/^pkgver=//p' "$root/PKGBUILD")"
cli_version="$(sed -n 's/^VERSION="\([^"]*\)"$/\1/p' "$root/appinstall")"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    echo "Invalid package version" >&2
    exit 1
}
[[ "$version" == "$cli_version" ]] || {
    echo "Package and CLI version mismatch" >&2
    exit 1
}
command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
command -v tar >/dev/null || { echo "tar is required" >&2; exit 1; }
command -v gzip >/dev/null || { echo "gzip is required" >&2; exit 1; }
mkdir -p -- "$output"
output="$(cd -- "$output" && pwd)"
archive="$output/appinstall-$version-portable.tar.gz"
temp="$(mktemp "$output/.appinstall-portable-XXXXXXXX")"
trap 'rm -f -- "$temp"' EXIT

# Archive tracked release source only, under a single directory. No downloaded
# executable, vendored dependency, or system-level install is included.
git -C "$root" archive --format=tar --prefix="appinstall-$version/" HEAD |
    gzip -n -9 >"$temp"

# Ensure the expected source/user installer is actually included in the archive.
tar -tzf "$temp" | grep -Fx "appinstall-$version/install-user.sh" >/dev/null || {
    echo "Portable archive is missing install-user.sh" >&2
    exit 1
}
tar -tzf "$temp" | grep -Fx "appinstall-$version/manager_ui/main.qml" >/dev/null || {
    echo "Portable archive is missing the Discover Apps UI" >&2
    exit 1
}
mv -f -- "$temp" "$archive"
trap - EXIT
sha256sum -- "$archive"
echo "Portable source release: $archive"
