#!/usr/bin/env python3
"""CI-only X11 smoke of AppInstall's real CLI and two top-level Qt windows.

This is *not* KDE, Dolphin, Wayland, a full package installation, or a
substitute for disposable CachyOS desktop acceptance. No apps are installed.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
ENTRYPOINT = ROOT / "appinstall"
WINDOWS = (
    ("--manage", "AppInstall.*My Applications", "My Applications"),
    ("--diagnostics", "AppInstall.*Application Diagnostics", "Application Diagnostics"),
)


def ensure_ci():
    if os.environ.get("CI") != "true" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Refusing to run outside GitHub Actions CI")
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Requires an X11 display (run through xvfb-run)")
    if os.geteuid() == 0:
        raise RuntimeError("Run as an unprivileged CI user")
    if not ENTRYPOINT.is_file():
        raise RuntimeError("AppInstall entry point is missing")


def check_detect(env, home):
    fixtures = {
        "sample.AppImage": "appimage",
        "sample.flatpak": "flatpak",
        "sample.flatpakref": "flatpakref",
        "sample.flatpakrepo": "flatpakrepo",
        "sample.deb": "deb",
        "sample.rpm": "rpm",
    }
    for name, expected in fixtures.items():
        path = home / name
        path.write_bytes(b"fixture only; never execute or install\n")
        result = subprocess.run(
            ["bash", str(ENTRYPOINT), "--detect", str(path)],
            env=env, text=True, capture_output=True, timeout=10, check=True
        )
        actual = result.stdout.strip()
        if actual != expected:
            raise AssertionError(f"Detection for {name}: expected {expected!r}, got {actual!r}")
    print("PASS: CLI recognizes all six supported file extensions", flush=True)


def visible_window(regex):
    result = subprocess.run(
        ["xdotool", "search", "--onlyvisible", "--name", regex],
        text=True, capture_output=True, timeout=5
    )
    if result.returncode != 0:
        return False
    return bool(re.search(r"^\d+$", result.stdout, re.MULTILINE))


def check_window(flag, expression, label, env):
    # Use temporary log files, so subprocess output never blocks the Qt process.
    with tempfile.TemporaryFile(mode="w+t") as log:
        proc = subprocess.Popen(
            ["bash", str(ENTRYPOINT), flag],
            env=env, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT
        )
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError(f"{label} exited before showing a window (exit {proc.returncode})")
                if visible_window(expression):
                    # Also reject a window that flashes open and crashes.
                    time.sleep(0.35)
                    if proc.poll() is not None:
                        raise RuntimeError(f"{label} exited immediately after showing its window")
                    print(f"PASS: {label} opened through appinstall {flag} under Xvfb/X11", flush=True)
                    return
                time.sleep(0.25)
            raise RuntimeError(f"Timed out waiting for visible {label} window")
        except Exception:
            log.flush()
            log.seek(0)
            print(f"--- {label} Qt output ---\n{log.read()[-12000:]}\n--- end output ---", file=sys.stderr)
            raise
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def main():
    ensure_ci()
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    if not runner_temp.is_dir():
        raise RuntimeError("RUNNER_TEMP does not exist")
    with tempfile.TemporaryDirectory(prefix="appinstall-x11-", dir=runner_temp) as temp:
        isolated = Path(temp)
        home = isolated / "home"
        home.mkdir()
        runtime = isolated / "runtime"
        runtime.mkdir(mode=0o700)
        env = os.environ.copy()
        env.update({
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(isolated / "config"),
            "XDG_DATA_HOME": str(isolated / "data"),
            "XDG_STATE_HOME": str(isolated / "state"),
            "XDG_CACHE_HOME": str(isolated / "cache"),
            "XDG_RUNTIME_DIR": str(runtime),
            "QT_QPA_PLATFORM": "xcb",
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        check_detect(env, home)
        for flag, expression, label in WINDOWS:
            check_window(flag, expression, label, env)
    print("PASS: Isolated CLI and X11 window smoke completed", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
