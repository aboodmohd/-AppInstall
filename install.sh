#!/usr/bin/env bash
#
# AppInstall — one-command installer (stable releases, Arch/CachyOS first).
#
# One-command use:
#   curl -fsSL https://raw.githubusercontent.com/aboodmohd/-AppInstall/main/install.sh | bash
#
# What this script does:
#   1. Detects distribution family, architecture and desktop environment.
#   2. Resolves the latest GitHub *stable* release (drafts and prereleases are
#      never used).
#   3. Downloads the package and its SHA256SUMS manifest and verifies the
#      checksum before anything else happens.
#   4. Installs with the native package manager (pacman). The script runs as
#      the invoking user; only the single pacman command is elevated, with its
#      stdin handed back to the terminal so `curl | bash` keeps working.
#   5. Offers to install missing optional backends via pacman.
#   6. Offers ONE clear confirmation to make AppInstall the default handler
#      for every MIME type advertised in appinstall.desktop. Previous per-user
#      defaults are backed up first and a restore script is written.
#
# What this script NEVER does:
#   - never executes AppInstall itself, and never runs it as root;
#   - never auto-creates Distrobox containers or runs third-party packages;
#   - never touches system-wide MIME configuration (per-user only);
#   - never silently replaces an existing installation without asking;
#   - never installs an Arch package with another distro's package manager;
#   - never pipes remote content into sudo.
#
# Exit codes: 0 ok, 1 generic error, 2 unsupported environment or refused
# conflict, 3 checksum verification failure, 4 network/API failure,
# 5 package installation failure, 130 interrupted.

# Propagate strictness when sourced into a test harness too. Function bodies
# assume errexit/unset-nounset exist (this file is bash >= 4 only).
set -euo pipefail

REPO_SLUG="aboodmohd/-AppInstall"
API_BASE="https://api.github.com"
RAW_URL="https://raw.githubusercontent.com/${REPO_SLUG}/main/install.sh"

DESKTOP_ID="appinstall.desktop"
APP_BIN="/usr/bin/appinstall"
APP_LOCAL_BIN="$HOME/.local/bin/appinstall"

# Every MIME type advertised in appinstall.desktop (handlers + aliases).
MIME_TYPES=(
  "application/vnd.debian.binary-package"
  "application/x-deb"
  "application/x-rpm"
  "application/vnd.flatpak"
  "application/vnd.flatpak.ref"
  "application/vnd.flatpak.repo"
  "application/vnd.appimage"
  "application/x-iso9660-appimage"
  "application/x-quickdrop-appimage"
)

# Distribution IDs enabled without extra consent (tested systems only).
SUPPORTED_IDS="arch cachyos"

# Optional backends offered after core installation (pacman package names).
OPTIONAL_PKGS=(flatpak podman distrobox squashfs-tools fuse2 kdialog zenity libnotify)

INSTALLER_VERSION="1.0.0"

# ---------------------------------------------------------------------------
# Flags / state. Defaults respect pre-existing environment values so the test
# harness (and CI) can inject flags via env vars; parse_flags() overrides them
# from real command-line arguments.
# ---------------------------------------------------------------------------
DRY_RUN="${DRY_RUN:-0}"
ASSUME_YES="${ASSUME_YES:-0}"
SET_DEFAULTS="${SET_DEFAULTS:-0}"
NO_DEFAULTS="${NO_DEFAULTS:-0}"
WITH_OPTIONAL="${WITH_OPTIONAL:-0}"
NO_OPTIONAL="${NO_OPTIONAL:-0}"
ALLOW_ARCH_LIKE="${ALLOW_ARCH_LIKE:-0}"
REMOVE_SOURCE_INSTALL="${REMOVE_SOURCE_INSTALL:-0}"
UNINSTALL="${UNINSTALL:-0}"

# Test hooks (only used by tests/test_install_sh.py and CI; undocumented on
# purpose so they don't become false compatibility claims in real usage).
TEST_OS_RELEASE="${APPINSTALL_TEST_OS_RELEASE:-}"
TEST_RELEASES_JSON="${APPINSTALL_TEST_RELEASES_JSON:-}"

STATE_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/appinstall/installer"
LOG_FILE=""
TMP_DIR=""
TTY_OK=0

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
info() { printf '==> %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
bad()  { printf 'ERROR: %s\n' "$*" >&2; }
die()  { local code="$1"; shift; bad "$*"; exit "$code"; }

log_write() {
  if [[ -n "$LOG_FILE" ]]; then
    printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >>"$LOG_FILE" 2>/dev/null || true
  fi
}

cleanup() { [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]] && rm -rf -- "$TMP_DIR" || true; }
trap cleanup EXIT
trap 'bad "Interrupted."; exit 130' INT TERM

# ---------------------------------------------------------------------------
# Basic tool checks
# ---------------------------------------------------------------------------
have_cmd() { command -v "$1" >/dev/null 2>&1; }

need_cmds() {
  local missing=() c
  for c in "$@"; do
    have_cmd "$c" || missing+=("$c")
  done
  if ((${#missing[@]})); then
    bad "Missing required tools: ${missing[*]}"
    return 2
  fi
  return 0
}

# ---------------------------------------------------------------------------
# Distribution detection (pure bash against os-release)
# ---------------------------------------------------------------------------
os_release_file() { printf '%s\n' "${TEST_OS_RELEASE:-/etc/os-release}"; }

read_os_release() { # -> "id|id_like"
  local file id="" id_like=""
  file="$(os_release_file)"
  [[ -r $file ]] || return 1
  local line
  while IFS= read -r line; do
    case $line in
      ID=\'*|ID=*)       id="${line#ID=}";       id="${id#\'}"; id="${id%\'}"; id="${id#\"}"; id="${id%\"}" ;;
      ID_LIKE=\'*|ID_LIKE=*) id_like="${line#ID_LIKE=}"; id_like="${id_like#\'}"; id_like="${id_like%\'}"; id_like="${id_like#\"}"; id_like="${id_like%\"}" ;;
    esac
  done <"$file"
  [[ -n "$id" ]] || return 1
  printf '%s|%s\n' "$id" "$id_like"
}

# "family" groups distros by packaging ecosystem. Issuing anything but "arch"
# is how this installer stays honest: it never installs Arch packages via
# another package manager.
detect_family() {
  local fields id rest
  if ! fields="$(read_os_release)"; then printf 'unknown\n'; return 0; fi
  id="${fields%%|*}"
  rest="${fields#*|}"
  case "$id" in
    arch|cachyos|endeavouros|manjaro|artix|garuda) printf 'arch\n'; return 0 ;;
  esac
  if [[ "$rest" == *arch* ]]; then printf 'arch\n'; return 0; fi
  case "$id" in
    debian|ubuntu|linuxmint|pop|elementary|zorin|kali|neon|mx) printf 'debian\n'; return 0 ;;
    fedora|rhel|centos|rocky|alma|nobara|bazzite) printf 'fedora\n'; return 0 ;;
    opensuse*|sles) printf 'opensuse\n'; return 0 ;;
  esac
  if [[ "$rest" == *debian* || "$rest" == *ubuntu* ]]; then printf 'debian\n'; return 0; fi
  if [[ "$rest" == *fedora* || "$rest" == *rhel* || "$rest" == *suse* ]]; then
    printf 'fedora\n'; return 0
  fi
  printf 'unknown\n'
}

detect_distro_id() {
  local fields
  if ! fields="$(read_os_release)"; then printf 'unknown\n'; return 0; fi
  printf '%s\n' "${fields%%|*}"
}

detect_arch() { uname -m; }

detect_de() {
  local de="${XDG_CURRENT_DESKTOP:-}"
  case "$de" in
    *KDE*|*Plasma*) printf 'kde\n' ;;
    *GNOME*) printf 'gnome\n' ;;
    *XFCE*) printf 'xfce\n' ;;
    "") printf 'unknown\n' ;;
    *) printf '%s\n' "$(printf '%s' "$de" | tr 'A-Z:' 'a-z-')" ;;
  esac
}

# ---------------------------------------------------------------------------
# Interactive prompts (never read stdin — always /dev/tty)
# ---------------------------------------------------------------------------
prepare_tty() {
  if [[ -r /dev/tty ]] && ( : </dev/tty ) 2>/dev/null; then
    TTY_OK=1
    TTY_IN="/dev/tty"
    TTY_OUT="/dev/tty"
  else
    TTY_OK=0
    TTY_IN=""
    TTY_OUT=""
  fi
}

tty_read_line() { # prompt -> prints answer
  local prompt="$1" line=""
  printf '%s' "$prompt" >"$TTY_OUT" 2>/dev/null || return 1
  IFS= read -r line <"$TTY_IN" || return 1
  printf '%s\n' "$line"
}

# ask "question" default(y|n): returns 0 for yes, 1 for no.
ask() {
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '[dry-run] would ask: %s\n' "$1"
    return 1
  fi
  if [[ $ASSUME_YES -eq 1 ]]; then
    printf '%s [y] (auto-yes)\n' "$1"
    return 0
  fi
  if [[ $TTY_OK -eq 0 ]]; then
    printf 'noninteractive: action requires consent: %s\n' "$1" >&2
    return 1
  fi
  local answer
  if [[ "$2" == "y" ]]; then
    answer="$(tty_read_line "$1 [Y/n] ")" || answer="n"
  else
    answer="$(tty_read_line "$1 [y/N] ")" || answer="n"
  fi
  case "$answer" in
    [Yy]|[Yy][Ee][Ss]*) return 0 ;;
    *) return 1 ;;
  esac
}

# ---------------------------------------------------------------------------
# Privileged execution (least privilege; stdin handback to terminal)
# ---------------------------------------------------------------------------
run_root() {
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '[dry-run] (root) %s\n' "$*"
    return 0
  fi
  if ((EUID == 0)); then
    "$@"
  elif have_cmd sudo; then
    if [[ $TTY_OK -eq 1 ]]; then
      sudo -- "$@" <"$TTY_IN"
    elif sudo -n true >/dev/null 2>&1; then
      # Non-interactive context where passwordless (NOPASSWD) sudo is
      # configured (CI containers). Never blocks on a password prompt.
      sudo -n -- "$@"
    else
      bad "No interactive terminal for the sudo password prompt, and passwordless sudo is not configured."
      bad "Run this installer from a real terminal, or configure NOPASSWD sudo for automation."
      return 2
    fi
  else
    bad "Neither root (EUID=0) nor sudo was available; cannot run: $*"
    return 2
  fi
}

# ---------------------------------------------------------------------------
# Release discovery (GitHub stable releases only)
# ---------------------------------------------------------------------------
api_get() { # path -> stdout
  local token="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
  if [[ -n "$TEST_RELEASES_JSON" ]]; then
    cat -- "$TEST_RELEASES_JSON"
    return 0
  fi
  if [[ -n "$token" ]]; then
    curl -fsSL -H "Accept: application/vnd.github+json" -H "Authorization: Bearer $token" "${API_BASE}$1"
  else
    curl -fsSL -H "Accept: application/vnd.github+json" "${API_BASE}$1"
  fi
}

# resolve_release -> "tag|pkg_url|sums_url|pkg_name"
resolve_release() {
  local json tag u
  json="$(api_get "/repos/${REPO_SLUG}/releases/latest")" || return 4
  # grep -oE prints every URL as its own line regardless of how the JSON is
  # formatted (grep -o is per-match, so greedy .* cannot collapse matches).
  tag="$(printf '%s' "$json" | grep -oE '"tag_name"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | head -n1 | sed 's/.*: *"//; s/"$//')"
  [[ -n "$tag" ]] || return 4
  local pkg_url="" sums_url="" pkg_name=""
  while IFS= read -r u; do
    [[ -z "$u" ]] && continue
    u="${u#*: \"}"
    u="${u%\"}"
    # Match against the basename so both https:// and file:// URLs work.
    local base="${u##*/}"
    case "$base" in
      appinstall-*.pkg.tar.zst) pkg_url="$u"; pkg_name="$base" ;;
      SHA256SUMS)              sums_url="$u" ;;
    esac
  done < <(printf '%s' "$json" | grep -oE '"browser_download_url"[[:space:]]*:[[:space:]]*"[^"]*"')
  [[ -n "$pkg_url" && -n "$sums_url" && -n "$pkg_name" ]] || return 4
  printf '%s|%s|%s|%s\n' "$tag" "$pkg_url" "$sums_url" "$pkg_name"
}

# ---------------------------------------------------------------------------
# Download + checksum verification
# ---------------------------------------------------------------------------
download_to() { # url dest
  curl -fsSL --retry 2 -o "$2" "$1" || { rm -f -- "$2"; return 4; }
  chmod 0644 "$2" 2>/dev/null || true
}

# verify_checksums dir pkg_name — exactly one matching line must validate.
verify_checksums() {
  local dir="$1" pkg="$2" count
  count="$(awk -v f="$pkg" '$NF == f { n++ } END { print n+0 }' "$dir/SHA256SUMS")"
  ((count == 1)) || return 3
  (cd "$dir" && sha256sum --check --strict SHA256SUMS >/dev/null 2>&1) || return 3
  return 0
}

# ---------------------------------------------------------------------------
# Existing installation and conflict handling
# ---------------------------------------------------------------------------
installed_version() { # -> version string, empty when absent
  pacman -Q appinstall 2>/dev/null | awk '{print $2}'
}

version_relation() { # a b -> a>b:1  a==b:0  a<b:-1  (empty comparison generic)
  if have_cmd vercmp; then
    local r
    r="$(vercmp "$1" "$2")" || r="?"
    case "$r" in 1) printf 'gt\n';; 0) printf 'eq\n';; -1) printf 'lt\n';; *) printf 'unk\n';; esac
    return 0
  fi
  [[ "$1" == "$2" ]] && { printf 'eq\n'; return 0; }
  printf 'unk\n'
}

# Returns 0 when no blocking conflict remains; may remove with consent, else exits.
check_shadow_conflicts() {
  local found=0
  [[ -e "$APP_LOCAL_BIN" ]] && found=$((found+1))
  [[ -e "/usr/local/bin/appinstall" ]] && found=$((found+1))
  if ((found == 0)); then
    return 0
  fi
  warn "A user-local AppInstall installation was found that would shadow /usr/bin/appinstall:"
  [[ -e "$APP_LOCAL_BIN" ]] && warn "  $APP_LOCAL_BIN"
  [[ -e "/usr/local/bin/appinstall" ]] && warn "  /usr/local/bin/appinstall"
  info "Records, containers and settings under ~ are never touched by cleanup."
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '[dry-run] would ask to remove the conflicting source install first\n'
    return 0
  fi
  local consented=0
  if [[ $REMOVE_SOURCE_INSTALL -eq 1 ]]; then
    # Explicit opt-in flag: the only noninteractive way to authorize removal.
    consented=1
  elif [[ $TTY_OK -eq 1 && $DRY_RUN -eq 0 ]]; then
    # Interactive terminal only. --yes / ASSUME_YES does NOT authorize source
    # removal: removing an existing installation is a destructive decision that
    # always needs either --remove-source-install or a live confirmation.
    ask "Remove the conflicting user-local AppInstall now (runs its uninstaller; your records, containers and settings are preserved)?" n && consented=1
  fi
  if ((consented == 0)); then
    bad "Refusing to continue while a user-local AppInstall shadows the package. See INSTALL.md."
    bad "Re-run with --remove-source-install if you want it removed, or remove it manually first."
    exit 2
  fi
  if [[ -e "$APP_LOCAL_BIN" && -x "$HOME/.local/bin/appinstall-uninstall" ]]; then
    "$HOME/.local/bin/appinstall-uninstall" || warn "User-uninstall script exited nonzero; continuing — re-run it manually if problems remain."
  fi
  [[ ! -e "$APP_LOCAL_BIN" ]] || { rm -f -- "$APP_LOCAL_BIN"; warn "Leftover $APP_LOCAL_BIN removed."; }
  if [[ -e "/usr/local/bin/appinstall" ]]; then
    bad "/usr/local/bin/appinstall is outside this installer's scope — remove it manually (usually a leftover of a manual copy), then re-run."
    exit 2
  fi
  log_write "shadow-conflict-cleared"
  return 0
}

# ---------------------------------------------------------------------------
# Per-user MIME default management (backup → set → restore)
# ---------------------------------------------------------------------------
STATE_BACKUP_TSV="${STATE_DIR}/previous-mime-defaults.tsv"
STATE_RESTORE_SCRIPT="${STATE_DIR}/restore-mime-defaults.sh"

mimeapps_path() {
  printf '%s/mimeapps.list\n' "${XDG_CONFIG_HOME:-$HOME/.config}"
}

xdg_query_default() { xdg-mime query default "$1" 2>/dev/null || printf '\n'; }

backup_mime_defaults() { # idempotent: first backup wins; returns backup path
  mkdir -p "$STATE_DIR"
  if [[ -f "$STATE_BACKUP_TSV" ]]; then
    log_write "backup-kept path=$STATE_BACKUP_TSV"
    printf '%s\n' "$STATE_BACKUP_TSV"
    return 0
  fi
  local mime prev
  for mime in "${MIME_TYPES[@]}"; do
    prev="$(xdg_query_default "$mime")"
    printf '%s\t%s\n' "$mime" "$prev" >>"$STATE_BACKUP_TSV"
  done
  if [[ -f "$(mimeapps_path)" ]]; then
    cp -p -- "$(mimeapps_path)" "${STATE_DIR}/previous-mimeapps.list.bak" || true
  fi
  chmod 600 "$STATE_BACKUP_TSV" 2>/dev/null || true
  log_write "backup-created path=$STATE_BACKUP_TSV"
  printf '%s\n' "$STATE_BACKUP_TSV"
}

write_restore_script() {
  mkdir -p "$STATE_DIR"
  cat >"$STATE_RESTORE_SCRIPT" <<'RESTORE'
#!/usr/bin/env bash
# Restores the per-user MIME defaults that were active before AppInstall was
# made the default handler for supported package formats. Written by install.sh.
# Per-user only; never touches system-wide settings; safe to run repeatedly.
set -u
TSV="${XDG_DATA_HOME:-$HOME/.local/share}/appinstall/installer/previous-mime-defaults.tsv"
MIMEAPPS="${XDG_CONFIG_HOME:-$HOME/.config}/mimeapps.list"
if [[ ! -r "$TSV" ]]; then
  echo "No saved MIME default backup found at: $TSV" >&2
  echo "Nothing to restore." >&2
  exit 0
fi
if [[ ! -f "$MIMEAPPS" ]]; then
  mkdir -p -- "${MIMEAPPS%/*}" 2>/dev/null || true
fi
if ! touch "$MIMEAPPS" 2>/dev/null; then
  echo "Cannot write $MIMEAPPS" >&2
  exit 1
fi
python3 - "$TSV" "$MIMEAPPS" <<'PY'
import os
import sys
tsv_path, mimeapps_path = sys.argv[1], sys.argv[2]
DESKTOP_ID = "appinstall.desktop"

ours = set()   # every MIME the installer may have set a default for
prev = {}      # only those that had a non-empty previous default
for raw in open(tsv_path, encoding="utf-8"):
    line = raw.rstrip("\n")
    if not line or "\t" not in line:
        continue
    mime, val = line.split("\t", 1)
    ours.add(mime)
    if val.strip():
        prev[mime] = val.strip()


def current_default(mime):
    """Read the current default handler for a MIME type from mimeapps.list."""
    if not os.path.exists(mimeapps_path):
        return ""
    insec = False
    for line in open(mimeapps_path, encoding="utf-8"):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            insec = s == "[Default Applications]"
            continue
        if insec and "=" in s:
            key, val = s.split("=", 1)
            if key.strip() == mime:
                return val.strip().rstrip(";").strip()
    return ""


try:
    text = open(mimeapps_path, encoding="utf-8").read()
except FileNotFoundError:
    text = ""
# Snapshot what is currently set for each installer-managed MIME *before* we
# rewrite the section, so user changes made after installation are preserved.
current = {}
for mime in ours:
    current[mime] = current_default(mime)
lines = text.splitlines()
out = []
section = None
for ln in lines:
    s = ln.strip()
    if s.startswith("[") and s.endswith("]"):
        section = s[1:-1]
        out.append(ln)
        continue
    if section == "Default Applications" and "=" in s:
        key = s.split("=", 1)[0].strip()
        if key in ours:
            continue  # drop installer defaults; re-applied below per rules
    out.append(ln)
if not any(s.strip() == "[Default Applications]" for s in out):
    out.append("[Default Applications]")
idx = next(i for i, s in enumerate(out) if s.strip() == "[Default Applications]")
inserted = 0
for mime in ours:
    cur = current[mime]
    if cur == DESKTOP_ID:
        # AppInstall is still the default: revert to the pre-install value
        # (or remove the entry if it was unset before installation).
        val = prev.get(mime)
        if val is None:
            continue
        entry = val
    else:
        # The user (or another tool) changed this default after installation.
        # Preserve their current choice.
        entry = cur
    if any(s.split("=", 1)[0].strip() == mime for s in out[idx + 1:] if "=" in s):
        continue
    out.insert(idx + 1 + inserted, f"{mime}={entry}")
    inserted += 1
open(mimeapps_path, "w", encoding="utf-8").write("\n".join(out) + "\n")
print(f"Restored defaults where AppInstall is still set; user-made changes after installation were preserved.")
PY
if command -v xdg-mime >/dev/null 2>&1; then
  while IFS=$'\t' read -r mime p; do
    [[ -n "$p" ]] && xdg-mime default "$p" "$mime" >/dev/null 2>&1 || true
  done <"$TSV"
fi
if command -v kbuildsycoca6 >/dev/null 2>&1; then
  kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${XDG_DATA_HOME:-$HOME/.local/share}/applications" >/dev/null 2>&1 || true
fi
echo "Per-user MIME defaults restoration attempted."
RESTORE
  chmod 0700 "$STATE_RESTORE_SCRIPT"
}

set_mime_defaults() {
  local mime got ok=0 fail=0
  for mime in "${MIME_TYPES[@]}"; do
    if xdg-mime default "$DESKTOP_ID" "$mime" >/dev/null 2>&1; then
      got="$(xdg_query_default "$mime")"
      if [[ "$got" == "$DESKTOP_ID" ]]; then
        ok=$((ok + 1))
      else
        fail=$((fail + 1))
        warn "Default for $mime did not resolve to $DESKTOP_ID (got '${got}')."
      fi
    else
      fail=$((fail + 1))
      warn "xdg-mime failed for $mime."
    fi
  done
  if ((ok == ${#MIME_TYPES[@]} && fail == 0)); then
    info "Default handler set for all ${#MIME_TYPES[@]} supported package MIME types (per-user only)."
    log_write "set-mime-defaults ok=$ok"
  else
    warn "Applied $ok of ${#MIME_TYPES[@]} defaults ($fail unresolved). Reset any time:"
    warn "  $STATE_RESTORE_SCRIPT"
    log_write "set-mime-defaults ok=$ok fail=$fail"
  fi
}

maybe_set_defaults() {
  if [[ $NO_DEFAULTS -eq 1 ]]; then
    info "Skipping file-association changes (--no-defaults)."
    return 0
  fi
  local fam
  fam="$(detect_family)"
  if [[ "$fam" != "arch" ]]; then
    return 0
  fi
  if ! have_cmd xdg-mime; then
    warn "xdg-mime not found (xdg-utils). Cannot manage per-user defaults; skipping."
    return 0
  fi
  local want=0
  if [[ $SET_DEFAULTS -eq 1 ]]; then
    want=1
  elif [[ $DRY_RUN -eq 1 ]]; then
    printf '[dry-run] would ask: make AppInstall the default handler for AppImage/Flatpak/DEB/RPM files (9 MIME types)?\n'
    return 0
  elif ask "Make AppInstall the default application for AppImage, Flatpak, DEB and RPM files (all 9 advertised MIME types)? Your previous per-user defaults are backed up and can be restored." n; then
    want=1
  fi
  if ((want == 0)); then
    info "Keeping existing file associations. You can set defaults later with:"
    info "  xdg-mime default $DESKTOP_ID application/vnd.appimage   (repeat for other types)"
    return 0
  fi
  backup_mime_defaults >/dev/null
  write_restore_script
  set_mime_defaults
  info "Backup of previous defaults: $STATE_BACKUP_TSV"
  info "Restore script (safe):        $STATE_RESTORE_SCRIPT"
}

# ---------------------------------------------------------------------------
# Optional backends and container readiness
# ---------------------------------------------------------------------------
missing_optional_pkgs() { # prints missing, one per line
  local p
  for p in "${OPTIONAL_PKGS[@]}"; do
    pacman -Q -- "$p" >/dev/null 2>&1 || printf '%s\n' "$p"
  done
}

audit_optional_backends() {
  local missing
  missing="$(missing_optional_pkgs)"
  if [[ -z "$missing" ]]; then
    info "Optional backends: all present (flatpak, podman, distrobox, squashfs-tools, fuse2, kdialog/zenity, libnotify)."
    return 0
  fi
  local display
  display="$(tr '\n' ', ' <<<"$missing")"
  display="${display%%,}"
  info "Optional backends not installed: $display"
  local want=0
  if [[ $WITH_OPTIONAL -eq 1 ]]; then
    want=1
  elif [[ $NO_OPTIONAL -eq 0 && $DRY_RUN -eq 0 ]]; then
    ask "Install the optional backends above with pacman? Recommended for Flatpak/AppImage preview and DEB/RPM via Distrobox." n && want=1
  elif [[ $DRY_RUN -eq 1 ]]; then
    printf '[dry-run] would ask to install optional backends\n'
  fi
  if ((want == 0)); then
    info "Skipping optional backends. Add later with: sudo pacman -S --needed --asdeps flatpak podman distrobox squashfs-tools fuse2"
    return 0
  fi
  mapfile -t to_install <<<"$missing"
  info "Installing optional backends: ${to_install[*]}"
  if ! run_root pacman -S --needed --asdeps "${to_install[@]}"; then
    warn "Optional backend installation had errors — AppInstall core still works; review pacman's output."
    return 0
  fi
  log_write "optional-backends-installed $(echo "$missing" | tr '\n' ' ')"
}

rootless_podman_report() {
  if ! have_cmd podman; then
    info "Podman not present — DEB/RPM via Distrobox stays unavailable until installed."
    return 0
  fi
  if podman unshare true >/dev/null 2>&1; then
    info "Rootless Podman verified working (user namespaces OK)."
    if have_cmd distrobox; then
      info "Distrobox present. Containers are NOT created by setup — only when you install your first .deb/.rpm with AppInstall."
    else
      warn "Distrobox missing; install 'distrobox' for DEB/RPM support."
    fi
  else
    warn "Podman present but rootless user namespaces do not work yet (podman unshare failed)."
    warn "Often fixed by logging out/in once (user session restart) or enabling user namespaces."
    warn "AppInstall itself works; only DEB/RPM-through-Distrobox needs this."
    log_write "rootless-podman-unshare-failed"
  fi
}

# ---------------------------------------------------------------------------
# Package install
# ---------------------------------------------------------------------------
package_version_from_asset() { # appinstall-1.0.0-1-any.pkg.tar.zst -> 1.0.0-1
  local base="${1##*/}"
  base="${base%.pkg.tar.zst}"
  base="${base%-any}"
  printf '%s\n' "${base#appinstall-}"
}

pkg_installed_state_hint() { # installed_version target_version -> words for dry-run
  if [[ -z "$1" ]]; then printf 'fresh install\n'; return 0; fi
  case "$(version_relation "$1" "$2")" in
    eq) printf 'skip (already this version)\n' ;;
    gt) printf 'skip (installed %s is newer)\n' "$1" ;;
    *)  printf "upgrade %s -> %s\n" "$1" "$2" ;;
  esac
}

install_package_file() { # verified pkg path
  local pkg="$1"
  info "Installing package (the only sudo step): pacman -U $(basename "$pkg")"
  if [[ $TTY_OK -eq 1 ]]; then
    run_root pacman -U --needed -- "$pkg" || die 5 "pacman reported an error and the package was not installed. Review pacman's message; nothing else was changed by this script."
  else
    if [[ $ASSUME_YES -ne 1 ]]; then
      die 2 "Package install needs explicit consent in a noninteractive context. Re-run with --yes (or from a terminal)."
    fi
    run_root pacman -U --needed --noconfirm -- "$pkg" || die 5 "pacman reported an error and the package was not installed."
  fi
  [[ -e "$APP_BIN" ]] || die 5 "pacman finished but $APP_BIN is missing — treat the install as failed and re-run."
  info "AppInstall installed: $APP_BIN exists."
  log_write "pacman-U-ok pkg=$(basename "$pkg")"
}

# ---------------------------------------------------------------------------
# Uninstall path (--uninstall)
# ---------------------------------------------------------------------------
uninstall_flow() {
  info "Removing AppInstall package and optionally restoring previous file associations."
  info "Your application records, containers, launchers, logs and settings under ~ are always preserved."
  if ! ask "Remove the system package now (pacman -R appinstall)? AppInstall windows should be closed first." n; then
    info "Keeping the package; nothing was changed."
    return 0
  fi
  if [[ ! -e "$APP_BIN" ]] && [[ -z "$(installed_version)" ]]; then
    info "AppInstall does not appear to be installed via pacman; nothing to remove."
  else
    run_root pacman -R "appinstall" || die 5 "pacman -R failed; see pacman's output above."
    info "Package removed."
  fi
  if [[ -f "$STATE_BACKUP_TSV" ]] && ask "Restore your previous file associations (defaults that were active before AppInstall)?" n; then
    write_restore_script
    "$STATE_RESTORE_SCRIPT" || warn "Restore script had errors; backup remains at $STATE_BACKUP_TSV."
  else
    [[ -f "$STATE_BACKUP_TSV" ]] && info "Backup kept at $STATE_BACKUP_TSV — run this any time to restore defaults:"
    [[ -f "$STATE_BACKUP_TSV" ]] && info "  $STATE_RESTORE_SCRIPT"
  fi
  log_write "appinstall-uninstalled"
  info "Uninstall complete."
}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
usage() {
  cat <<HELP
AppInstall one-command installer (stable releases only; Arch Linux + CachyOS tested).

  curl -fsSL $RAW_URL | bash

Flags:
  --yes, -y                answer yes to installer prompts (install, upgrade, optional backends; NOT defaults)
  --set-defaults           opt in (noninteractively) to making AppInstall the default for all supported formats
  --no-defaults            never change default file associations
  --with-optional          install optional backends without asking
  --no-optional            do not offer optional backends
  --remove-source-install  consent to removing a conflicting user-local AppInstall (records preserved)
  --allow-arch-like        enable other arch-like distros outside the tested list (use at your own risk)
  --uninstall              remove AppInstall; offers restoring previous associations
  --dry-run                show the plan; change nothing
  --help                   show this help
  --version                print installer version

Notes:
  * Only Arch Linux and CachyOS are fully tested today. Other distros are
    refused with manual instructions rather than risking a broken install.
  * Stable GitHub releases only — drafts and prereleases are never used.
  * Per-user file association changes only; previous defaults are backed up.
HELP
}

parse_flags() {
  while (($#)); do
    case $1 in
      --yes|-y) ASSUME_YES=1 ;;
      --set-defaults) SET_DEFAULTS=1 ;;
      --no-defaults) NO_DEFAULTS=1 ;;
      --with-optional) WITH_OPTIONAL=1 ;;
      --no-optional) NO_OPTIONAL=1 ;;
      --remove-source-install) REMOVE_SOURCE_INSTALL=1 ;;
      --allow-arch-like) ALLOW_ARCH_LIKE=1 ;;
      --uninstall) UNINSTALL=1 ;;
      --dry-run) DRY_RUN=1 ;;
      --help|-h) usage; exit 0 ;;
      --version) printf 'appinstall-installer %s\n' "$INSTALLER_VERSION"; exit 0 ;;
      *) bad "Unknown flag: $1"; usage >&2; exit 2 ;;
    esac
    shift
  done
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  info "AppInstall one-command installer ${INSTALLER_VERSION}"
  info "Stable GitHub releases only; Arch Linux and CachyOS are the tested systems."

  # --- 1. environment ------------------------------------------------
  local family distro_id arch de
  family="$(detect_family)"
  distro_id="$(detect_distro_id)"
  arch="$(detect_arch)"
  de="$(detect_de)"
  info "Detected: distro=${distro_id} family=${family} arch=${arch} desktop=${de}"
  log_write "start flags=$* family=${family} id=${distro_id} arch=${arch} de=${de}"

  # --- 2. support gate (STRICT: no untested installs by default) -------
  if [[ "$family" != "arch" ]]; then
    cat >&2 <<UNSUPPORTED
This installer currently supports: Arch Linux and CachyOS (pacman) — both
thoroughly tested. Your system is '${distro_id}' (family '${family}'), which has
no tested one-command path yet.

No package was downloaded and nothing was changed. On Debian/Ubuntu, Fedora
and openSUSE you must NOT install the Arch pkg.tar.zst file. See INSTALL.md
for manual source installation (install-user.sh) options.
UNSUPPORTED
    exit 2
  fi
  local is_supported=0
  [[ " $SUPPORTED_IDS " == *" $distro_id "* ]] && is_supported=1
  if ((is_supported == 0)); then
    if [[ $ALLOW_ARCH_LIKE -eq 1 ]]; then
      warn "Distro '${distro_id}' is arch-like but untested — continuing because --allow-arch-like was used. Install at your own risk."
    else
      bad "Arch-like distro '${distro_id}' is not in the tested list (${SUPPORTED_IDS})."
      bad "You can force installation with --allow-arch-like, but there is no compatibility claim."
      exit 2
    fi
  fi
  if [[ "$arch" != "x86_64" ]]; then
    bad "Architecture '${arch}' is not supported by the tested stable release (x86_64)."
    bad "No untested builds will be installed."
    exit 2
  fi

  # --- 3. working tools (after the gate, so unsupported systems still get
  #        a helpful refusal even if a tool is missing) -------------------
  if ! need_cmds curl sha256sum pacman; then
    exit 2
  fi

  # --- 4. state cleanup (first-run hygiene) ----------------------------
  mkdir -p "$STATE_DIR"
  LOG_FILE="${STATE_DIR}/install-log.txt"
  log_write "start family=${family} id=${distro_id} arch=${arch} de=${de} dry_run=${DRY_RUN} assume_yes=${ASSUME_YES} set_defaults=${SET_DEFAULTS} no_defaults=${NO_DEFAULTS} with_optional=${WITH_OPTIONAL} no_optional=${NO_OPTIONAL} allow_arch_like=${ALLOW_ARCH_LIKE}"

  # --- 5. uninstall path ----------------------------------------------
  if [[ $UNINSTALL -eq 1 ]]; then
    prepare_tty
    uninstall_flow
    info "Done."
    return 0
  fi

  prepare_tty

  # --- 6. conflict / shadow install handling --------------------------
  check_shadow_conflicts

  # --- 7. resolve the latest stable release ---------------------------
  local installed_rel="" installed="0"
  installed_rel="$(installed_version)" || true
  [[ -n "$installed_rel" ]] && installed=1

  info "Resolving the latest stable release from GitHub (drafts and prereleases are never used)…"
  local release tag pkg_url sums_url pkg_name
  release="$(resolve_release)" || die 4 "GitHub API query for the latest stable release failed (network issue or rate limit). Optionally export GITHUB_TOKEN=<token> to raise the API rate limit, then retry."
  IFS='|' read -r tag pkg_url sums_url pkg_name <<<"$release"
  local pkg_ver
  pkg_ver="$(package_version_from_asset "$pkg_name")"
  info "Latest stable: ${tag} — asset: ${pkg_name}"

  # --- 8. dry-run: show the complete plan, change nothing ----------------
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '[dry-run] would download:  %s\n' "$pkg_url"
    printf '[dry-run] would download:  %s\n' "$sums_url"
    printf '[dry-run] then: verify SHA256SUMS; %s\n' "install with pacman -U $(pkg_installed_state_hint "$installed_rel" "$pkg_ver")"
    audit_optional_backends
    rootless_podman_report
    maybe_set_defaults
    printf '[dry-run] done — no changes were made.\n'
    return 0
  fi

  # --- 9. install decision -----------------------------------------------
  local already_current=0
  if ((installed == 1)); then
    case "$(version_relation "$installed_rel" "$pkg_ver")" in
      eq)
        info "AppInstall ${pkg_ver} (pacman) is already installed and is the latest stable. Nothing to install."
        already_current=1
        ;;
      gt)
        info "Installed AppInstall ${installed_rel} appears newer than stable ${pkg_ver}. Not downgrading."
        already_current=1
        ;;
      lt|unk)
        if ask "Upgrade the installed AppInstall (${installed_rel} → ${pkg_ver})? Close any running AppInstall window first." y; then
          info "Upgrading: ${installed_rel} → ${pkg_ver}."
        else
          info "Keeping existing version ${installed_rel}; nothing was changed."
          already_current=1
        fi
        ;;
    esac
  else
    # First-time install consent (transparent, one clear confirmation).
    if ! ask "Download and install AppInstall ${pkg_ver} from the verified stable release now? Checksum is verified before anything is installed." y; then
      if [[ $TTY_OK -eq 0 && $ASSUME_YES -eq 0 ]]; then
        die 2 "Noninteractive run without --yes: nothing was installed. Re-run with --yes for unattended installation, or from a terminal to answer prompts."
      fi
      info "Not installing. Nothing was changed."
      return 0
    fi
  fi

  if ((already_current == 0)); then
    TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/appinstall-install-XXXXXX")"
    info "Downloading package and checksum manifest to a private temp directory…"
    download_to "$pkg_url"  "${TMP_DIR}/${pkg_name}"   || die 4 "Package download failed; nothing was installed."
    download_to "$sums_url" "${TMP_DIR}/SHA256SUMS"    || die 4 "Manifest download failed; nothing was installed."
    info "Verifying checksum (sha256sum -c SHA256SUMS)…"
    if ! verify_checksums "$TMP_DIR" "$pkg_name"; then
      bad "Checksum verification FAILED (or manifest mismatch)."
      bad "The downloaded package has been deleted. Nothing was installed."
      bad "Re-run this installer, or investigate your network/proxy if this repeats."
      log_write "verify-failed pkg=${pkg_name}"
      exit 3
    fi
    info "Checksum verified."
    install_package_file "${TMP_DIR}/${pkg_name}"
  fi

  # --- 10. optional backends ------------------------------------------
  audit_optional_backends

  # --- 11. rootless container readiness -------------------------------
  rootless_podman_report

  # --- 12. desktop integration / file associations ---------------------
  maybe_set_defaults

  # --- 13. summary -----------------------------------------------------
  local current="${installed_rel}"
  if ((already_current == 0)); then
    current="$pkg_ver"
  fi
  info "All done."
  info "AppInstall version active: ${current}"
  info "Installed with pacman; launcher: application menu → 'AppInstall'."
  info "Open a supported file (.AppImage, .flatpak, .flatpakref, .flatpakrepo, .deb, .rpm) to preview it."
  info "Executable .AppImage files: some file managers may run them directly instead of opening the preview; right-click → 'Open With → AppInstall' when in doubt."
  info "To undo file-association changes at any time: $STATE_RESTORE_SCRIPT"
  info "To remove AppInstall entirely (records, containers and settings preserved): $0 --uninstall"
  log_write "done"
  return 0
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  parse_flags "$@"
  if [[ $SET_DEFAULTS -eq 1 && $NO_DEFAULTS -eq 1 ]]; then
    bad "--set-defaults and --no-defaults are mutually exclusive."
    exit 2
  fi
  if [[ $WITH_OPTIONAL -eq 1 && $NO_OPTIONAL -eq 1 ]]; then
    bad "--with-optional and --no-optional are mutually exclusive."
    exit 2
  fi
  main
fi
