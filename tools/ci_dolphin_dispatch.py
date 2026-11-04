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
MIMES = ("application/vnd.debian.binary-package", "application/x-deb")


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


def is_appinstall_package_window(window, env):
    pid = run(["xdotool", "getwindowpid", window], env, check=False).stdout.strip()
    if not pid.isdigit():
        return False
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return False
    return "container_ui.py" in cmdline and "appinstall-ci-mime-fixture" in cmdline


def verify_dolphin_dispatch(artifact, env):
    filetype = run(["xdg-mime", "query", "filetype", str(artifact)], env).stdout.strip()
    if filetype not in MIMES:
        raise RuntimeError(f"Fixture has unexpected MIME type: {filetype!r}")
    print(f"PASS: real .deb fixture detected as {filetype}", flush=True)

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
        print(f"PASS: Dolphin file-manager window appeared (X11 window {window})", flush=True)
        # --select highlights the fixture; Return activates the selected file.
        run(["xdotool", "windowactivate", "--sync", window], env)
        run(["xdotool", "key", "--clearmodifiers", "Return"], env)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            windows = search_windows(["--name", "^AppInstall$"], env)
            for app_window in windows:
                if is_appinstall_package_window(app_window, env):
                    observed_app_pid = int(run(
                        ["xdotool", "getwindowpid", app_window], env
                    ).stdout.strip())
                    break
            if observed_app_pid:
                print(
                    "PASS: Dolphin activated the .deb and launched the real "
                    "AppInstall container-package preview UI", flush=True
                )
                break
            time.sleep(0.4)
        if not observed_app_pid:
            raise RuntimeError(
                "Dolphin file activation did not open the AppInstall "
                "container-package preview (no install was attempted)"
            )
        time.sleep(0.5)
        if not Path(f"/proc/{observed_app_pid}").exists():
            raise RuntimeError("AppInstall preview process exited immediately")
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
        artifact = make_fixture(root, env)
        configure_handler(root, env)
        verify_dolphin_dispatch(artifact, env)
        registry = root / "data/appinstall/containers/registry.json"
        if registry.exists():
            raise RuntimeError("Unexpected container-install registry: installation must never occur")
        print("PASS: no package installed or registered by the review-only smoke", flush=True)
    print("PASS: isolated Dolphin MIME dispatch smoke completed", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
