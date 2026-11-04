#!/usr/bin/env bash
# Disposable Arch CI container ONLY: clean pacman install, runtime smoke,
# and removal without changing an unrelated user profile.
set -euo pipefail

if [[ "$(printenv CI 2>/dev/null || true)" != "true" ||
      "$(printenv GITHUB_ACTIONS 2>/dev/null || true)" != "true" ]]; then
  echo "Refusing to run package lifecycle test outside CI." >&2
  exit 2
fi
if [[ "$(id -u)" != 0 ]]; then
  echo "Requires root inside the disposable Arch CI container." >&2
  exit 2
fi
if [[ $# != 2 ]]; then
  echo "Usage: arch_clean_install_gate.sh PACKAGE EXPECTED_CLI_VERSION" >&2
  exit 2
fi
package=$1
expected=$2
[[ -f "$package" ]] || { echo "Built package missing" >&2; exit 2; }
if pacman -Qq appinstall >/dev/null 2>&1; then
  echo "Refusing: AppInstall should not be installed before the clean-install gate" >&2
  exit 2
fi

# Create a fake user in the disposable container, never the real user's HOME.
username=appinstall-check
if id "$username" >/dev/null 2>&1; then
  echo "Refusing to use an existing account" >&2
  exit 2
fi
useradd --create-home --shell /bin/bash "$username"
home=$(getent passwd "$username" | cut -d: -f6)
[[ "$home" == "/home/$username" ]] || exit 2
config="$home/.config"
data="$home/.local/share"
mkdir -p "$config" "$data/applications" "$data/appinstall/containers" "$home/Applications"
cat >"$config/mimeapps.list" <<'EOF'
[Default Applications]
application/vnd.flatpak=another-installer.desktop;
application/x-rpm=another-rpm.desktop;
text/plain=editor.desktop;
EOF
cat >"$data/applications/unrelated.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Unrelated User App
Exec=/bin/true
EOF
cat >"$data/appinstall/containers/registry.json" <<'EOF'
{"deb:keep":{"name":"Retain Existing User Registry","status":"installed"}}
EOF
printf 'preserve existing appimage\n' >"$home/Applications/keep.AppImage"
chown -R "$username:$username" "$home"

snapshot() {
  local path
  for path in \
    "$config/mimeapps.list" \
    "$data/applications/unrelated.desktop" \
    "$data/appinstall/containers/registry.json" \
    "$home/Applications/keep.AppImage"; do
    sha256sum "$path"
    stat -c '%a' "$path"
  done
}
before=$(snapshot)
verify_user_data() {
  if [[ "$(snapshot)" != "$before" ]]; then
    echo "Package lifecycle changed unrelated user files, modes or MIME defaults" >&2
    exit 1
  fi
}

# Package path must be owned by pacman. Source registration must not run.
pacman -U --noconfirm "$package"
pacman -Qq appinstall >/dev/null
[[ "$(appinstall --version)" == "appinstall $expected" ]]
[[ -f /usr/share/applications/appinstall.desktop ]]
[[ -f /usr/share/licenses/appinstall/LICENSE ]]
cmp -s LICENSE /usr/share/licenses/appinstall/LICENSE
[[ -f /usr/bin/manager.py && -f /usr/bin/diagnostics_ui.py ]]
[[ ! -e "$data/applications/appinstall.desktop" ]]
[[ ! -e "$home/.local/bin/appinstall" ]]
[[ ! -e "$data/appinstall/associations.json" ]]
runuser -u "$username" -- env \
  HOME="$home" XDG_CONFIG_HOME="$config" XDG_DATA_HOME="$data" \
  QT_QPA_PLATFORM=offscreen appinstall --version | grep -Fx "appinstall $expected"
runuser -u "$username" -- env \
  HOME="$home" XDG_CONFIG_HOME="$config" XDG_DATA_HOME="$data" \
  QT_QPA_PLATFORM=offscreen appinstall --list >/dev/null
verify_user_data
echo "PASS: clean package installation left user defaults and data unchanged"

# Remove the system package, not the user source registration or applications.
pacman -R --noconfirm appinstall
if pacman -Qq appinstall >/dev/null 2>&1; then
  echo "Pacman still reports AppInstall installed after removal" >&2
  exit 1
fi
[[ ! -e /usr/bin/appinstall ]]
[[ ! -e /usr/share/applications/appinstall.desktop ]]
[[ ! -e /usr/share/licenses/appinstall/LICENSE ]]
verify_user_data
echo "PASS: package uninstall left MIME defaults, managed records and user files unchanged"
