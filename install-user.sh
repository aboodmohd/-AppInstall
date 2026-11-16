#!/usr/bin/env bash
set -eu
here=$(cd -- "$(dirname -- "$0")" && pwd)
if ! command -v python3 >/dev/null; then
  echo 'Python 3 is required for desktop registration.' >&2
  exit 1
fi
if ! command -v kdialog >/dev/null && ! command -v zenity >/dev/null; then
  echo 'Install zenity (GNOME/Xfce) or kdialog (KDE) using your package manager for graphical dialogs.' >&2
fi
# Portable source installation is intentionally distro-neutral. Never silently
# shadow a system copy installed by pacman, APT/dpkg or DNF/RPM.
installed_by=""
if command -v pacman >/dev/null 2>&1 && pacman -Qq appinstall >/dev/null 2>&1; then
  installed_by="pacman"
elif command -v dpkg-query >/dev/null 2>&1 && \
     dpkg-query -W -f='\${Status}' appinstall 2>/dev/null | grep -qx 'install ok installed'; then
  installed_by="dpkg"
elif command -v rpm >/dev/null 2>&1 && rpm -q appinstall >/dev/null 2>&1; then
  installed_by="rpm"
fi

if [ -n "$installed_by" ]; then
  printf 'AppInstall is already installed through %s.\n' "$installed_by" >&2
  printf '%s\n' 'A source installation in ~/.local/bin may shadow /usr/bin/appinstall.' >&2
  printf '%s\n' 'Check with: type -a appinstall. No existing installation will be deleted.' >&2
  if [ ! -t 0 ]; then
    printf '%s\n' 'Refusing an additional user installation without interactive confirmation.' >&2
    exit 2
  fi
  printf 'Continue with an additional user installation? [y/N] ' >&2
  read -r answer || exit 2
  case "$answer" in
    y|Y|yes|YES) ;;
    *) printf '%s\n' 'Installation cancelled.' >&2; exit 2 ;;
  esac
fi

# PySide6 is needed for Discover Apps, but CLI use and the existing KDialog/
# Zenity fallback remain usable without it. Don't silently install dependencies
# or invoke an unfamiliar host package manager.
if ! python3 -c 'import PySide6.QtQml, PySide6.QtQuick' >/dev/null 2>&1; then
  echo 'Discover Apps requires Python PySide6 and Qt Quick from your distribution.' >&2
  echo 'Install those dependencies if you want the full v1.7.0 manager UI.' >&2
fi

exec python3 "$here/integration.py"
