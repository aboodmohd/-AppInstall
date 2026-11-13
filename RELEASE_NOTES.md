# AppInstall v1.4.0

Managed-app update checks: auto (TTL-cached ~12h) plus manual Check now.
Desktop notifications for available updates (notify-send, headless-safe).
Settings module, theme toggle (auto/light/dark), favorites, package size.
Drag-and-drop batch install with per-file results and cancel.
Container health & repair for DEB/RPM container apps.
Uninstall cleanup with explicit per-path checkboxes; nothing silently deleted.

To get the updater for the first time, run the existing one-command
installer. The in-app updater supports native Arch and Debian-family
packages. Use the terminal installer if your desktop has no polkit agent.

CI exercised real pacman and APT upgrades with simulated authorization.
A real CachyOS KDE test confirmed the password prompt, successful upgrade,
and completion dialog.
