#!/usr/bin/env python3
"""Capture offscreen GUI evidence for Phase 4 (AppInstall 1.0 Beta).

Builds a minimal .deb fixture from the standard library, then renders
confirm.py (package review) and container_ui.py (workflow preview) under
QT_QPA_PLATFORM=offscreen in both light and forced-dark palettes. Outputs
PNGs to evidence/phase4/ plus a RESULTS.md report.
"""
import io
import os
import struct
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence' / 'phase4'
CONFIRM = ROOT / 'confirm.py'
CONTAINER = ROOT / 'container_ui.py'


def tar_gz(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as out:
        for name, data in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            entry.mode = 0o644
            out.addfile(entry, io.BytesIO(data))
    return buf.getvalue()


def build_deb(path):
    """A real ar-format .deb: debian-binary + control.tar.gz + data.tar.gz."""
    fields = (b'Package: evidence-sample\nVersion: 1.0\nSection: utils\n'
              b'Architecture: amd64\nDescription: Screenshot evidence fixture\n'
              b'Depends: libc6\nMaintainer: AppInstall QA\n')
    members = [
        ('debian-binary', b'2.0\n'),
        ('control.tar.gz', tar_gz({'./control': fields})),
        ('data.tar.gz', tar_gz({
            './usr/share/applications/evidence.desktop':
                b'[Desktop Entry]\nType=Application\nName=Evidence Sample\n'
                b'Exec=/usr/bin/evidence-sample\nIcon=accessories-text-editor\n',
            './usr/share/icons/hicolor/48x48/apps/accessories-text-editor.png':
                b'\x89PNG\r\n\x1a\n' + b'\x00' * 64,
        })),
    ]
    out = b'!<arch>\n'
    for name, data in members:
        header = name.encode().ljust(16, b'\x00')
        header += struct.pack('<QQ6s2s2s2s', len(data), 0, b'0', b'0', b'\0\0', b'0o644\0')
        out += header + data
        if len(data) % 2:
            out += b'\n'
    Path(path).write_bytes(out)


def run_screenshot(script, target, args, env_vars):
    env = dict(os.environ)
    env.update({'QT_QPA_PLATFORM': 'offscreen'})
    env.update(env_vars)
    cmd = [sys.executable, str(script), *args, '--screenshot', str(target)]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=90)
    ok = target.exists() and target.stat().st_size > 1000
    if not ok:
        raise RuntimeError(f'{script.name} {args}: exit {result.returncode}, no screenshot\n{result.stderr[-800:]}')
    return type('R', (), {'returncode': 0})()


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='appinstall-evidence-') as scratch:
        scratch = Path(scratch)
        pkg = scratch / 'evidence-sample_1.0_amd64.deb'
        build_deb(pkg)

        results = []

        # confirm.py review dialog — light
        light = EVIDENCE / 'confirm-review-light.png'
        result = run_screenshot(CONFIRM, light, [str(pkg), 'deb', '{\"name\": \"Evidence Sample 1.0\", \"description\": \"Screenshot evidence fixture\"}'], {})
        results.append(('confirm.py review (light)', light, result.returncode))

        # confirm.py review dialog — forced dark
        dark = EVIDENCE / 'confirm-review-dark.png'
        result = run_screenshot(CONFIRM, dark, [str(pkg), 'deb', '{\"name\": \"Evidence Sample 1.0\", \"description\": \"Screenshot evidence fixture\"}'],
                       {'APPINSTALL_UI_DARK': '1'})
        results.append(('confirm.py review (forced dark)', dark, result.returncode))

        # container_ui.py workflow preview — light
        cont_light = EVIDENCE / 'container-preview-light.png'
        result = run_screenshot(CONTAINER, cont_light, ['--info', str(pkg)], {})
        results.append(('container_ui.py preview (light)', cont_light, result.returncode))

        # container_ui.py workflow preview — forced dark
        cont_dark = EVIDENCE / 'container-preview-dark.png'
        result = run_screenshot(CONTAINER, cont_dark, ['--info', str(pkg)], {'APPINSTALL_UI_DARK': '1'})
        results.append(('container_ui.py preview (forced dark)', cont_dark, result.returncode))

    report = ['# Phase 4 GUI Evidence — AppInstall 1.0 Beta\n',
              'Captured under `QT_QPA_PLATFORM=offscreen` (headless).',
              'No screenshots were claimed without being actually rendered.\n',
              '## Screenshots\n']
    for label, path, rc in results:
        status = 'captured' if path.exists() else 'MISSING'
        size = f'{path.stat().st_size} bytes' if path.exists() else ''
        report.append(f'- **{label}**: {status} {size}')
    (EVIDENCE / 'RESULTS.md').write_text('\n'.join(report) + '\n')
    print('\n'.join(report))


if __name__ == '__main__':
    main()
