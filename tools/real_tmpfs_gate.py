#!/usr/bin/env python3
"""Real ENOSPC and SIGKILL source recovery on a CI-only disposable tmpfs.

DANGER: this writes until ENOSPC. Refuses to run unless the supplied path
is a dedicated tmpfs mount inside GitHub Actions RUNNER_TEMP. Never run it
on a real HOME, the root filesystem, or a production-mounted device.
"""
import errno
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_INSTALLER = ROOT / "integration.py"
MIME = "application/vnd.flatpak"


def require_disposable_tmpfs(raw):
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Refusing to fill any filesystem outside GitHub Actions")
    runner_temp = os.environ.get("RUNNER_TEMP")
    if not runner_temp:
        raise RuntimeError("RUNNER_TEMP is required")
    mount = Path(raw).resolve(strict=True)
    scratch = Path(runner_temp).resolve(strict=True)
    if mount == scratch or not mount.is_relative_to(scratch):
        raise RuntimeError("The test mount must be a child of RUNNER_TEMP")
    if not mount.is_mount():
        raise RuntimeError("Test root is not an independent filesystem mount")
    # Require the expected disposable filesystem instead of a mounted volume.
    lines = Path("/proc/self/mountinfo").read_text().splitlines()
    matches = [entry for entry in lines if " - " in entry and
               entry.split(" - ", 1)[0].split()[4] == str(mount)]
    if not any(entry.split(" - ", 1)[1].split()[0] == "tmpfs" for entry in matches):
        raise RuntimeError("Test mount must be tmpfs, not a persistent disk")
    capacity = os.statvfs(mount)
    total = capacity.f_blocks * capacity.f_frsize
    if not 8 * 1024 * 1024 <= total <= 64 * 1024 * 1024:
        raise RuntimeError("Refusing unexpectedly sized tmpfs mount")
    if any(mount.iterdir()):
        raise RuntimeError("Test mount must be empty")
    return mount


def run_install(env, *options):
    return subprocess.run(
        [sys.executable, str(SOURCE_INSTALLER), *options],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=45,
    )


def must_pass(run, description):
    if run.returncode != 0:
        raise AssertionError(
            description + " failed with code " + str(run.returncode) +
            "\nstdout: " + run.stdout[-2000:] +
            "\nstderr: " + run.stderr[-2000:])


def fill_to_enospc(path):
    chunk = b"F" * (1024 * 1024)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    total = 0
    try:
        # Write directly without buffering so we can distinguish ENOSPC.
        # 32 MiB takes at most 32 iterations plus one final partial write.
        while True:
            try:
                size = os.write(fd, chunk)
                if size <= 0:
                    raise AssertionError("Filler made no progress")
                total += size
            except OSError as exc:
                if exc.errno != errno.ENOSPC:
                    raise
                break
    finally:
        os.close(fd)
    if total < 1024 * 1024:
        raise AssertionError("tmpfs filled too soon; insufficient disk capacity")
    return total


def main(raw_mount):
    mount = require_disposable_tmpfs(raw_mount)
    home = mount / "home"
    config = home / "config"
    data = home / "data"
    state = data / "appinstall"
    applications = data / "applications"
    config.mkdir(parents=True)
    applications.mkdir(parents=True)
    mime = config / "mimeapps.list"
    mime.write_text(
        "[Default Applications]\n"
        "application/vnd.flatpak=previous.desktop;\n"
        "text/plain=editor.desktop;\n"
    )
    registry = state / "containers/registry.json"
    registry.parent.mkdir(parents=True)
    registry_value = {"deb:untouched": {"name": "Keep", "status": "installed"}}
    registry.write_text(json.dumps(registry_value))
    unrelated = applications / "unrelated.desktop"
    unrelated.write_text("[Desktop Entry]\nName=Keep Unrelated Application\n")

    env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(config),
               XDG_DATA_HOME=str(data), XDG_STATE_HOME=str(home / "state"),
               QT_QPA_PLATFORM="offscreen")
    result = run_install(env)
    must_pass(result, "Initial clean source registration")
    installed = home / ".local/bin/appinstall"
    manager = state / "manager.py"
    associations = state / "associations.json"
    tracked = [installed, manager, mime, associations, registry, unrelated]
    before = {path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
              for path in tracked}
    if b"application/vnd.flatpak=appinstall.desktop;" not in before[mime][0]:
        raise AssertionError("Initial registration did not set the MIME default")

    filler = mount / "filler.bin"
    wrote = fill_to_enospc(filler)
    try:
        free = os.statvfs(mount)
        free_bytes = free.f_bavail * free.f_frsize
        if free_bytes > 4096:
            raise AssertionError("ENOSPC was not actually reached")
        failed = run_install(env)
        if failed.returncode == 0:
            raise AssertionError("Full-disk source upgrade unexpectedly succeeded")
        for path in tracked:
            blob, mode = before[path]
            if path.read_bytes() != blob or stat.S_IMODE(path.stat().st_mode) != mode:
                raise AssertionError("Disk-full attempt changed " + str(path))
        print("PASS: real ENOSPC on disposable tmpfs; source, MIME defaults, "
              "permissions and unrelated user records preserved", flush=True)
        print("Disposable filesystem fill: " + str(wrote) +
              " bytes; remaining " + str(free_bytes) + " bytes", flush=True)
    finally:
        # Removing one file is permitted even after ENOSPC and restores space.
        filler.unlink(missing_ok=True)

    must_pass(run_install(env), "Registration retry after freeing disk")
    for path in tracked:
        blob, mode = before[path]
        if path.read_bytes() != blob or stat.S_IMODE(path.stat().st_mode) != mode:
            raise AssertionError("Retry did not preserve " + str(path))
    print("PASS: source registration retry after genuine ENOSPC", flush=True)

    # Simulate SIGKILL after the first file has been replaced. This creates
    # a genuine persisted pending journal (no exception-handler rollback).
    child = r"""
import os
from pathlib import Path
import signal
import sys
sys.path.insert(0, sys.argv[1])
from source_transaction import SourceTransaction
state, first, second = map(Path, sys.argv[2:])
with SourceTransaction(state, [first, second]) as transaction:
    publish = transaction._publish
    def interrupted(stage, target):
        publish(stage, target)
        os.kill(os.getpid(), signal.SIGKILL)
    transaction._publish = interrupted
    transaction.apply({
        first: (b'PARTIALLY-PUBLISHED-MANAGER', 0o644),
        second: (b'[Default Applications]\napplication/vnd.flatpak=wrong.desktop;\n', 0o600),
    })
"""
    killed = subprocess.run(
        [sys.executable, "-c", child, str(ROOT), str(state),
         str(manager), str(mime)],
        env=env, capture_output=True, text=True, timeout=30)
    if killed.returncode != -signal.SIGKILL:
        raise AssertionError("SIGKILL test did not terminate as expected: " +
                             str(killed.returncode) + " " + killed.stderr[-1000:])
    journal = state / ".source-update/journal.json"
    if not journal.exists() or manager.read_bytes() != b"PARTIALLY-PUBLISHED-MANAGER":
        raise AssertionError("The interrupted transaction did not persist")
    if mime.read_bytes() != before[mime][0]:
        raise AssertionError("MIME was altered before the simulated SIGKILL")

    must_pass(run_install(env), "Registration and journal recovery after SIGKILL")
    if journal.exists():
        raise AssertionError("Recovery journal remains after successful restart")
    for path in tracked:
        blob, mode = before[path]
        if path.read_bytes() != blob or stat.S_IMODE(path.stat().st_mode) != mode:
            raise AssertionError("SIGKILL recovery failed to preserve " + str(path))
    print("PASS: genuine SIGKILL during commit, next-run journal recovery, "
          "permissions and unrelated user files intact", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: real_tmpfs_gate.py <CI-only-mounted-tmpfs>")
    try:
        main(sys.argv[1])
    except (OSError, RuntimeError, AssertionError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        raise SystemExit(1) from error
