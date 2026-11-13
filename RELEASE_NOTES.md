# AppInstall v1.3.0

My Applications checks for a newer stable AppInstall release while open.
When an update is available, choose **Update AppInstall** and approve the
desktop authentication prompt. AppInstall verifies the package checksum
before installing and shows **What's New** after confirming the installed
version. Reopen AppInstall to use the updated version.

To get the updater for the first time, run the existing one-command
installer. The in-app updater supports native Arch and Debian-family
packages. Use the terminal installer if your desktop has no polkit agent.

CI exercised real pacman and APT upgrades with simulated authorization.
A real CachyOS KDE test confirmed the password prompt, successful upgrade,
and completion dialog.
