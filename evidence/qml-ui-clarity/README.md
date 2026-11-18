# AppInstall Qt redesign evidence

Actual AppInstall QML windows captured on CachyOS KDE with PySide6 6.12.
The harness supplies six disposable inventory records and deterministic catalog
and update results. These are UI fixtures, not live provider or transaction
evidence. Installed-app artwork uses local desktop-theme images and letter
fallbacks. Nothing was installed, updated or removed on the host.

| Screen | Baseline (`20dc69d`) | Redesigned |
| --- | --- | --- |
| My applications, 1440 logical px, Wayland | [Before](before-library.png) | [After](library.png) |
| Discover, 1440 logical px, Wayland | [Before](before-discover.png) | [After](discover.png) |
| Updates, 1440 logical px, Wayland | [Before](before-updates.png) | [After](updates.png) |
| My applications, 1024 logical px, light mode, Wayland | — | [After](light.png) |
| Discover, 800 logical px, 150% scale, XWayland (`xcb`) | — | [After](narrow.png) |

The redesigned windows retain system typography, native window behavior, and
scrollable result lists rather than reproducing the browser prototype pixel for
pixel. On short desktops, Featured can be expanded on demand so the catalog
remains usable.

The PR #89 layout follow-up refreshed the three wide fixtures, light mode, and
the narrow capture. The library fixture shows an AppInstall update notice
alongside the attention warning. Discover shows the first catalog row aligned
at the top and Previous/Next controls for the six Featured results.

Read-only checks also rendered six actual managed records and the first
24 entries of a live Flathub browse with six Featured results. Local inventory
captures are not published. No source setup or package action was invoked.

## Run on CachyOS KDE

From the branch checkout, with PySide6 installed:

```sh
QT_QPA_PLATFORM=wayland python evidence/qml-ui-clarity/capture.py \
  "$PWD" /tmp/appinstall-discover.png discover 1440 dark
APPINSTALL_DESKTOP_SMOKE=1 QT_QPA_PLATFORM=xcb QT_SCALE_FACTOR=1.5 \
  python evidence/qml-ui-clarity/capture.py \
  "$PWD" /tmp/appinstall-narrow.png library 800 dark
```

The smoke variant checks keyboard navigation, menu and category popup, update
summary counts, and the six-record inventory without contacting package
providers. To explore the application interactively, run `python manager_qml.py`
as a disposable user or in a test VM. Do not use a live account for package
transaction tests.
