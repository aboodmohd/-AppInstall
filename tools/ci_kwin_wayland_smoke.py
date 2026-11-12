#!/usr/bin/env python3
"""GitHub CI-only AppInstall smoke under KDE KWin's *virtual Wayland* backend.

This tests real KWin Wayland protocol traffic and Qt windows using only
disposable HOME/XDG paths on a hosted runner. It is not a full Plasma desktop,
not CachyOS, and not real four-format application-installation acceptance.
"""
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from ci_wayland_smoke import (
    check_app_window, check_manager_capture, qt_platform_probe,
    stop_process, wait_for_socket,
)

SOCKET = "wayland-appinstall-kwin-ci"


def assert_qt_capture(program, output, env, title):
    result = subprocess.run(
        [sys.executable, str(ROOT / program), "--screenshot", str(output)],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=35,
    )
    if result.returncode:
        raise RuntimeError(
            f"{title}: screenshot command failed ({result.returncode}): "
            + (result.stdout + result.stderr)[-5000:]
        )
    data = output.read_bytes()
    if len(data) < 1000 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError(f"{title}: invalid or empty Qt PNG screenshot")
    w, h = struct.unpack(">II", data[16:24])
    if w < 300 or h < 200:
        raise RuntimeError(f"{title}: unexpected capture size {w}x{h}")
    print(f"PASS: {title} Qt window captured under KWin Wayland ({w}x{h})", flush=True)


def run_native_url_dialog_tests(env):
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests",
         "-p", "test_url_dialog.py", "-v"],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=90,
    )
    if result.returncode:
        raise RuntimeError(
            "Native-KWin URL dialog regression tests failed: "
            + (result.stdout + result.stderr)[-9000:]
        )
    if "OK" not in result.stderr or "skipped=" in result.stderr:
        raise RuntimeError("URL dialog tests did not complete cleanly without skips: "
                           + result.stderr[-5000:])
    print("PASS: URL dialog regression suite on native KDE KWin Wayland",
          flush=True)


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("CI") != "true":
        raise RuntimeError("Refusing to run outside disposable GitHub Actions CI")
    if os.geteuid() == 0:
        raise RuntimeError("Must run as unprivileged GitHub runner user")
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    if not runner_temp.is_dir():
        raise RuntimeError("RUNNER_TEMP missing")
    kwin_exe = shutil.which("kwin_wayland")
    if not kwin_exe:
        raise RuntimeError("KWin Wayland binary is not installed")
    if not (ROOT / "url_dialog.py").is_file():
        raise RuntimeError("AppInstall URL dialog source is missing")

    with tempfile.TemporaryDirectory(prefix="appinstall-kwin-wayland-",
                                     dir=runner_temp) as tmp:
        root = Path(tmp)
        runtime = root / "runtime"
        runtime.mkdir(mode=0o700)
        home = root / "home"
        home.mkdir()
        env = os.environ.copy()
        env.pop("DISPLAY", None)
        env.update({
            "HOME": str(home),
            "XDG_RUNTIME_DIR": str(runtime),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_DATA_HOME": str(root / "data"),
            "XDG_CACHE_HOME": str(root / "cache"),
            "XDG_STATE_HOME": str(root / "state"),
            "XDG_SESSION_TYPE": "wayland",
            "XDG_CURRENT_DESKTOP": "KDE",
            "WAYLAND_DISPLAY": SOCKET,
            "QT_QPA_PLATFORM": "wayland",
            "QT_QUICK_BACKEND": "software",
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "WAYLAND_DEBUG": "client",
        })
        kwin_env = dict(env)
        kwin_env.pop("WAYLAND_DISPLAY", None)
        kwin_env.pop("WAYLAND_DEBUG", None)
        # The KWin virtual backend must not depend on a host display or GPU.
        kwin_env["QT_QPA_PLATFORM"] = "offscreen"

        cmd = [kwin_exe, "--virtual", "--width", "1280", "--height", "800",
               "--socket", SOCKET, "--no-lockscreen"]
        with (root / "kwin.log").open("w+b") as log:
            kwin = subprocess.Popen(
                cmd, cwd=str(root), env=kwin_env,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            )
            try:
                try:
                    wait_for_socket(runtime / SOCKET, kwin, seconds=35)
                    print("PASS: KDE KWin virtual Wayland compositor responding",
                          flush=True)
                    qt_platform_probe(env)
                    check_app_window("--manage", "My Applications", env)
                    check_app_window("--diagnostics", "Application Diagnostics", env)
                    check_manager_capture(env, root / "manager-kwin-wayland.png")
                    assert_qt_capture(
                        "url_dialog.py", root / "url-dialog-kwin-wayland.png",
                        env, "Install from URL",
                    )
                    run_native_url_dialog_tests(env)
                    # No real app installation, container creation, source
                    # registration or user-data mutation is allowed.
                    for path in (
                        root / "data" / "appinstall" / "containers" / "registry.json",
                        home / "Applications",
                    ):
                        if path.exists():
                            raise RuntimeError(
                                "Unexpected AppInstall installation state: "
                                + str(path)
                            )
                except Exception:
                    log.flush()
                    log.seek(0)
                    print("--- KWin diagnostics ---\n" +
                          log.read()[-10000:].decode(errors="replace") +
                          "\n--- End KWin diagnostics ---",
                          file=sys.stderr)
                    raise
            finally:
                stop_process(kwin)
    print("PASS: isolated KWin virtual Wayland AppInstall GUI/URL smoke",
          flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError,
            FileNotFoundError, ValueError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        sys.exit(1)
