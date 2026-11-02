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
# A source/user installation can shadow a system package on PATH.
# Do not overwrite either installation or change precedence silently.
if command -v pacman >/dev/null 2>&1 && pacman -Qq appinstall >/dev/null 2>&1; then
  printf '%s\n' 'AppInstall is already installed through pacman.' >&2
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
exec python3 "$here/integration.py"
