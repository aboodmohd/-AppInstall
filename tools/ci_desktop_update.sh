#!/usr/bin/env bash
# Disposable GitHub Actions container only. Never run on a desktop host.
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && "${CI:-}" == true && -f /.dockerenv && $EUID == 0 ]]
[[ ! -e /usr/bin/pkexec ]]
repo="$PWD"
fixture="$(mktemp -d)"
chmod 755 "$fixture"
trap 'rm -rf -- "$fixture"' EXIT
mkdir -p "$fixture"/{source,feed,bin}
cp -a "$repo"/. "$fixture/source/"
cd "$fixture/source"
useradd --create-home --shell /bin/bash appinstall-ci
chown -R appinstall-ci:appinstall-ci "$fixture/source"

build_package() {
    local version="$1"
    sed -i "s/^pkgver=.*/pkgver=$version/" PKGBUILD
    sed -i "s/^VERSION=.*/VERSION=\"$version\"/" appinstall
    printf '# AppInstall %s\n\nDesktop updater CI fixture.\n' "$version" > RELEASE_NOTES.md
    if [[ "$FAMILY" == arch ]]; then
        runuser -u appinstall-ci -- bash -c 'makepkg --noconfirm --skipinteg'
        mv "appinstall-$version-1-any.pkg.tar.zst" "$fixture/feed/"
    else
        bash tools/build_deb.sh "$fixture/feed"
    fi
}

build_package 1.2.2
build_package 1.2.3
cd "$fixture/feed"
if [[ "$FAMILY" == arch ]]; then
    pacman -U --noconfirm ./appinstall-1.2.2-1-any.pkg.tar.zst
    old='appinstall-1.2.2-1-any.pkg.tar.zst'
    new='appinstall-1.2.3-1-any.pkg.tar.zst'
    installer=/usr/bin/appinstall-installer
else
    apt-get install -y --no-install-recommends ./appinstall_1.2.2-1_all.deb
    old='appinstall_1.2.2-1_all.deb'
    new='appinstall_1.2.3-1_all.deb'
    installer=/usr/lib/appinstall/appinstall-installer
fi
rm -- "$old"
sha256sum "$new" > SHA256SUMS
cp SHA256SUMS correct-sums
python3 - "$new" <<'PY'
import json
import sys
from pathlib import Path

prefix = "https://github.com/aboodmohd/-AppInstall/releases/download/v1.2.3/"
Path("release.json").write_text(json.dumps({
    "tag_name": "v1.2.3", "draft": False, "prerelease": False,
    "assets": [{"name": name, "browser_download_url": prefix + name}
               for name in (sys.argv[1], "SHA256SUMS")],
}))
PY

# Redirect only the updater's expected HTTPS URLs to known local files.
cat > "$fixture/bin/curl" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
output=
args=("$@")
for ((i=0; i < ${#args[@]} - 1; i++)); do
    if [[ "${args[i]}" == -o ]]; then output="${args[i+1]}"; fi
done
case "${args[-1]}" in
    https://api.github.com/repos/aboodmohd/-AppInstall/releases/latest)
        cat "$APPINSTALL_FIXTURE/release.json" ;;
    https://github.com/aboodmohd/-AppInstall/releases/download/v1.2.3/*)
        name="${args[-1]##*/}"
        case "$name" in
            SHA256SUMS|appinstall-1.2.3-1-any.pkg.tar.zst|appinstall_1.2.3-1_all.deb)
                cp "$APPINSTALL_FIXTURE/$name" "$output" ;;
            *) exit 22 ;;
        esac ;;
    *) exit 22 ;;
esac
SHIM
chmod 755 "$fixture/bin/curl"

# Replace the authorization prompt only inside the test container.
cat > /usr/bin/pkexec <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
[[ "$1" == --disable-internal-agent ]]
shift
[[ "$1" == /usr/bin/pacman || "$1" == /usr/bin/apt-get ]]
[[ "$APPINSTALL_AUTHORIZATION" == allow ]] || exit 126
exec sudo -n -- "$@"
SHIM
chmod 755 /usr/bin/pkexec
printf '%s\n' 'appinstall-ci ALL=(root) NOPASSWD: /usr/bin/pacman, /usr/bin/apt-get' > /etc/sudoers.d/appinstall-ci
chmod 440 /etc/sudoers.d/appinstall-ci

run_update() {
    local decision="$1"
    shift
    runuser -u appinstall-ci -- env PATH="$fixture/bin:$PATH" \
        APPINSTALL_FIXTURE="$fixture/feed" APPINSTALL_AUTHORIZATION="$decision" \
        "$installer" "$@"
}

run_update deny --desktop-check | grep -Fx 'APPINSTALL_UPDATE=v1.2.3'
if run_update deny --desktop-update v1.2.3; then exit 1; fi
test "$(appinstall --version)" = 'appinstall 1.2.2'

printf '%064d  %s\n' 0 "$new" > SHA256SUMS
status=0
run_update allow --desktop-update v1.2.3 || status=$?
test "$status" -eq 3
test "$(appinstall --version)" = 'appinstall 1.2.2'
mv correct-sums SHA256SUMS

run_update allow --desktop-update v1.2.3 | grep -Fx 'APPINSTALL_UPDATED=v1.2.3'
test "$(appinstall --version)" = 'appinstall 1.2.3'
grep -Fx '# AppInstall 1.2.3' /usr/share/doc/appinstall/RELEASE_NOTES.md
output="$(run_update deny --desktop-check)"
! grep -q '^APPINSTALL_UPDATE=' <<<"$output"
