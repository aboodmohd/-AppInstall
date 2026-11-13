# AppInstall v1.2.0

AppInstall now has a native APT package for Debian 13, Ubuntu 24.04 and
26.04, and Linux Mint 22. The one-command installer selects the appropriate
release package and verifies its checksum. On APT systems it installs only
required dependencies. Arch and CachyOS use pacman.

CI covers package installation, reinstallation, removal, preservation of
user data, and headless GUI startup on the APT targets. Full desktop
integration and managed-app lifecycle testing on these desktops remain
unverified.

Ubuntu users need the Universe repository enabled.
