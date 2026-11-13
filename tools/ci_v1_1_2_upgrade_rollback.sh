#!/usr/bin/env bash
# CI-ONLY: validate a genuine published 1.1.1 -> candidate 1.1.2 upgrade
# and rollback using a throwaway Arch Linux GitHub Actions container.
set -euo pipefail

if [[ "${GITHUB_ACTIONS:-}" != "true" || -z "${GITHUB_WORKSPACE:-}" || "$PWD" != "$GITHUB_WORKSPACE" ]]; then
  echo "Refusing to run outside a GitHub Actions workspace." >&2
  exit 2
fi
if [[ "$(id -u)" != "0" ]]; then
  echo "This gate must run as root in the disposable Arch CI container." >&2
  exit 2
fi
if pacman -Q appinstall >/dev/null 2>&1; then
  echo "Refusing: AppInstall must not already be installed in the disposable container." >&2
  exit 2
fi

candidate="$PWD/appinstall-1.1.2-1-any.pkg.tar.zst"
[[ -f "$candidate" ]] || { echo "Candidate package missing." >&2; exit 2; }
sha256sum -c SHA256SUMS

tmp="$(mktemp -d /tmp/appinstall-upgrade-rollback-XXXXXXXX)"
test -d "$tmp"
cleanup() {
  if pacman -Q appinstall >/dev/null 2>&1; then
    pacman -R --noconfirm appinstall || true
  fi
  rm -rf -- "$tmp"
}
trap cleanup EXIT

base="https://github.com/aboodmohd/-AppInstall/releases/download/v1.1.1"
stable_name="appinstall-1.1.1-1-any.pkg.tar.zst"
curl -fLsS --retry 3 --connect-timeout 20 --max-time 120 \
  "$base/$stable_name" -o "$tmp/$stable_name"
curl -fLsS --retry 3 --connect-timeout 20 --max-time 120 \
  "$base/SHA256SUMS" -o "$tmp/SHA256SUMS"
(
  cd "$tmp"
  sha256sum -c --strict SHA256SUMS
)
pacman -Qip "$tmp/$stable_name" | grep -Eq '^Version[[:space:]]*:[[:space:]]*1\.1\.1-1$'
pacman -Qip "$candidate" | grep -Eq '^Version[[:space:]]*:[[:space:]]*1\.1\.2-1$'

# These represent unrelated per-user files: package operations must not
# overwrite or modify them. All paths belong to a disposable test account.
account="appinstall_upgrade_guard"
useradd -m -s /bin/bash "$account"
home="/home/$account"
mkdir -p "$home/.local/share/appinstall/containers" "$home/.config"
printf '{"owner":"test-user","sentinel":"keep-this-registry"}\n' \
  > "$home/.local/share/appinstall/containers/registry.json"
printf '[Default Applications]\napplication/vnd.appimage=unrelated-app.desktop\n' \
  > "$home/.config/mimeapps.list"
printf 'unrelated-user-data-should-survive-upgrade-and-rollback\n' \
  > "$home/keep-my-data.txt"
chown -R "$account:$account" "$home"
(
  cd "$home"
  sha256sum \
    .local/share/appinstall/containers/registry.json \
    .config/mimeapps.list \
    keep-my-data.txt > "$tmp/expected-user-data.sha256"
)

check_data() {
  (cd "$home" && sha256sum -c --strict "$tmp/expected-user-data.sha256")
}

echo '--- Install published v1.1.1 ---'
pacman -U --noconfirm "$tmp/$stable_name"
[[ "$(appinstall --version)" == "appinstall 1.1.1" ]]
pacman -Q appinstall | grep -Fxq 'appinstall 1.1.1-1'
check_data

echo '--- Upgrade to CI-built v1.1.2 candidate ---'
pacman -U --noconfirm "$candidate"
[[ "$(appinstall --version)" == "appinstall 1.1.2" ]]
pacman -Q appinstall | grep -Fxq 'appinstall 1.1.2-1'
[[ -s /usr/bin/url_install.py && -s /usr/bin/url_dialog.py ]]
[[ -s /usr/share/licenses/appinstall/LICENSE ]]
check_data

echo '--- Roll back to published v1.1.1 ---'
pacman -U --noconfirm "$tmp/$stable_name"
[[ "$(appinstall --version)" == "appinstall 1.1.1" ]]
pacman -Q appinstall | grep -Fxq 'appinstall 1.1.1-1'
check_data

echo '--- Uninstall from disposable container ---'
pacman -R --noconfirm appinstall
! pacman -Q appinstall >/dev/null 2>&1
check_data

echo "PASS: genuine published v1.1.1 -> candidate v1.1.2 -> v1.1.1 rollback, user data preserved."
