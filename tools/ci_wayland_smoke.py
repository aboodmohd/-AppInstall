#!/usr/bin/env python3
"""CI-only Wayland protocol smoke for AppInstall under headless Weston.

A real Wayland compositor accepts AppInstall Qt top-level surfaces. This is
not KDE Plasma, CachyOS, Dolphin, installation, nor a release acceptance test.
No installed applications or real user data are accessed or modified.
"""
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
APPINSTALL = ROOT / "appinstall"
SOCKET_NAME = "wayland-appinstall-ci"
COMMANDS = (("--manage", "My Applications"), ("--diagnostics", "Application Diagnostics"))


def stop_process(proc):
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)


def wait_for_socket(path, proc, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Weston exited before its socket was ready (status {proc.returncode})")
        if path.exists():
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.settimeout(1)
                sock.connect(str(path))
                print("PASS: disposable Weston Wayland socket accepts connections", flush=True)
                return
            except OSError:
                pass
            finally:
                sock.close()
        time.sleep(0.2)
    raise RuntimeError("Weston did not create a usable Wayland socket")


def qt_platform_probe(env):
    snippet = (
        "from PySide6.QtWidgets import QApplication, QWidget; "
        "a=QApplication([]); "
        "assert a.platformName()=='wayland', a.platformName(); "
        "w=QWidget(); w.setWindowTitle('AppInstall Qt Wayland probe'); "
        "w.show(); a.processEvents(); "
        "print('PASS: Qt uses native Wayland platform', flush=True); "
        "w.close()"
    )
    result = subprocess.run(
        [sys.executable, "-c", snippet],
        env=env, text=True, capture_output=True, timeout=20,
    )
    if result.returncode:
        raise RuntimeError(
            "Native Wayland Qt probe failed: " +
            (result.stderr + result.stdout)[-6000:]
        )
    print(result.stdout.strip(), flush=True)


def check_app_window(flag, label, env):
    # Redirect protocol logs to a temporary regular file rather than a pipe.
    with tempfile.TemporaryFile(mode="w+b") as log:
        child = subprocess.Popen(
            ["bash", str(APPINSTALL), flag],
            cwd=str(ROOT), env=env,
            stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                log.flush()
                log.seek(0)
                content = log.read()
                if child.poll() is not None:
                    raise RuntimeError(
                        f"{label} exited early with {child.returncode}; "
                        f"output: {content[-7000:].decode(errors='replace')}"
                    )
                # WAYLAND_DEBUG=client emits real Qt -> Weston protocol traffic.
                # Require creation of a top-level Wayland surface and a commit
                # while the CLI-launched AppInstall process remains alive.
                if b"xdg_toplevel" in content and b".commit(" in content:
                    time.sleep(0.4)
                    if child.poll() is not None:
                        raise RuntimeError(f"{label} exited immediately after a Wayland commit")
                    print(
                        f"PASS: appinstall {flag} created and committed a "
                        f"native Wayland top-level surface ({label})",
                        flush=True,
                    )
                    return
                time.sleep(0.25)
            log.flush()
            log.seek(0)
            raise RuntimeError(
                f"Timed out waiting for {label} Wayland top-level traffic: " +
                log.read()[-7000:].decode(errors="replace")
            )
        finally:
            stop_process(child)


def check_manager_capture(env, path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "manager.py"), "--screenshot", str(path)],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=25,
    )
    if result.returncode:
        raise RuntimeError(
            "Manager screenshot under Wayland failed: " +
            (result.stderr + result.stdout)[-7000:]
        )
    data = path.read_bytes()
    if len(data) < 1000 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError("Manager Wayland screenshot has invalid PNG header/length")
    width, height = struct.unpack(">II", data[16:24])
    if width < 500 or height < 400:
        raise RuntimeError(f"Unexpected manager screenshot size: {width}x{height}")
    print(
        f"PASS: My Applications rendered a {width}x{height} PNG "
        "through native Wayland Qt (discarded after test)",
        flush=True,
    )


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("CI") != "true":
        raise RuntimeError("Refusing to run outside GitHub Actions CI")
    if os.geteuid() == 0:
        raise RuntimeError("Must be an unprivileged CI account")
    if not APPINSTALL.is_file():
        raise RuntimeError("Missing AppInstall command")
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    if not runner_temp.is_dir():
        raise RuntimeError("Missing GitHub runner temporary directory")

    with tempfile.TemporaryDirectory(prefix="appinstall-wayland-", dir=runner_temp) as tmp:
        root = Path(tmp)
        home = root / "home"
        home.mkdir()
        runtime = root / "runtime"
        runtime.mkdir(mode=0o700)
        env = os.environ.copy()
        env.pop("DISPLAY", None)
        env.update({
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_DATA_HOME": str(root / "data"),
            "XDG_CACHE_HOME": str(root / "cache"),
            "XDG_STATE_HOME": str(root / "state"),
            "XDG_RUNTIME_DIR": str(runtime),
            "XDG_SESSION_TYPE": "wayland",
            "XDG_CURRENT_DESKTOP": "Weston",
            "WAYLAND_DISPLAY": SOCKET_NAME,
            "QT_QPA_PLATFORM": "wayland",
            "QT_QUICK_BACKEND": "software",
            "PYTHONDONTWRITEBYTECODE": "1",
            "WAYLAND_DEBUG": "client",
        })
        weston_env = dict(env)
        weston_env.pop("WAYLAND_DISPLAY", None)
        weston_env.pop("WAYLAND_DEBUG", None)
        with (root / "weston.log").open("w+b") as weston_log:
            weston = subprocess.Popen(
                [
                    "weston", "--backend=headless-backend.so",
                    "--socket=" + SOCKET_NAME, "--idle-time=0",
                    "--width=1280", "--height=800", "--no-config",
                ],
                cwd=str(root), env=weston_env,
                stdout=weston_log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                try:
                    wait_for_socket(runtime / SOCKET_NAME, weston)
                    qt_platform_probe(env)
                    for flag, label in COMMANDS:
                        check_app_window(flag, label, env)
                    check_manager_capture(env, root / "manager-wayland.png")
                    for path in (
                        root / "data/appinstall/containers/registry.json",
                        root / "home/Applications",
                    ):
                        if path.exists():
                            raise RuntimeError(f"Unexpected installation state: {path}")
                except Exception:
                    weston_log.flush()
                    weston_log.seek(0)
                    print(
                        "--- Weston diagnostic output ---\n" +
                        weston_log.read()[-10000:].decode(errors="replace") +
                        "\n--- end Weston output ---",
                        file=sys.stderr,
                    )
                    raise
            finally:
                stop_process(weston)
    print("PASS: isolated headless-Weston AppInstall Wayland smoke completed", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
