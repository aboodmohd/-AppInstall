#!/usr/bin/env python3
"""Installed Applications Manager for AppInstall.

Reads AppInstall-managed application records from the container registry
(DEB/RPM in Distrobox) and the launch-monitor registry (AppImage/Flatpak),
builds a unified inventory, and presents a graphical manager for opening,
diagnosing, repairing, reinstalling and safely uninstalling managed
applications.

Never takes ownership of unrelated applications. Never deletes legacy registry
data. Never assumes a desktop entry alone proves installation.
"""
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import container_backend as container_backend_mod
import launch_monitor as monitor
import diagnostics_core as core

FORMATS = ('appimage', 'flatpak', 'deb', 'rpm')
FORMAT_LABELS = {'appimage': 'AppImage', 'flatpak': 'Flatpak', 'deb': 'DEB', 'rpm': 'RPM'}
STATUS_INSTALLED = 'installed'
STATUS_NEEDS_REPAIR = 'needs-repair'
STATUS_MISSING = 'missing'
STATUS_STALE = 'stale'
STATUS_CORRUPTED = 'corrupted'
STATUS_UNKNOWN = 'unknown'


def _read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def container_registry_path():
    return Path(container_backend_mod.state_dir()) / 'registry.json'


def launch_registry_path():
    return Path(monitor.data_root()) / 'launchers.json'


def inventory_signature():
    """Lightweight read-only change marker for atomically replaced registries."""
    marker = []
    for path in (container_registry_path(), launch_registry_path()):
        try:
            info = path.stat()
            marker.append((info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size))
        except FileNotFoundError:
            marker.append(None)
        except OSError:
            marker.append(('unreadable',))
    return tuple(marker)


def launches_dir():
    return Path(monitor.state_root()) / 'launches'


def _last_launch(key):
    """Return the most recent launch attempt for a managed key, or None."""
    try:
        attempts = monitor.history(key)
    except (OSError, ValueError):
        return None
    return attempts[0] if attempts else None


def _launch_error(key):
    attempt = _last_launch(key)
    return attempt.get('error') if attempt and attempt.get('error') else None


def icon_pixmap(app):
    """Return a 64x64 pixmap for an app record, falling back to the generic icon."""
    from PySide6.QtGui import QIcon
    icon = app.get('icon') or ''
    if icon and Path(icon).is_file():
        return QPixmap(icon)
    icon_name = app.get('icon_name') or ''
    qicon = QIcon()
    if icon_name:
        qicon = QIcon.fromTheme(icon_name)
    if qicon.isNull():
        qicon = QIcon.fromTheme('package-x-generic')
    return qicon.pixmap(QSize(64, 64))


def _launcher_exists(record):
    """A managed launcher is real if the recorded desktop entry OR any
    AppInstall-owned export path exists on disk."""
    desktop = record.get('desktop') or ''
    if desktop and Path(desktop).is_file():
        return True
    for entry in record.get('exports', []):
        path = entry.get('path') if isinstance(entry, dict) else None
        if path and Path(path).is_file():
            return True
    return False


def _flatpak_installed(appid):
    """Return True/False for a confirmed inventory result, None on failure.

    An unsuccessful ``flatpak info`` cannot distinguish absence from access
    errors. List applications instead; without scope flags Flatpak includes
    both user and system installations (including additional installations).
    """
    if not appid:
        return None
    try:
        result = subprocess.run(
            ['flatpak', 'list', '--app', '--columns=application'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return None
        installed = {line.strip() for line in result.stdout.splitlines()}
        if appid in installed:
            return True
        # A warning may indicate a partially readable inventory. It cannot
        # establish absence, even if the command returned success.
        return None if result.stderr.strip() else False
    except Exception:
        # Missing CLI, timeouts, access/decoding errors and unexpected query
        # failures are unknown, never evidence that an application is absent.
        return None


def _appimage_target(raw):
    """Resolve the AppImage generation path from the manifest when the
    launch registry record does not store it directly."""
    target = raw.get('target') or raw.get('file')
    if target and Path(target).is_file():
        return target
    manifest = raw.get('manifest')
    if manifest and Path(manifest).is_file():
        try:
            data = json.loads(Path(manifest).read_text())
            for key in ('target', 'generation'):
                cand = data.get(key)
                if cand and Path(cand).exists():
                    return cand
        except (OSError, ValueError):
            pass
    return target or ''


def _resolve_desktop(raw, fmt):
    """Return the real managed desktop entry path.

    For container packages, the registry's recorded desktop path may point to
    a non-existent system path. The actual managed launcher lives in
    exports[0].path. Prefer the export path when the recorded path is missing.
    """
    desktop = raw.get('desktop') or ''
    if desktop and Path(desktop).is_file():
        return desktop
    if fmt in ('deb', 'rpm'):
        for entry in raw.get('exports', []):
            path = entry.get('path') if isinstance(entry, dict) else None
            if path and Path(path).is_file():
                return path
    return desktop


def _clean_description(text):
    """Return a meaningful description, or '' if it is empty/whitespace/junk."""
    if not text:
        return ''
    stripped = text.strip()
    if not stripped or stripped == '.':
        return ''
    return stripped


def _friendly_launch_status(status):
    """Map a raw launch status to user-friendly text."""
    friendly = {
        'checking': 'Checking',
        'starting': 'Starting',
        'running_unverified': 'Running (unverified)',
        'detached_or_exited_unverified': 'Launch unverified',
        'exited_after_startup_unverified': 'Exited after startup',
        'failed': 'Failed',
    }
    return friendly.get(status, status)


def build_app_record(key, raw, source):
    """Normalize one raw registry record into a unified app record.

    Does not launch containers. Status uses recorded state, on-disk evidence
    and a read-only Flatpak inventory query.
    """
    if not isinstance(raw, dict):
        raw = {}
    fmt = raw.get('format') or raw.get('kind') or 'unknown'
    name = raw.get('name') or raw.get('application_name') or key.rsplit(':', 1)[-1]
    version = raw.get('version') or ''
    desktop = _resolve_desktop(raw, fmt)
    icon = raw.get('icon') or ''
    icon_name = raw.get('icon_name') or ''
    container = raw.get('container')
    manifest = raw.get('manifest')
    target = _appimage_target(raw) if fmt == 'appimage' else (raw.get('target') or raw.get('file'))
    description = _clean_description(raw.get('description') or '')
    status = raw.get('status') or STATUS_UNKNOWN

    problems = []
    # Validate backing installation without side effects.
    if fmt == 'appimage':
        if manifest and not Path(manifest).is_file():
            problems.append('manifest missing')
        if target and not Path(target).is_file():
            problems.append('application file missing')
        if not _launcher_exists(raw):
            problems.append('launcher missing')
    elif fmt == 'flatpak':
        appid = key.rsplit(':', 1)[-1] if key.startswith('flatpak:') else None
        if appid:
            installed = _flatpak_installed(appid)
            if installed is False:
                problems.append('application file missing')
            # installed is True -> app confirmed present, no problem
            # installed is None -> could not determine (flatpak missing,
            # timeout, etc.) — do not mark as missing; leave status as-is
    elif fmt in ('deb', 'rpm'):
        if status not in (STATUS_INSTALLED, 'installing', 'removing'):
            problems.append('container record not installed')
        if not _launcher_exists(raw):
            problems.append('launcher missing')
        if not container:
            problems.append('container not recorded')

    if problems:
        if status == STATUS_CORRUPTED or 'corrupted' in problems:
            status = STATUS_CORRUPTED
        elif status in (STATUS_INSTALLED, 'installing', 'removing') and any(
            p in ('application file missing', 'container not recorded') for p in problems
        ):
            status = STATUS_MISSING
        elif status == STATUS_NEEDS_REPAIR:
            status = STATUS_NEEDS_REPAIR
        else:
            status = STATUS_STALE
    elif status == STATUS_UNKNOWN:
        status = STATUS_INSTALLED

    last = _last_launch(key)
    return {
        'key': key,
        'format': fmt,
        'name': str(name),
        'version': str(version) or 'unknown',
        'status': status,
        'desktop': desktop,
        'icon': icon,
        'icon_name': icon_name,
        'container': container,
        'manifest': manifest,
        'target': target,
        'description': description,
        'install_date': 'unknown',
        'package_id': key,
        'last_launch': last,
        'last_error': _launch_error(key),
        'source': source,
        'problems': problems,
        'raw': raw,
    }


def load_inventory():
    """Build a unified inventory of AppInstall-managed applications.

    Reads both registries read-only. Never acquires the container lock, never
    starts a container, never calls flatpak. Duplicate keys across sources are
    dropped in favour of the container record.
    """
    apps = []
    seen_keys = set()

    container_records = _read_json(container_registry_path()) or {}
    if not isinstance(container_records, dict):
        container_records = {}
    for key, raw in container_records.items():
        if not isinstance(key, str) or not isinstance(raw, dict):
            continue
        apps.append(build_app_record(key, raw, 'container-registry'))
        seen_keys.add(key)

    launch_records = _read_json(launch_registry_path()) or {}
    if not isinstance(launch_records, dict):
        launch_records = {}
    for key, raw in launch_records.items():
        if not isinstance(key, str) or not isinstance(raw, dict):
            continue
        if key in seen_keys:
            continue
        apps.append(build_app_record(key, raw, 'launch-monitor'))

    apps.sort(key=lambda app: app['name'].casefold())
    return apps


def find_app(inventory, key):
    for app in inventory:
        if app['key'] == key:
            return app
    return None


def formats_summary(inventory):
    counts = {fmt: 0 for fmt in FORMATS}
    for app in inventory:
        if app['format'] in counts:
            counts[app['format']] += 1
    return counts


# ── Action helpers ─────────────────────────────────────────────────────────

def can_uninstall(app):
    return app['format'] in ('appimage', 'flatpak', 'deb', 'rpm')


def can_reinstall(app):
    if app['format'] == 'appimage':
        return bool(app.get('target') and Path(app['target']).is_file())
    if app['format'] in ('deb', 'rpm'):
        return bool(app.get('target') and Path(app['target']).is_file())
    return False  # flatpak requires the original bundle/ref


def can_update(app):
    """Update is supported when the backend can perform it without a new file."""
    return app['format'] == 'flatpak'


def uninstall_app(app):
    """Safe uninstall via diagnostics_core. Removes only AppInstall-owned artifacts."""
    if not can_uninstall(app):
        raise RuntimeError('Uninstall is not supported for '+app['format']+' applications.')
    core.uninstall(app['key'])
    return 'Application removed. Personal application data and logs were kept.'


def reinstall_app(app):
    """Reinstall from the staged/original package file. No duplicates created."""
    if app['format'] == 'appimage':
        target = app.get('target')
        if not target or not Path(target).is_file():
            raise RuntimeError(
                'The original AppImage file is no longer available. '
                'Select the AppImage file again to reinstall.')
        import appimage_backend as backend
        destination = str(Path(target).parent)
        backend.install(target, destination)
        return 'AppImage reinstalled.'
    if app['format'] in ('deb', 'rpm'):
        target = app.get('target')
        if not target or not Path(target).is_file():
            raise RuntimeError(
                'The staged package file is no longer available. '
                'Select the package file again to reinstall.')
        from container_backend import Engine
        info = dict(app['raw'])
        info['file'] = target
        engine = Engine()
        try:
            engine.install(info, lambda entries: entries[0] if entries else None)
        finally:
            engine.close()
        return 'Container package reinstalled.'
    raise RuntimeError('Reinstall is not supported for '+app['format']+' applications.')


def update_app(app):
    """Run a backend-supported update. Flatpak only; confirm multi-package impact."""
    if app['format'] != 'flatpak':
        raise RuntimeError('Automatic updates are not supported for '+app['format']+' applications.')
    appid = app['raw'].get('appid') or app['key'].rsplit(':', 1)[-1]
    result = subprocess.run(
        ['flatpak', 'update', '--user', '--noninteractive', '--assumeyes', 'app/'+appid],
        capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip() or 'Flatpak update failed.')
    return 'Flatpak update completed.'


def open_app(app):
    """Launch through the monitored entry point; never claims success without evidence."""
    return core.open_application(app['key'])


def repair_launcher(app):
    if app['format'] in ('deb', 'rpm'):
        return core.repair_launcher(app['key'])
    if app['format'] in ('appimage', 'flatpak'):
        monitor.rewrite_launcher(app['raw'])
        return 'The managed launcher was recreated.'
    raise RuntimeError('Launcher repair is not supported for '+app['format']+' applications.')


def diagnostics_for(app):
    return dict(
        key=app['key'],
        name=app['name'],
        format=app['format'],
        container=app.get('container'),
        desktop=app.get('desktop'),
        last_launch=app.get('last_launch'),
        last_error=app.get('last_error'),
        last=app.get('last_launch'),
    )


# ── UI layer ───────────────────────────────────────────────────────────────

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PySide6.QtGui import QIcon, QPixmap, QColor, QPalette
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem, QFrame, QSizePolicy,
    QMessageBox, QDialog, QDialogButtonBox, QScrollArea, QGridLayout,
    QSpacerItem, QMenu
)

import ui_style

from url_dialog import UrlInstallDialog


class InventoryLoader(QThread):
    """Background worker that reads the registries without blocking the GUI."""
    done = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            self.done.emit(load_inventory())
        except Exception as error:  # pragma: no cover - defensive UI guard
            self.failed.emit(str(error))


class AppCard(QWidget):
    """One application card: icon, summary, status and permitted actions."""

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setMinimumWidth(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(132)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        # Icon.
        self.icon = QLabel()
        self.icon.setFixedSize(64, 64)
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setScaledContents(True)
        pix = self._icon_pixmap()
        self.icon.setPixmap(pix)
        self.icon.setStyleSheet('border-radius: 8px; background: palette(base);')
        layout.addWidget(self.icon, 0)

        # Summary.
        summary = QVBoxLayout()
        summary.setSpacing(4)
        self.name = QLabel(app['name'])
        self.name.setTextFormat(Qt.PlainText)
        self.name.setWordWrap(True)
        font = self.name.font(); font.setPointSizeF(font.pointSizeF() * 1.12); font.setBold(True)
        self.name.setFont(font)
        summary.addWidget(self.name)

        meta = QLabel(self._meta_text())
        meta.setTextFormat(Qt.PlainText)
        meta.setWordWrap(True)
        meta.setStyleSheet('color: palette(text); font-size: 12px;')
        summary.addWidget(meta)

        self.status = QLabel(self._status_text())
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        self.status.setStyleSheet(self._status_style())
        summary.addWidget(self.status)

        if app['problems']:
            note = QLabel('⚠ '+'; '.join(app['problems']))
            note.setTextFormat(Qt.PlainText)
            note.setWordWrap(True)
            note.setStyleSheet('color: #b3402e; font-size: 11.5px;')
            summary.addWidget(note)

        summary.addStretch(1)
        layout.addLayout(summary, 1)

        # Actions.
        actions = QHBoxLayout()
        actions.setSpacing(8)
        open_btn = QPushButton('Open')
        open_btn.setObjectName('primary')
        open_btn.setMinimumWidth(80)
        open_btn.setEnabled(self._can_launch())
        open_btn.clicked.connect(self._emit_open)
        actions.addWidget(open_btn)

        details = QPushButton('Details')
        details.setObjectName('ghost')
        details.setMinimumWidth(80)
        details.clicked.connect(self._emit_details)
        actions.addWidget(details)

        more = QPushButton('⋮')
        more.setObjectName('ghost')
        more.setMinimumWidth(40)
        more.setMenu(self._build_menu())
        actions.addWidget(more)

        layout.addLayout(actions, 0)

        self.setStyleSheet(ui_style.primary_button_stylesheet(self) + ui_style.ghost_button_stylesheet(self))

        # Signals exposed to the window.
        self.open_requested = None
        self.details_requested = None

    def _icon_pixmap(self):
        return icon_pixmap(self.app)

    def _meta_text(self):
        app = self.app
        parts = [FORMAT_LABELS.get(app['format'], app['format'])]
        if app['version'] and app['version'] != 'unknown':
            parts.append('v'+app['version'])
        if app['container']:
            parts.append(app['container']+' container')
        elif app['format'] == 'appimage':
            parts.append('AppImage file')
        return '   ·   '.join(parts)

    def _status_text(self):
        app = self.app
        if app['status'] == STATUS_INSTALLED and not app['problems']:
            return 'Managed — installed'
        if app['status'] == STATUS_NEEDS_REPAIR:
            return 'Managed — needs repair'
        if app['status'] == STATUS_MISSING:
            return 'Managed — files missing'
        if app['status'] == STATUS_STALE:
            return 'Managed — stale record'
        if app['status'] == STATUS_CORRUPTED:
            return 'Managed — metadata corrupted'
        return 'Managed — status unknown'

    def _status_style(self):
        app = self.app
        palette = self.palette()
        if app['status'] == STATUS_INSTALLED and not app['problems']:
            return 'color: palette(text); font-weight: 600; font-size: 12px;'
        if app['status'] == STATUS_NEEDS_REPAIR:
            return 'color: #c77d2e; font-weight: 600; font-size: 12px;'
        return 'color: #b3402e; font-weight: 600; font-size: 12px;'

    def _can_launch(self):
        return self.app['format'] in ('appimage', 'flatpak', 'deb', 'rpm') and bool(self.app['desktop'])

    def _build_menu(self):
        menu = QMenu(self)
        app = self.app
        if self._can_launch():
            menu.addAction('Launch (monitored)', self._emit_open)
        menu.addSection('Management')
        if can_reinstall(app):
            menu.addAction('Reinstall', self._emit_reinstall)
        else:
            action = menu.addAction('Reinstall — package file required')
            action.setEnabled(False)
        if can_update(app):
            menu.addAction('Check for Updates', self._emit_update)
        else:
            action = menu.addAction('Update — not auto-supported')
            action.setEnabled(False)
        if can_uninstall(app):
            menu.addAction('Uninstall', self._emit_uninstall)
        else:
            action = menu.addAction('Uninstall — not supported')
            action.setEnabled(False)
        menu.addSection('Diagnostics')
        menu.addAction('View Logs', self._emit_logs)
        menu.addAction('Repair Launcher', self._emit_repair)
        menu.addAction('Open Diagnostics', self._emit_diagnostics)
        return menu

    def _emit_open(self):
        if self.open_requested:
            self.open_requested(self.app)

    def _emit_details(self):
        if self.details_requested:
            self.details_requested(self.app)

    def _emit_reinstall(self):
        if hasattr(self, 'reinstall_requested') and self.reinstall_requested:
            self.reinstall_requested(self.app)

    def _emit_update(self):
        if hasattr(self, 'update_requested') and self.update_requested:
            self.update_requested(self.app)

    def _emit_uninstall(self):
        if hasattr(self, 'uninstall_requested') and self.uninstall_requested:
            self.uninstall_requested(self.app)

    def _emit_logs(self):
        if hasattr(self, 'logs_requested') and self.logs_requested:
            self.logs_requested(self.app)

    def _emit_repair(self):
        if hasattr(self, 'repair_requested') and self.repair_requested:
            self.repair_requested(self.app)

    def _emit_diagnostics(self):
        if hasattr(self, 'diagnostics_requested') and self.diagnostics_requested:
            self.diagnostics_requested(self.app)


class AppDetailsDialog(QDialog):
    """Read-only details view for one managed application."""

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle('AppInstall — '+app['name'])
        self.setMinimumWidth(560)
        self.resize(640, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(16)
        picture = QLabel()
        picture.setFixedSize(72, 72)
        picture.setScaledContents(True)
        picture.setPixmap(icon_pixmap(app))
        picture.setStyleSheet('border-radius: 8px; background: palette(base);')
        header.addWidget(picture, 0, Qt.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(4)
        title = QLabel(app['name'])
        title.setTextFormat(Qt.PlainText)
        title.setWordWrap(True)
        font = title.font(); font.setPointSizeF(font.pointSizeF() * 1.3); font.setBold(True)
        title.setFont(font)
        text.addWidget(title)
        kind = QLabel(FORMAT_LABELS.get(app['format'], app['format'])+' · '+app['status'])
        kind.setTextFormat(Qt.PlainText)
        kind.setStyleSheet('color: palette(text); font-size: 13px;')
        text.addWidget(kind)
        header.addLayout(text, 1)
        layout.addLayout(header)

        if app['description']:
            desc = QLabel(app['description'])
            desc.setTextFormat(Qt.PlainText)
            desc.setWordWrap(True)
            layout.addWidget(desc)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        rows = [
            ('Package identifier', app['package_id']),
            ('Version', app['version']),
            ('Installation date', app['install_date']),
            ('Installed path', app['target'] or '—'),
        ]
        if app.get('container'):
            rows.append(('Container', app['container']))
        rows += [
            ('Desktop entry', app['desktop'] or '—'),
            ('Manifest', app['manifest'] or '—'),
            ('Source', app['source']),
        ]
        for row, (label, value) in enumerate(rows):
            key_label = QLabel(label)
            key_label.setStyleSheet('color: palette(text); font-size: 12px;')
            grid.addWidget(key_label, row, 0)
            value_label = QLabel(str(value))
            value_label.setTextFormat(Qt.PlainText)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_label.setToolTip(str(value))
            grid.addWidget(value_label, row, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        # Last launch.
        last = app.get('last_launch') or {}
        if last or app.get('last_error'):
            launch_box = QFrame()
            launch_box.setFrameShape(QFrame.StyledPanel)
            launch_layout = QVBoxLayout(launch_box)
            launch_layout.setContentsMargins(14, 12, 14, 12)
            launch_layout.setSpacing(6)
            head = QLabel('Last launch')
            head.setTextFormat(Qt.PlainText)
            font = head.font(); font.setBold(True); head.setFont(font)
            launch_layout.addWidget(head)
            status = _friendly_launch_status(last.get('status', 'Never launched'))
            started = last.get('started', '—')
            launch_layout.addWidget(QLabel('Status: '+status))
            launch_layout.addWidget(QLabel('Started: '+started))
            if app.get('last_error'):
                err = app['last_error']
                err_label = QLabel('Error: '+err.get('category', '')+' — '+err.get('detail', ''))
                err_label.setTextFormat(Qt.PlainText)
                err_label.setWordWrap(True)
                err_label.setStyleSheet('color: #b3402e;')
                launch_layout.addWidget(err_label)
                if last.get('log'):
                    log_btn = QPushButton('View Launch Log')
                    log_btn.setObjectName('ghost')
                    log_btn.clicked.connect(lambda: _show_log(last['log'], self))
                    launch_layout.addWidget(log_btn)
            layout.addWidget(launch_box)

        # Compatibility notes.
        if app['problems']:
            compat = QFrame()
            compat.setFrameShape(QFrame.StyledPanel)
            clayout = QVBoxLayout(compat)
            clayout.setContentsMargins(14, 12, 14, 12)
            chead = QLabel('Compatibility notes')
            chead.setTextFormat(Qt.PlainText)
            font = chead.font(); font.setBold(True); chead.setFont(font)
            clayout.addWidget(chead)
            for problem in app['problems']:
                clayout.addWidget(QLabel('• '+problem))
            layout.addWidget(compat)

        layout.addStretch(1)

        # Action buttons.
        action_row = QHBoxLayout(); action_row.setSpacing(8)
        open_btn = QPushButton('&Open')
        open_btn.setObjectName('primary')
        open_btn.setEnabled(bool(app['desktop']))
        open_btn.clicked.connect(lambda: self._do_action('open'))
        action_row.addWidget(open_btn)
        if can_reinstall(app):
            reinstall_btn = QPushButton('&Reinstall')
            reinstall_btn.setObjectName('ghost')
            reinstall_btn.clicked.connect(lambda: self._do_action('reinstall'))
            action_row.addWidget(reinstall_btn)
        if can_uninstall(app):
            uninstall_btn = QPushButton('&Uninstall')
            uninstall_btn.setObjectName('ghost')
            uninstall_btn.clicked.connect(lambda: self._do_action('uninstall'))
            action_row.addWidget(uninstall_btn)
        repair_btn = QPushButton('&Repair Launcher')
        repair_btn.setObjectName('ghost')
        repair_btn.clicked.connect(lambda: self._do_action('repair'))
        action_row.addWidget(repair_btn)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setStyleSheet(ui_style.primary_button_stylesheet(self) + ui_style.ghost_button_stylesheet(self))

    def _do_action(self, action):
        app = self.app
        if action == 'open':
            try:
                open_app(app); self.accept()
            except Exception as error:
                QMessageBox.warning(self, 'AppInstall', 'Could not launch '+app['name']+': '+str(error))
        elif action == 'reinstall':
            try:
                message = reinstall_app(app)
                QMessageBox.information(self, 'AppInstall', message); self.accept()
                parent = self.parent()
                if parent is not None and hasattr(parent, 'refresh'):
                    parent.refresh()
            except Exception as error:
                QMessageBox.warning(self, 'AppInstall', 'Reinstall failed: '+str(error))
        elif action == 'uninstall':
            try:
                message = uninstall_app(app)
                QMessageBox.information(self, 'AppInstall', message); self.accept()
                parent = self.parent()
                if parent is not None and hasattr(parent, 'refresh'):
                    parent.refresh()
            except Exception as error:
                QMessageBox.warning(self, 'AppInstall', 'Uninstall failed: '+str(error))
        elif action == 'repair':
            try:
                message = repair_launcher(app)
                QMessageBox.information(self, 'AppInstall', message); self.accept()
                parent = self.parent()
                if parent is not None and hasattr(parent, 'refresh'):
                    parent.refresh()
            except Exception as error:
                QMessageBox.warning(self, 'AppInstall', 'Repair failed: '+str(error))


def _show_log(path, parent):
    try:
        content = Path(path).read_bytes()[-monitor.LOG_BYTES:].decode(errors='replace')
    except OSError:
        content = 'The log file is not available.'
    dialog = QDialog(parent)
    dialog.setWindowTitle('AppInstall — Launch Log')
    dialog.resize(760, 500)
    layout = QVBoxLayout(dialog)
    text = QLabel(content)
    text.setTextFormat(Qt.PlainText)
    text.setWordWrap(True)
    text.setTextInteractionFlags(Qt.TextSelectableByMouse)
    scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(text)
    layout.addWidget(scroll)
    copy = QPushButton('Copy Log')
    copy.clicked.connect(lambda: QApplication.clipboard().setText(content))
    close = QPushButton('Close'); close.clicked.connect(dialog.accept)
    row = QHBoxLayout(); row.addWidget(copy); row.addStretch(1); row.addWidget(close)
    layout.addLayout(row)
    dialog.exec()


class ManagerWindow(QMainWindow):
    """Main window of the Installed Applications Manager."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle('AppInstall — My Applications')
        self.setMinimumWidth(760)
        self.resize(1000, 640)
        self.inventory = []
        self.filtered = []
        self.cards = {}
        self.loader = None
        self._inventory_revision = inventory_signature()
        self._refresh_pending = False
        self._build_ui()
        self._apply_style()
        # External installers atomically replace the registry files. Poll
        # lightweight metadata to detect changes even across rename/replace.
        self._inventory_timer = QTimer(self)
        self._inventory_timer.setInterval(1500)
        self._inventory_timer.timeout.connect(self._check_inventory_changes)
        self._inventory_timer.start()
        QTimer.singleShot(0, self.refresh)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        # Header.
        header = QHBoxLayout()
        header.setSpacing(12)
        heading = QLabel('My Applications')
        font = heading.font(); font.setPointSize(21); font.setBold(True); heading.setFont(font)
        header.addWidget(heading)
        self.install_url_btn = QPushButton('Install from URL…')
        self.install_url_btn.setObjectName('ghost')
        self.install_url_btn.setCursor(Qt.PointingHandCursor)
        self.install_url_btn.clicked.connect(self._install_from_url)
        header.addWidget(self.install_url_btn)
        header.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search applications…')
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(self._refilter)
        header.addWidget(self.search)
        root.addLayout(header)

        # Filters.
        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.filter_buttons = {}
        for label, fmt in [('All', None), ('AppImage', 'appimage'), ('Flatpak', 'flatpak'),
                           ('DEB', 'deb'), ('RPM', 'rpm')]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(fmt is None)
            btn.setObjectName('ghost')
            btn.clicked.connect(lambda checked, f=fmt: self._set_filter(f))
            filters.addWidget(btn)
            self.filter_buttons[fmt] = btn
        filters.addStretch(1)
        root.addLayout(filters)

        # List.
        self.list = QListWidget()
        self.list.setSpacing(10)
        self.list.setUniformItemSizes(False)
        root.addWidget(self.list, 1)

        # Status bar.
        self.status = QLabel('Loading…')
        self.status.setStyleSheet('color: palette(text); font-size: 12px;')
        root.addWidget(self.status)

        # Empty state (hidden by default).
        self.empty = QLabel('No AppInstall-managed applications found. Install a file to begin.')
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet('color: palette(text); font-size: 14px;')
        self.empty.hide()
        root.addWidget(self.empty)

    def _apply_style(self):
        self.setStyleSheet(ui_style.primary_button_stylesheet(self) + ui_style.ghost_button_stylesheet(self))

    def _check_inventory_changes(self):
        if inventory_signature() != self._inventory_revision:
            if self.loader and self.loader.isRunning():
                self._refresh_pending = True
            else:
                self.refresh()

    def refresh(self):
        if self.loader and self.loader.isRunning():
            self._refresh_pending = True
            return
        self._inventory_revision = inventory_signature()
        self.status.setText('Loading applications…')
        self.list.clear()
        self.cards.clear()
        self.empty.hide()
        self.loader = InventoryLoader()
        self.loader.done.connect(self._loaded)
        self.loader.failed.connect(self._load_failed)
        self.loader.finished.connect(self._refresh_if_changed_during_load)
        self.loader.start()

    def _refresh_if_changed_during_load(self):
        # Never lose a registry write while the inventory thread is loading.
        if self._refresh_pending or inventory_signature() != self._inventory_revision:
            self._refresh_pending = False
            QTimer.singleShot(0, self.refresh)

    def _loaded(self, inventory):
        self.inventory = inventory
        self.filtered = list(inventory)
        self._refilter()
        self.status.setText(f'{len(self.filtered)} application(s) managed by AppInstall')

    def _load_failed(self, message):
        self.status.setText('Could not load inventory: '+message)

    def _set_filter(self, fmt):
        for f, btn in self.filter_buttons.items():
            btn.setChecked(f == fmt)
        self.current_filter = fmt
        self._refilter()

    def _refilter(self):
        fmt = getattr(self, 'current_filter', None)
        text = self.search.text().strip().casefold()
        result = []
        for app in self.inventory:
            if fmt is not None and app['format'] != fmt:
                continue
            if text and text not in app['name'].casefold() and text not in app['package_id'].casefold():
                continue
            result.append(app)
        self.filtered = result
        self._rebuild()
        self.status.setText(f'{len(self.filtered)} application(s)')

    def _rebuild(self):
        self.list.clear()
        self.cards.clear()
        for app in self.filtered:
            card = AppCard(app)
            card.open_requested = self._open_app
            card.details_requested = self._show_details
            card.reinstall_requested = self._reinstall_app
            card.update_requested = self._update_app
            card.uninstall_requested = self._uninstall_app
            card.logs_requested = self._show_logs
            card.repair_requested = self._repair_app
            card.diagnostics_requested = self._open_diagnostics
            item = QListWidgetItem(self.list)
            item.setSizeHint(card.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, card)
            self.cards[app['key']] = card
        self.empty.setVisible(len(self.filtered) == 0 and not (self.loader and self.loader.isRunning()))

    # ── actions ──────────────────────────────────────────────────────────

    def _open_app(self, app):
        try:
            open_app(app)
        except Exception as error:
            QMessageBox.warning(self, 'AppInstall', 'Could not launch '+app['name']+': '+str(error))

    def _show_details(self, app):
        dialog = AppDetailsDialog(app, self)
        dialog.exec()

    def _reinstall_app(self, app):
        try:
            message = reinstall_app(app)
            QMessageBox.information(self, 'AppInstall', message)
            self.refresh()
        except Exception as error:
            QMessageBox.warning(self, 'AppInstall', 'Reinstall failed: '+str(error))

    def _update_app(self, app):
        if not can_update(app):
            QMessageBox.information(
                self, 'AppInstall',
                'Automatic updates are not supported for '+app['format']+' applications. '
                'Reinstall with a newer package file instead.')
            return
        reply = QMessageBox.question(
            self, 'AppInstall',
            'Check for updates to '+app['name']+'? This may update several packages '
            'in the user Flatpak installation.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            message = update_app(app)
            QMessageBox.information(self, 'AppInstall', message)
            self.refresh()
        except Exception as error:
            QMessageBox.warning(self, 'AppInstall', 'Update failed: '+str(error))

    def _uninstall_app(self, app):
        if not can_uninstall(app):
            QMessageBox.information(self, 'AppInstall', 'Uninstall is not supported for '+app['format']+' applications.')
            return
        reply = QMessageBox.question(
            self, 'AppInstall',
            'Uninstall '+app['name']+' ('+app['package_id']+')?\n\n'
            'Only AppInstall-managed files, launchers and metadata will be removed. '
            'Personal application data and logs will be kept.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            message = uninstall_app(app)
            QMessageBox.information(self, 'AppInstall', message)
            self.refresh()
        except Exception as error:
            QMessageBox.warning(self, 'AppInstall', 'Uninstall failed: '+str(error))

    def _show_logs(self, app):
        last = app.get('last_launch') or {}
        if not last.get('log'):
            QMessageBox.information(self, 'AppInstall', 'No launch log is available for '+app['name']+'.')
            return
        _show_log(last['log'], self)

    def _repair_app(self, app):
        try:
            message = repair_launcher(app)
            QMessageBox.information(self, 'AppInstall', message)
            self.refresh()
        except Exception as error:
            QMessageBox.warning(self, 'AppInstall', 'Repair failed: '+str(error))

    def _open_diagnostics(self, app):
        import subprocess, sys
        ui = Path(__file__).resolve().with_name('diagnostics_ui.py')
        subprocess.Popen([sys.executable, str(ui)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def _install_from_url(self):
        dialog = UrlInstallDialog(self)
        dialog.installed.connect(self.refresh)
        dialog.exec()


if __name__ == '__main__':
    app = QApplication(sys.argv[:1])
    ui_style.maybe_dark(app)
    window = ManagerWindow()
    window.show()
    shot = None
    if '--screenshot' in sys.argv:
        index = sys.argv.index('--screenshot')
        if index + 1 < len(sys.argv):
            shot = sys.argv[index + 1]
    if shot:
        def grab():
            app.processEvents()
            window.list.repaint()
            window.grab().save(shot)
            app.quit()
        QTimer.singleShot(1500, grab)
    sys.exit(app.exec())

