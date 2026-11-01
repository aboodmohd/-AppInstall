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
exec python3 "$here/integration.py"
