#!/usr/bin/env bash
# Disposable, NON-ACCEPTANCE probe: KDE 6 Dolphin and a user-owned KIO service menu.
# No package installation, no execution of AppImages, no modification of host.
set -euo pipefail

repo=/workspace
out=/out
mkdir -p "$out"
probe="$(mktemp -d -t appinstall-plasma6-probe-XXXXXX)"
trap 'rm -rf "$probe"' EXIT

for tool in waymux waymux-run dolphin kbuildsycoca6 python3 dbus-run-session; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "FAIL: disposable Plasma 6 image lacks $tool"
        exit 1
    fi
done

echo "INFO: KDE 6 Dolphin availability"
dolphin --version
kbuildsycoca6 --version || true

export HOME="$probe/home"
export XDG_DATA_HOME="$probe/data"
export XDG_CONFIG_HOME="$probe/config"
export XDG_CACHE_HOME="$probe/cache"
export XDG_CURRENT_DESKTOP=KDE
export KDE_SESSION_VERSION=6
export QT_QPA_PLATFORM=wayland
mkdir -p "$HOME" "$XDG_DATA_HOME/kio/servicemenus" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"

menu="$XDG_DATA_HOME/kio/servicemenus/appinstall-appimage-review.desktop"
cp "$repo/appinstall-appimage-review.desktop" "$menu"
chmod 755 "$menu"

# Parse the actual source service-menu configuration. A positive result does
# NOT establish that the KDE context menu visibly lists this action.
python3 - "$menu" <<'PY'
from configparser import RawConfigParser
from pathlib import Path
import sys
p=Path(sys.argv[1])
c=RawConfigParser(interpolation=None)
c.read(p, encoding="utf-8")
assert c["Desktop Entry"]["Type"] == "Service"
assert c["Desktop Entry"]["Actions"] == "ReviewWithAppInstall;"
assert c["Desktop Entry"]["X-KDE-Priority"] == "TopLevel"
assert c["Desktop Entry"]["X-KDE-RequiredNumberOfUrls"] == "1"
assert "application/vnd.appimage;" in c["Desktop Entry"]["MimeType"]
assert c["Desktop Action ReviewWithAppInstall"]["Exec"] == "appinstall %f"
assert "--yes" not in p.read_text()
assert p.stat().st_mode & 0o111
print("PASS: unprivileged KDE6 user service-menu file and safe review action", flush=True)
PY

# Generate only a harmless non-executable mock with an AppImage extension.
fixture="$probe/appinstall-disposable-ci.AppImage"
python3 - "$fixture" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
p.write_bytes(b"\x7fELF" + b"\x00"*124)
p.chmod(0o644)
print("PASS: non-executable test fixture created", flush=True)
PY

# Refresh KDE6's cache in this isolated XDG profile. No host-owned paths.
kbuildsycoca6 --noincremental
echo "PASS: KDE6 KIO service cache built for isolated profile"

export APPINSTALL_CI_FIXTURE="$fixture"
export APPINSTALL_CI_OUT="$out"
dbus-run-session -- waymux-run --name appinstall-kio --size 1280x800 \
    --artifacts "$out" -- bash -c '
        set -eu
        dolphin --select "$APPINSTALL_CI_FIXTURE" >"$APPINSTALL_CI_OUT/dolphin.log" 2>&1 &
        pid=$!
        trap "kill $pid 2>/dev/null || true" EXIT
        waymux wait appinstall-kio --app-id org.kde.dolphin --timeout-ms 20000
        waymux windows appinstall-kio >"$APPINSTALL_CI_OUT/windows.json"
        waymux screenshot-desktop appinstall-kio \
            -o "$APPINSTALL_CI_OUT/dolphin-plasma6-wayland.png"
        test -s "$APPINSTALL_CI_OUT/dolphin-plasma6-wayland.png"
        echo "PASS: real KDE6 Dolphin window rendered on disposable Wayland compositor"
    '

echo "LIMITATION: Dolphin right-click menu visibility/action was not verified."
echo "LIMITATION: This is Debian/Ubuntu-based Plasma 6 CI, not CachyOS."
echo "LIMITATION: No real AppImage installation, launch, uninstall or user rights approval."
