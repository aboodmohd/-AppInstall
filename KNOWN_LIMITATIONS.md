# AppInstall Known Limitations

## Package format compatibility

- **DEB/RPM**: Compatibility is not universal. Some packages omit runtime
  dependencies or require additional configuration. DEB/RPM applications run
  in rootless Distrobox containers (Debian 13 / Fedora 44). This project does
  not guarantee that every Linux package will run.
- **Flatpak**: Update support is available. Reinstall requires the original
  bundle or reference file.
- **AppImage**: Only ELF type 2 images matching x86-64 or ARM64 are supported.
  FUSE 2 is not required for passive preview; `squashfs-tools` is required
  for detailed content inspection.

## Container limitations

- Containers do not guarantee security isolation. They are convenience
  wrappers, not sandboxes.
- Drivers, kernel modules, and system services are unsupported.
- Shared Distrobox containers (`debian-apps`, `fedora-apps`) are never
  automatically deleted during uninstall.

## Launch monitoring limitations

- GUI launch monitoring cannot always prove that an application is usable.
  "Running" status means the process started, not that the application window
  appeared or is functional.
- Some runtime dependencies may be discovered only during launch output.
- Detached or background processes are not assumed usable.

## Update limitations

- Automatic updates are supported for Flatpak only.
- DEB/RPM updates require reinstalling with a newer package file.
- AppImage updates require replacing the AppImage file manually.
- Never silently upgrades unrelated applications.

## Intended user experience by format

| Format | Install | Launch | Update | Uninstall |
|--------|---------|--------|--------|-----------|
| AppImage | Copy to `~/Applications`, menu entry | Monitored launcher | Replace .AppImage file | Remove managed copy + launcher |
| Flatpak | `flatpak --user install` | Monitored `flatpak run` | `flatpak --user update` | `flatpak --user uninstall` |
| DEB | Distrobox Debian container | Monitored container entry | Reinstall with newer .deb | Remove from container + launcher |
| RPM | Distrobox Fedora container | Monitored container entry | Reinstall with newer .rpm | Remove from container + launcher |

## Security notes

- AppImages are never executed to display metadata. Passive inspection via
  `unsquashfs` only.
- Without `squashfs-tools`, detailed preview is unavailable; the installer
  degrades gracefully to a generic icon with an honest notice.
- Launchers are monitored; startup failures show useful errors and logs.
- Personal application data and diagnostic logs are preserved across
  uninstall/reinstall.
