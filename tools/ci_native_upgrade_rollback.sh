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
test "$(sed -n 's/^pkgver=//p' PKGBUILD)" = 1.8.0
test "$(sed -n 's/^pkgrel=//p' PKGBUILD)" = 1
grep -Fx 'VERSION="1.8.0"' appinstall >/dev/null
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work"/{old,new}

case "$FAMILY" in
arch)
 old=appinstall-1.7.0-1-any.pkg.tar.zst
 new=appinstall-1.8.0-1-any.pkg.tar.zst
 old_sha=722c4b2cb6211f92de9a4d21047e3aa5c6e4a281644faf9a8779f878c562f917
 pkgmeta() { test "$(pacman -Q appinstall)" = "appinstall $1"; }
 native_install() { pacman -U --noconfirm "$1"; }
 installed_helper=/usr/bin/portable_update.py
 smoke=/usr/bin/manager_qml.py
 ;;
debian)
 old=appinstall_1.7.0-1_all.deb
 new=appinstall_1.8.0-1_all.deb
 old_sha=d276dacca8a9338f29a60576207134f5daa9167fd2f25bbb4cacbe2a7ace6bfb
 pkgmeta() {
   fmt="$(printf '$%s' '{Version}')"
   test "$(dpkg-query -W -f="$fmt" appinstall)" = "$1"
 }
 native_install() { apt-get install -y --no-install-recommends --allow-downgrades "$1"; }
 installed_helper=/usr/lib/appinstall/portable_update.py
 smoke=/usr/lib/appinstall/manager_qml.py
 ;;
fedora)
 old=appinstall-1.7.0-1.noarch.rpm
 new=appinstall-1.8.0-1.noarch.rpm
 old_sha=f953a4c163773d922ace262f1163c085057d2c16ad6d361a369030b961f333db
 pkgmeta() { test "$(rpm -q --qf '%{VERSION}-%{RELEASE}' appinstall)" = "$1"; }
 native_install() {
   if rpm -q appinstall >/dev/null 2>&1; then
     installed="$(rpm -q --qf '%{VERSION}' appinstall)"
     if [[ "$installed" == 1.8.0 ]]; then dnf -y downgrade "$1";
     else dnf -y upgrade "$1"; fi
   else dnf -y install "$1"; fi
 }
 installed_helper=/usr/lib/appinstall/portable_update.py
 smoke=/usr/lib/appinstall/manager_qml.py
 ;;
esac

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
  "https://github.com/aboodmohd/-AppInstall/releases/download/v1.7.0/$old"
printf '%s  %s\n' "$old_sha" "$work/old/$old" | sha256sum -c -
echo "PASS: verified authentic published v1.7.0 $FAMILY package"

native_install "$work/old/$old"
pkgmeta 1.7.0-1
test "$(appinstall --version)" = 'appinstall 1.7.0'
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
pkgmeta 1.8.0-1
test "$(appinstall --version)" = 'appinstall 1.8.0'
test -f "$installed_helper"
test -f "$smoke"
check_data
runuser -u appinstall-acceptance -- env HOME="$user_home" \
 XDG_DATA_HOME="$user_home/.local/share" \
 XDG_CONFIG_HOME="$user_home/.config" \
 QT_QPA_PLATFORM=offscreen APPINSTALL_DISABLE_UPDATE_TIMER=1 \
 python3 "$smoke" --smoke
echo "PASS: v1.7.0 -> v1.8.0 $FAMILY native upgrade"

native_install "$work/old/$old"
pkgmeta 1.7.0-1
test "$(appinstall --version)" = 'appinstall 1.7.0'
test ! -e "$installed_helper"
check_data
grep -Fx 'text/plain=preserved-editor.desktop;' "$mime_file"
echo "PASS: v1.8.0 -> v1.7.0 $FAMILY native downgrade with preserved settings and MIME"
