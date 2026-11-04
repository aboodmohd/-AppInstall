#!/usr/bin/env python3
"""Disposable GitHub Actions smoke: Dolphin -> MIME handler -> AppInstall UI.

This exercises KDE Dolphin on Ubuntu X11/Xvfb, NOT KDE Plasma Wayland,
CachyOS, or real package installation. No package install button is clicked.
"""
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "appinstall"
MIMES = (
    "application/vnd.debian.binary-package", "application/x-deb",
    "application/x-rpm",
    "application/vnd.flatpak", "application/vnd.flatpak.ref",
    "application/vnd.flatpak.repo", "application/vnd.appimage",
)
TYPES = {
    "deb": ("application/vnd.debian.binary-package", "application/x-deb"),
    "rpm": ("application/x-rpm",),
    "flatpak": ("application/vnd.flatpak",),
    "flatpakref": ("application/vnd.flatpak.ref",),
    "flatpakrepo": ("application/vnd.flatpak.repo",),
    "appimage": ("application/vnd.appimage",),
}


def run(args, env, *, timeout=20, check=True):
    proc = subprocess.run(
        args, env=env, capture_output=True, text=True,
        timeout=timeout, check=False,
    )
    if check and proc.returncode:
        raise RuntimeError(
            f"{args!r} failed (exit {proc.returncode}):\n"
            f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
        )
    return proc


def search_windows(args, env):
    result = run(["xdotool", "search", "--onlyvisible", *args], env, check=False)
    return [x for x in result.stdout.splitlines() if x.isdigit()]


def wait_for_window(args, env, seconds=35):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        ids = search_windows(args, env)
        if ids:
            return ids[-1]
        time.sleep(0.3)
    raise RuntimeError(f"No visible X11 window found for {args!r}")


def make_fixture(root, env):
    pkgroot = root / "deb-root"
    control = pkgroot / "DEBIAN"
    control.mkdir(parents=True)
    (control / "control").write_text(
        "Package: appinstall-ci-mime-fixture\n"
        "Version: 1.0\nArchitecture: all\nMaintainer: CI <ci@example.invalid>\n"
        "Description: Harmless AppInstall MIME-dispatch fixture\n"
    )
    artifact = root / "appinstall-ci-mime-fixture_1.0_all.deb"
    run(["dpkg-deb", "--build", str(pkgroot), str(artifact)], env)
    if not artifact.is_file():
        raise RuntimeError("dpkg-deb did not create the fixture")
    return artifact


def make_flatpak_fixture(root, kind):
    if kind == "flatpakref":
        path = root / "appinstall-ci-flatpak-ref.flatpakref"
        # Deliberately invalid App ID: prevents Flathub metadata network lookup.
        path.write_text(
            "[Flatpak Ref]\n"
            "Name=ci_metadata_only\n"
            "Title=AppInstall CI Reference\n"
            "Branch=stable\n"
            "Url=https://example.invalid/disposable-repo\n"
        )
    elif kind == "flatpakrepo":
        path = root / "appinstall-ci-flatpak-repo.flatpakrepo"
        path.write_text(
            "[Flatpak Repo]\n"
            "Title=AppInstall CI Repository\n"
            "Url=https://example.invalid/disposable-repo\n"
        )
    else:
        raise ValueError(f"Unexpected fixture type: {kind}")
    return path



def make_rpm_fixture(root, env):
    """Build an inert real RPM containing one desktop metadata file, no scripts."""
    top = root / "rpmbuild"
    for part in ("BUILD", "BUILDROOT", "RPMS", "SOURCES", "SPECS", "SRPMS"):
        (top / part).mkdir(parents=True)
    spec = top / "SPECS/appinstall-ci-rpm-fixture.spec"
    spec.write_text(
        "Name: appinstall-ci-rpm-fixture\n"
        "Version: 1.0\n"
        "Release: 1\n"
        "Summary: Harmless AppInstall preview-only RPM fixture\n"
        "License: MIT\n"
        "BuildArch: noarch\n"
        "\n"
        "%description\n"
        "CI-generated metadata-only RPM with no scripts or executables.\n"
        "\n"
        "%prep\n"
        "%build\n"
        "%install\n"
        "mkdir -p %{buildroot}/usr/share/applications\n"
        "printf '[Desktop Entry]\\nType=Application\\nName=AppInstall CI RPM Fixture\\n"
        "Exec=/bin/false\\n' > "
        "%{buildroot}/usr/share/applications/appinstall-ci-fixture.desktop\n"
        "\n"
        "%files\n"
        "/usr/share/applications/appinstall-ci-fixture.desktop\n"
    )
    run(["rpmbuild", "-bb", "--define", f"_topdir {top}",
         str(spec)], env, timeout=90)
    artifact = top / "RPMS/noarch/appinstall-ci-rpm-fixture-1.0-1.noarch.rpm"
    if not artifact.is_file() or artifact.stat().st_size < 1000:
        raise RuntimeError("rpmbuild did not generate a real, inert RPM fixture")
    return artifact


def make_appimage_fixture(root):
    """Minimal non-executable ELF/AppImage *header*, never an installable app."""
    path = root / "appinstall-ci-preview.AppImage"
    header = bytearray(128)
    header[0:4] = b"\x7fELF"
    header[4:8] = b"\x02\x01\x01\x00"
    header[8:11] = b"AI\x02"
    header[16:18] = b"\x02\x00"
    header[18:20] = b"\x3e\x00"  # x86_64; CI uses amd64 Ubuntu runners
    path.write_bytes(header)
    path.chmod(0o644)  # Do not mark executable; this is only preview metadata
    return path


def make_flatpak_bundle_fixture(root):
    """Non-installable placeholder: preview UI should not read or execute it."""
    path = root / "appinstall-ci-preview.flatpak"
    path.write_bytes(b"AppInstall CI harmless local Flatpak preview placeholder\\n")
    return path


def register_isolated_appimage_mime(isolated, env):
    """Model the opt-in AppImage MIME association in this temporary XDG profile.

    The minimal Ubuntu runner does not ship AppImageLauncher MIME definitions;
    this only tests the opted-in handler, not distro out-of-box registration.
    """
    packages = isolated / "data/mime/packages"
    packages.mkdir(parents=True)
    xml = """<?xml version="1.0" encoding="utf-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/vnd.appimage">
    <comment>AppInstall disposable AppImage preview fixture</comment>
    <glob pattern="*.AppImage" weight="100"/>
    <magic priority="95">
      <match type="string" value="AI" offset="8"/>
    </magic>
  </mime-type>
</mime-info>
"""
    (packages / "appinstall-ci-appimage.xml").write_text(xml)
    run(["update-mime-database", str(packages.parent)], env)
    print("PASS: optional AppImage MIME type registered in isolated XDG only", flush=True)


def configure_handler(isolated, env):
    desktopdir = isolated / "data/applications"
    desktopdir.mkdir(parents=True)
    desktop = ROOT.joinpath("appinstall.desktop").read_text()
    original = "Exec=appinstall %F"
    if desktop.count(original) != 1:
        raise RuntimeError("AppInstall desktop Exec entry changed unexpectedly")
    replacement = f'Exec=/usr/bin/bash "{INSTALLER}" %F'
    (desktopdir / "appinstall.desktop").write_text(
        desktop.replace(original, replacement)
    )
    # Use only an isolated, temporary XDG config, never runner user defaults.
    config = isolated / "config"
    config.mkdir()
    for mime in MIMES:
        run(["xdg-mime", "default", "appinstall.desktop", mime], env)
        actual = run(["xdg-mime", "query", "default", mime], env).stdout.strip()
        if actual != "appinstall.desktop":
            raise RuntimeError(f"MIME default for {mime}: {actual!r}")
    print("PASS: isolated KDE MIME defaults point to AppInstall", flush=True)
    for command in ("kbuildsycoca5", "kbuildsycoca6"):
        if shutil.which(command):
            result = run([command, "--noincremental"], env, timeout=25, check=False)
            print(
                f"INFO: {command} exit {result.returncode}; "
                f"{(result.stderr or result.stdout)[-400:]}",
                flush=True,
            )
            if result.returncode:
                raise RuntimeError(f"{command} failed to refresh KDE service cache")
            break


def is_appinstall_package_window(window, env, artifact, kind):
    pid = run(["xdotool", "getwindowpid", window], env, check=False).stdout.strip()
    if not pid.isdigit():
        return False
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return False
    module = "container_ui.py" if kind in ("deb", "rpm") else "confirm.py"
    return module in cmdline and artifact.name in cmdline


def verify_dolphin_dispatch(artifact, kind, env):
    # KDE in a minimal X11 session can return an empty xdg-mime filetype.
    # GIO reads the installed shared MIME database, including Flatpak's
    # .flatpakref/.flatpakrepo registrations supplied by the CI runner.
    xdg_type = run(
        ["xdg-mime", "query", "filetype", str(artifact)], env, check=False
    ).stdout.strip()
    gio = run(["gio", "info", "-a", "standard::content-type", str(artifact)], env)
    content_types = [
        row.split("standard::content-type:", 1)[1].strip()
        for row in gio.stdout.splitlines()
        if "standard::content-type:" in row
    ]
    print(
        f"INFO: {kind} xdg-mime={xdg_type!r}, gio={content_types!r}",
        flush=True,
    )
    if not content_types or content_types[-1] not in TYPES[kind]:
        raise RuntimeError(
            f"{kind} fixture not recognized by installed MIME database: "
            f"{content_types!r}, expected={TYPES[kind]!r}"
        )
    print(f"PASS: harmless {kind} fixture has registered MIME type", flush=True)

    manager = subprocess.Popen(
        ["openbox"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    dolphin = None
    observed_app_pid = None
    try:
        time.sleep(0.6)
        dolphin = subprocess.Popen(
            ["dolphin", "--select", str(artifact)],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        window = wait_for_window(["--class", "dolphin"], env)
        print(f"PASS: Dolphin opened for {kind} (X11 window {window})", flush=True)
        # --select highlights the fixture; Return activates the selected file.
        # NEVER activate a confirmation/installation button inside AppInstall.
        run(["xdotool", "windowactivate", "--sync", window], env)
        run(["xdotool", "key", "--clearmodifiers", "Return"], env)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            windows = search_windows(["--name", "^AppInstall$"], env)
            for app_window in windows:
                if is_appinstall_package_window(app_window, env, artifact, kind):
                    observed_app_pid = int(run(
                        ["xdotool", "getwindowpid", app_window], env
                    ).stdout.strip())
                    break
            if observed_app_pid:
                module = "container_ui.py" if kind == "deb" else "confirm.py"
                print(
                    f"PASS: Dolphin activated {kind}, opened real {module} "
                    "AppInstall review window; no install was requested",
                    flush=True,
                )
                break
            time.sleep(0.4)
        if not observed_app_pid:
            raise RuntimeError(
                f"Dolphin did not open AppInstall preview for {kind}; "
                "no install was attempted"
            )
        time.sleep(0.5)
        if not Path(f"/proc/{observed_app_pid}").exists():
            raise RuntimeError(f"{kind} AppInstall review process exited immediately")
    finally:
        if observed_app_pid:
            try:
                os.kill(observed_app_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if dolphin:
            if dolphin.poll() is None:
                dolphin.terminate()
            try:
                dolphin.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                dolphin.kill()
                dolphin.communicate(timeout=5)
        if manager.poll() is None:
            manager.terminate()
        try:
            manager.wait(timeout=5)
        except subprocess.TimeoutExpired:
            manager.kill()
            manager.wait(timeout=5)


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("CI") != "true":
        raise RuntimeError("Refusing to run outside GitHub Actions")
    if os.geteuid() == 0 or not os.environ.get("DISPLAY") or not INSTALLER.is_file():
        raise RuntimeError("Requires an unprivileged runner with X11 display and source checkout")
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    with tempfile.TemporaryDirectory(prefix="appinstall-dolphin-", dir=runner_temp) as directory:
        root = Path(directory)
        home = root / "home"
        home.mkdir()
        runtime = root / "runtime"
        runtime.mkdir(mode=0o700)
        env = dict(os.environ)
        env.update({
            "HOME": str(home),
            "XDG_DATA_HOME": str(root / "data"),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_STATE_HOME": str(root / "state"),
            "XDG_CACHE_HOME": str(root / "cache"),
            "XDG_RUNTIME_DIR": str(runtime),
            "XDG_CURRENT_DESKTOP": "KDE",
            "KDE_SESSION_VERSION": "5",
            "XDG_SESSION_TYPE": "x11",
            "QT_QPA_PLATFORM": "xcb",
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        register_isolated_appimage_mime(root, env)
        artifacts = [
            ("deb", make_fixture(root, env)),
            ("rpm", make_rpm_fixture(root, env)),
            ("appimage", make_appimage_fixture(root)),
            ("flatpak", make_flatpak_bundle_fixture(root)),
            ("flatpakref", make_flatpak_fixture(root, "flatpakref")),
            ("flatpakrepo", make_flatpak_fixture(root, "flatpakrepo")),
        ]
        configure_handler(root, env)
        for kind, artifact in artifacts:
            verify_dolphin_dispatch(artifact, kind, env)
        registry = root / "data/appinstall/containers/registry.json"
        if registry.exists():
            raise RuntimeError("Unexpected container-install registry: installation must never occur")
        print("PASS: no package installed or registered by the review-only smoke", flush=True)
    print("PASS: six isolated Dolphin preview dispatch fixtures (DEB/RPM/AppImage/Flatpak/ref/repo) completed", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
