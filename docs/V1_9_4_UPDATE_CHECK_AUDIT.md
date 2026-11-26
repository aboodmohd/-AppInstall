# AppInstall v1.9.4 update-check audit

## Root cause (confirmed)

The live v1.9.3 Premium UI self-update button starts `/usr/lib/abood-appinstall/appinstall-installer --desktop-check` through `QProcess`. `Bridge._update_finished()` treated **any** non-zero exit as `Could not check for updates` and displayed raw helper output. It did not distinguish DNS/connect failures, proxies, HTTP/rate limits, TLS, timeouts, missing dependencies or unsupported distributions.

Healthy live checks succeeded. Forcing a proxy failure produced the same failure path:

```text
curl: (7) Failed to connect to api.github.com:443 over proxy 127.0.0.1:9
ERROR: No abood-appinstall asset for arch in the latest stable release...
```

Application update scans were partly isolated: `UpdateEngine.check_one()` returned per-app `error` candidates, but only caught `OSError`, `ValueError`, `RuntimeError` and `TypeError`, and `check_many()` only caught cancellation. A `subprocess.TimeoutExpired` or another provider exception could stop the whole scan and lose partial results.

## Fixes

- `install.sh` emits `APPINSTALL_UPDATE_ERROR=<category>: <actionable detail>` on stderr for DNS, connection/proxy, timeout, HTTP/rate-limit and TLS failures. Both desktop and normal release discovery use the same `api_get()` path.
- `manager_qml.py` and `manager.py` classify those markers plus legacy output keywords into network, timeout, HTTP/API-limit, TLS, dependency, unsupported and backend categories. The status now names the category and the dialog includes an action before the bounded diagnostic output.
- A 150-second `QTimer` stops the self-update helper and its whole process group (via `setsid` on POSIX) and reports a timeout, so the UI cannot wait indefinitely and no `curl` child is left behind.
- `update_engine.py` adds `backend_error_reason()` and catches every provider exception per application; one failing backend can no longer suppress results from other applications.
- Widgets and QML Premium UI share the same classifier.

## Evidence

- Regression tests added for self-update network categorization, timeout termination, API error markers, and partial application-update results after a provider timeout.
- Real Premium UI click with a forced proxy failure now shows `Network problem` with actionable guidance and status `Update check failed: network`; healthy network shows no failure.
- Independent application-update checks on the live inventory returned per-format results without a global exception: AppImage manual/unsupported results, Flatpak up-to-date/error records, and the existing DEB fixture error.
- Synthetic repository-backed DEB and RPM records returned actionable backend errors instead of crashing the scan.

## Limitations

No physical DEB/RPM-managed applications were installed for the live check; those backends were exercised by unit tests and read-only container queries. A real GitHub outage or rate-limit event was not awaited; the failure path was reproduced by forcing a local proxy failure. No application, record, setting, Flatpak or container was modified during testing.
