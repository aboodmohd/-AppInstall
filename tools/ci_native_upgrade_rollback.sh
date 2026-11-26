#!/usr/bin/env bash
# Native release upgrade/downgrade gate. GitHub Actions containers ONLY.
set -euo pipefail
if [[ "$GITHUB_ACTIONS" != true || "$CI" != true ||
      "$EUID" != 0 || ! -f /.dockerenv ||
      "$APPINSTALL_DISPOSABLE_NATIVE_CI" != YES ]]; then
  echo 'Refusing: requires explicitly marked disposable root CI container.' >&2
  exit 2
fi
case "$FAMILY" in arch|debian|fedora) ;; *) exit 2 ;; esac
root="$PWD"
test "$(sed -n 's/^pkgver=//p' PKGBUILD)" = 1.9.1
test "$(sed -n 's/^pkgrel=//p' PKGBUILD)" = 1
grep -Fx 'VERSION="1.9.1"' appinstall >/dev/null
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work"/{old,new}

case "$FAMILY" in
arch)
 old=appinstall-1.9.0-1-any.pkg.tar.zst
 new=abood-appinstall-1.9.1-1-any.pkg.tar.zst
 pkgmeta() { test "$(pacman -Q appinstall)" = "appinstall $1"; }
 native_install() { pacman -U --noconfirm "$1"; }
 remove_new() { pacman -R --noconfirm abood-appinstall; }
 ;;
debian)
 old=appinstall_1.9.0-1_all.deb
 new=abood-appinstall_1.9.1-1_all.deb
 pkgmeta() {
   fmt="$(printf '$%s' '{Version}')"
   test "$(dpkg-query -W -f="$fmt" appinstall)" = "$1"
 }
 native_install() { apt-get install -y --no-install-recommends --allow-downgrades "$1"; }
 remove_new() { apt-get remove -y abood-appinstall; }
 ;;
fedora)
 old=appinstall-1.9.0-1.noarch.rpm
 new=abood-appinstall-1.9.1-1.noarch.rpm
 pkgmeta() { test "$(rpm -q --qf '%{VERSION}-%{RELEASE}' appinstall)" = "$1"; }
 native_install() { dnf -y install "$1"; }
 remove_new() { dnf -y remove --no-autoremove abood-appinstall; }
 ;;
esac
installed_helper=/usr/lib/abood-appinstall/portable_update.py
smoke=/usr/lib/abood-appinstall/manager_qml.py

case "$FAMILY" in
arch)
 useradd -m -s /bin/bash appinstall-builder
 chown -R appinstall-builder:appinstall-builder "$root"
 runuser -u appinstall-builder -- env HOME=/home/appinstall-builder \
   bash -c 'cd "$1" && makepkg --noconfirm --clean' _ "$root"
 mv "$root/$new" "$work/new/$new"
 ;;
debian) bash "$root/tools/build_deb.sh" "$work/new" ;;
fedora)
 useradd -m -s /bin/bash appinstall-builder
 chown -R appinstall-builder:appinstall-builder "$root"
 runuser -u appinstall-builder -- env HOME=/home/appinstall-builder \
   bash -c 'cd "$1" && bash tools/build_rpm.sh dist' _ "$root"
 mv -- "$root/dist/$new" "$work/new/$new"
 ;;
esac
test -s "$work/new/$new"
curl --fail --location --silent --show-error --retry 3 \
  --proto '=https' --proto-redir '=https' --connect-timeout 15 \
  --max-time 150 --output "$work/old/$old" \
  "https://github.com/aboodmohd/-AppInstall/releases/download/v1.9.0/$old"
# Verify the exact old asset against the published v1.9.0 checksum manifest.
# SHA-256 verifies archive integrity, not an independent publisher signature.
curl --fail --location --silent --show-error --retry 3 \
  --proto '=https' --proto-redir '=https' --connect-timeout 15 \
  --max-time 150 --output "$work/old/SHA256SUMS" \
  "https://github.com/aboodmohd/-AppInstall/releases/download/v1.9.0/SHA256SUMS"
matches=0
old_digest=""
while read -r digest filename; do
  if [[ "$filename" == "$old" && "$digest" =~ ^[0-9a-f]{64}$ ]]; then
    old_digest="$digest"
    matches=$((matches + 1))
  fi
done < "$work/old/SHA256SUMS"
test "$matches" -eq 1
(cd "$work/old" && printf '%s  %s\n' "$old_digest" "$old" | sha256sum -c --strict -)
echo "PASS: verified published v1.9.0 $FAMILY package against SHA256SUMS"

native_install "$work/old/$old"
pkgmeta 1.9.0-1
test "$(appinstall --version)" = 'appinstall 1.9.0'
useradd -m -s /bin/bash appinstall-acceptance
user_home=/home/appinstall-acceptance

runuser -u appinstall-acceptance -- env HOME="$user_home" python3 - <<'PYTHON'
import json
from pathlib import Path
home = Path.home()
state = home / ".local/share/appinstall"
config = home / ".config"
apps = home / "Applications"
for folder in (state, config, apps):
    folder.mkdir(parents=True, exist_ok=True)
(state / "settings.json").write_text(json.dumps({
    "theme": "dark", "favorites": ["flatpak:org.example.Preserved"],
    "notifications": True, "uninstall_mode": "ask", "last_update_check": 0
}, indent=2))
(state / "user-app-record.json").write_text(
    '{"providerKey":"flatpak:org.example.Preserved","user_owned":true}\n')
(config / "mimeapps.list").write_text(
    "[Default Applications]\ntext/plain=preserved-editor.desktop;\n")
(apps / "keep.txt").write_text("user data survives\n")
PYTHON
settings_file="$user_home/.local/share/appinstall/settings.json"
record_file="$user_home/.local/share/appinstall/user-app-record.json"
mime_file="$user_home/.config/mimeapps.list"
user_file="$user_home/Applications/keep.txt"
sha256sum "$settings_file" "$record_file" "$mime_file" "$user_file" > "$work/baseline"
check_data() {
 sha256sum -c "$work/baseline"
 runuser -u appinstall-acceptance -- env HOME="$user_home" python3 - <<'PYTHON'
import json
from pathlib import Path
doc = json.loads((Path.home()/".local/share/appinstall/settings.json").read_text())
assert doc["theme"] == "dark"
assert doc["favorites"] == ["flatpak:org.example.Preserved"]
assert doc["notifications"] is True
PYTHON
}
check_data

native_install "$work/new/$new"
pkgmeta 1.9.0-1
test "$(abood-appinstall --version)" = 'appinstall 1.9.1'
test "$(bash -c 'source ./install.sh; installed_version "$1"' _ "$FAMILY")" = 1.9.1-1
test -f "$installed_helper"
test -f "$smoke"
check_data
runuser -u appinstall-acceptance -- env HOME="$user_home" \
 XDG_DATA_HOME="$user_home/.local/share" \
 XDG_CONFIG_HOME="$user_home/.config" \
 QT_QPA_PLATFORM=offscreen APPINSTALL_DISABLE_UPDATE_TIMER=1 \
 python3 "$smoke" --smoke
echo "PASS: v1.9.0 legacy -> v1.9.1 $FAMILY identity migration preserved both packages"

remove_new
pkgmeta 1.9.0-1
test "$(appinstall --version)" = 'appinstall 1.9.0'
test ! -e "$installed_helper"
check_data
grep -Fx 'text/plain=preserved-editor.desktop;' "$mime_file"
echo "PASS: v1.9.1 -> v1.9.0 $FAMILY migration rollback with preserved settings and MIME"
