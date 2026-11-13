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
import time
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
UPDATE_TTL_SECONDS = 12 * 60 * 60  # ~12 hours between automatic checks
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
    from qt_compat import QtGui
    QIcon = QtGui.QIcon
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


def _launcher_exists(record, key=None):
    """A managed launcher is real if the recorded desktop entry OR any
    AppInstall-owned export path exists on disk."""
    desktop = record.get('desktop') or ''
    if desktop and Path(desktop).is_file():
        return True
    for entry in record.get('exports', []):
        path = entry.get('path') if isinstance(entry, dict) else None
        if path and Path(path).is_file():
            return True
    # A menu entry may have been moved to KDE's desktop. Its bytes and
    # AppInstall launch ID must still match the owned record before trusting it.
    if key:
        try:
            spec = monitor.registry().get(key, {})
            if monitor.relocated_desktop_launcher(spec) is not None:
                return True
        except (OSError, ValueError, AttributeError):
            pass
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


def app_disk_usage(app):
    """Best-effort bytes attributable to one managed app, or None.

    AppImage: the generation file. DEB/RPM: the staged package file — the
    container filesystem is shared, so installed size is not attributable
    per application. Flatpak: owned by the Flatpak installation, not a file.
    """
    if app.get('format') not in ('appimage', 'deb', 'rpm'):
        return None
    target = app.get('target')
    if not target:
        return None
    try:
        return Path(target).stat().st_size
    except OSError:
        return None


def format_size(size):
    """Human-readable size for the manager; an em dash when unknown."""
    if size is None:
        return '—'
    if size < 1024:
        return f'{size:.0f} B'
    value = float(size)
    for unit in ('KB', 'MB', 'GB', 'TB'):
        value /= 1024.0
        if value < 1024.0:
            return f'{value:.1f} {unit}'
    return f'{value:.1f} PB'


# Extension → MIME mapping for dropped package files. Every value must also
# appear in the MimeType= line of appinstall.desktop (enforced by tests). The
# iso9660-appimage and quickdrop-appimage MIME types are AppImage containers
# sharing the same .AppImage extension, so no extra entry is needed.
PACKAGE_MIMES = {
    '.deb': 'application/vnd.debian.binary-package',
    '.rpm': 'application/x-rpm',
    '.appimage': 'application/vnd.appimage',
    '.flatpak': 'application/vnd.flatpak',
    '.flatpakref': 'application/vnd.flatpak.ref',
    '.flatpakrepo': 'application/vnd.flatpak.repo',
}


def classify_package(path):
    """Desktop-listed MIME type for a dropped package file, or None."""
    target = Path(path)
    try:
        if not target.is_file():
            return None
    except OSError:
        return None
    return PACKAGE_MIMES.get(target.suffix.lower())


def _appinstall_command():
    """Path of the appinstall CLI hosting the normal per-file review."""
    command = Path(__file__).with_name('appinstall')
    if command.is_file():
        return command
    return Path.home()/'.local/bin/appinstall'


class BatchItem:
    """One dropped file and its install state."""
    QUEUED = 'queued'
    RUNNING = 'running'
    INSTALLED = 'installed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    UNSUPPORTED = 'unsupported'

    def __init__(self, path):
        self.path = Path(path)
        self.mime = classify_package(path)
        self.state = BatchItem.QUEUED if self.mime else BatchItem.UNSUPPORTED
        self.exit_code = None


class BatchQueue:
    """Sequential queue state for batch installs. Qt-free on purpose so the
    state transitions are testable without spawning processes."""

    def __init__(self, paths=()):
        self.items = [BatchItem(path) for path in paths]

    def runnable(self):
        """Index of the next item to review, or None when nothing is queued."""
        for index, item in enumerate(self.items):
            if item.state == BatchItem.QUEUED:
                return index
        return None

    def started(self, index):
        item = self.items[index]
        if item.state == BatchItem.QUEUED:
            item.state = BatchItem.RUNNING

    def finished(self, index, exit_code):
        item = self.items[index]
        if item.state != BatchItem.RUNNING:
            return  # Cancelled mid-review keeps its Cancelled verdict.
        item.exit_code = exit_code
        item.state = BatchItem.INSTALLED if exit_code == 0 else BatchItem.FAILED

    def cancel(self, index):
        item = self.items[index]
        if item.state in (BatchItem.QUEUED, BatchItem.RUNNING):
            item.state = BatchItem.CANCELLED

    def busy(self):
        return any(item.state == BatchItem.RUNNING for item in self.items)

    def pending(self):
        return any(item.state in (BatchItem.QUEUED, BatchItem.RUNNING)
                   for item in self.items)



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
        if not _launcher_exists(raw, key):
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
        if not _launcher_exists(raw, key):
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


def uninstall_cleanup_items(app):
    """Data that can be reliably tied to this app and offered for cleanup.

    Every item is an exact path. AppInstall-owned launchers and icons come
    from the registry record; launch logs and history come from the app's
    keyed state directory; AppImage targets and manifests come from the
    record itself. Personal application data is never offered.
    """
    items = []
    for entry in app.get('exports', []) + app.get('icons', []):
        path = entry.get('path', '')
        if path:
            items.append(('Export', path))
    key = app['key']
    history_dir = Path(os.environ.get('XDG_STATE_HOME',
                                      Path.home()/'.local/state'))/'appinstall'/'launches'/hashlib.sha256(key.encode()).hexdigest()[:20]
    if history_dir.is_dir():
        items.append(('Launch history', str(history_dir)))
    if app['format'] == 'appimage':
        for path in (app.get('target'), app.get('manifest')):
            if path:
                items.append(('AppImage file', path))
    elif app['format'] in ('deb', 'rpm') and app.get('container'):
        items.append(('Container', app['container']))
    # De-duplicate while preserving order.
    seen = set()
    unique = []
    for label, path in items:
        if path not in seen:
            seen.add(path)
            unique.append((label, path))
    return unique


def uninstall_app(app, cleanup=()):
    """Safe uninstall via diagnostics_core. Removes only AppInstall-owned
    artifacts, plus any cleanup paths explicitly selected by the user."""
    if not can_uninstall(app):
        raise RuntimeError('Uninstall is not supported for '+app['format']+' applications.')
    core.uninstall(app['key'], cleanup=set(cleanup))
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


def container_health_report(app):
    """Health report for a container-backed app (deb/rpm), or None otherwise."""
    if app['format'] not in ('deb', 'rpm'):
        return None
    from container_backend import Engine
    engine = Engine()
    try:
        return engine.container_health(app['key'])
    finally:
        engine.close()


def repair_container_app(app):
    """Repair/ensure the container for a deb/rpm app."""
    if app['format'] not in ('deb', 'rpm'):
        raise RuntimeError('Container repair is not supported for '+app['format']+' applications.')
    return core.repair_container(app['key'])


def reexport_launcher(app):
    """Re-export the application launcher for a deb/rpm app."""
    if app['format'] not in ('deb', 'rpm'):
        raise RuntimeError('Launcher re-export is not supported for '+app['format']+' applications.')
    return core.repair_export(app['key'])


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

from qt_compat import QtCore, Signal
Qt = QtCore.Qt
QProcess = QtCore.QProcess
QThread = QtCore.QThread
QTimer = QtCore.QTimer
QSize = QtCore.QSize
from qt_compat import QtGui
QIcon = QtGui.QIcon
QPixmap = QtGui.QPixmap
QColor = QtGui.QColor
QPalette = QtGui.QPalette
from qt_compat import QtWidgets
QApplication = QtWidgets.QApplication
QComboBox = QtWidgets.QComboBox
QMainWindow = QtWidgets.QMainWindow
QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QLineEdit = QtWidgets.QLineEdit
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QFrame = QtWidgets.QFrame
QSizePolicy = QtWidgets.QSizePolicy
QMessageBox = QtWidgets.QMessageBox
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QScrollArea = QtWidgets.QScrollArea
QGridLayout = QtWidgets.QGridLayout
QSpacerItem = QtWidgets.QSpacerItem
QMenu = QtWidgets.QMenu
QStackedLayout = QtWidgets.QStackedLayout
QCheckBox = QtWidgets.QCheckBox

import ui_style
import settings

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

    def __init__(self, app, parent=None, pinned=False):
        super().__init__(parent)
        self.app = app
        self.pinned = pinned
        self.setMinimumWidth(300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(132)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        # Icon.
        self.icon = QLabel()
        self.icon.setFixedSize(64, 64)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setScaledContents(True)
        pix = self._icon_pixmap()
        self.icon.setPixmap(pix)
        self.icon.setStyleSheet('border-radius: 8px; background: palette(base);')
        layout.addWidget(self.icon, 0)

        # Summary.
        summary = QVBoxLayout()
        summary.setSpacing(4)
        self.name = QLabel(('★ ' if pinned else '')+app['name'])
        self.name.setTextFormat(Qt.TextFormat.PlainText)
        self.name.setWordWrap(True)
        font = self.name.font(); font.setPointSizeF(font.pointSizeF() * 1.12); font.setBold(True)
        self.name.setFont(font)
        summary.addWidget(self.name)

        meta = QLabel(self._meta_text())
        meta.setTextFormat(Qt.TextFormat.PlainText)
        meta.setWordWrap(True)
        meta.setStyleSheet('color: palette(text); font-size: 12px;')
        summary.addWidget(meta)

        self.status = QLabel(self._status_text())
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setStyleSheet(self._status_style())
        summary.addWidget(self.status)

        if app['problems']:
            note = QLabel('⚠ '+'; '.join(app['problems']))
            note.setTextFormat(Qt.TextFormat.PlainText)
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
        self.pin_requested = None
        self.health_requested = None
        self.container_repair_requested = None
        self.reexport_requested = None

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
        size = app_disk_usage(app)
        if size is not None:
            parts.append(format_size(size))
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
        menu.addAction('Unpin from top' if self.pinned else 'Pin to top', self._emit_pin)
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
        if app['format'] in ('deb', 'rpm'):
            menu.addSection('Container')
            menu.addAction('Container Health…', self._emit_health)
            menu.addAction('Repair Container', self._emit_container_repair)
            menu.addAction('Re-export Launcher', self._emit_reexport)
        return menu

    def _emit_open(self):
        if self.open_requested:
            self.open_requested(self.app)

    def _emit_details(self):
        if self.details_requested:
            self.details_requested(self.app)

    def _emit_pin(self):
        if self.pin_requested:
            self.pin_requested(self.app)

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

    def _emit_health(self):
        if hasattr(self, 'health_requested') and self.health_requested:
            self.health_requested(self.app)

    def _emit_container_repair(self):
        if hasattr(self, 'container_repair_requested') and self.container_repair_requested:
            self.container_repair_requested(self.app)

    def _emit_reexport(self):
        if hasattr(self, 'reexport_requested') and self.reexport_requested:
            self.reexport_requested(self.app)


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
        header.addWidget(picture, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(4)
        title = QLabel(app['name'])
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setWordWrap(True)
        font = title.font(); font.setPointSizeF(font.pointSizeF() * 1.3); font.setBold(True)
        title.setFont(font)
        text.addWidget(title)
        kind = QLabel(FORMAT_LABELS.get(app['format'], app['format'])+' · '+app['status'])
        kind.setTextFormat(Qt.TextFormat.PlainText)
        kind.setStyleSheet('color: palette(text); font-size: 13px;')
        text.addWidget(kind)
        header.addLayout(text, 1)
        layout.addLayout(header)

        if app['description']:
            desc = QLabel(app['description'])
            desc.setTextFormat(Qt.TextFormat.PlainText)
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
            ('Package size', format_size(app_disk_usage(app))),
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
            value_label.setTextFormat(Qt.TextFormat.PlainText)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value_label.setToolTip(str(value))
            grid.addWidget(value_label, row, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        # Last launch.
        last = app.get('last_launch') or {}
        if last or app.get('last_error'):
            launch_box = QFrame()
            launch_box.setFrameShape(QFrame.Shape.StyledPanel)
            launch_layout = QVBoxLayout(launch_box)
            launch_layout.setContentsMargins(14, 12, 14, 12)
            launch_layout.setSpacing(6)
            head = QLabel('Last launch')
            head.setTextFormat(Qt.TextFormat.PlainText)
            font = head.font(); font.setBold(True); head.setFont(font)
            launch_layout.addWidget(head)
            status = _friendly_launch_status(last.get('status', 'Never launched'))
            started = last.get('started', '—')
            launch_layout.addWidget(QLabel('Status: '+status))
            launch_layout.addWidget(QLabel('Started: '+started))
            if app.get('last_error'):
                err = app['last_error']
                err_label = QLabel('Error: '+err.get('category', '')+' — '+err.get('detail', ''))
                err_label.setTextFormat(Qt.TextFormat.PlainText)
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
            compat.setFrameShape(QFrame.Shape.StyledPanel)
            clayout = QVBoxLayout(compat)
            clayout.setContentsMargins(14, 12, 14, 12)
            chead = QLabel('Compatibility notes')
            chead.setTextFormat(Qt.TextFormat.PlainText)
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

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
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
    text.setTextFormat(Qt.TextFormat.PlainText)
    text.setWordWrap(True)
    text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(text)
    layout.addWidget(scroll)
    copy = QPushButton('Copy Log')
    copy.clicked.connect(lambda: QApplication.clipboard().setText(content))
    close = QPushButton('Close'); close.clicked.connect(dialog.accept)
    row = QHBoxLayout(); row.addWidget(copy); row.addStretch(1); row.addWidget(close)
    layout.addLayout(row)
    dialog.exec()


class BatchQueueDialog(QDialog):
    """Modeless progress list for a drag-and-drop batch install.

    One file runs at a time through the normal `appinstall FILE` review so
    confirm dialogs never overlap. Every file keeps its own row and result;
    cancelling a queued row skips it, cancelling the running row closes that
    review and the queue moves on with the remaining files. Closing the
    dialog never kills a running review — it is an independent app window.
    """

    def __init__(self, queue, parent=None):
        super().__init__(parent)
        self.queue = queue
        self.process = None
        self._active_index = None
        self._kill_timer = None
        self.rows = {}
        self._closed = False
        self.setWindowTitle('Installing Files')
        self.setMinimumWidth(480)
        self.setModal(False)
        root = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list.setAlternatingRowColors(True)
        root.addWidget(self.list)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        for index, item in enumerate(self.queue.items):
            self._add_row(index, item)
        self._run_next()

    def _add_row(self, index, item):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 4, 8, 4)
        name = QLabel(item.path.name)
        name.setToolTip(str(item.path))
        layout.addWidget(name, 1)
        status = QLabel(self._status_text(item))
        layout.addWidget(status)
        cancel = QPushButton('Cancel')
        cancel.setObjectName('ghost')
        cancel.clicked.connect(lambda checked=False, i=index: self._cancel(i))
        layout.addWidget(cancel)
        wrapper = QListWidgetItem()
        wrapper.setSizeHint(row.sizeHint())
        self.list.addItem(wrapper)
        self.list.setItemWidget(wrapper, row)
        active = item.state in (BatchItem.QUEUED, BatchItem.RUNNING)
        cancel.setEnabled(active)
        cancel.setVisible(active)
        self.rows[index] = (status, cancel)

    @staticmethod
    def _status_text(item):
        if item.state == BatchItem.QUEUED:
            return 'Queued'
        if item.state == BatchItem.RUNNING:
            return 'Review open…'
        if item.state == BatchItem.INSTALLED:
            return 'Installed'
        if item.state == BatchItem.FAILED:
            return f'Failed (exit {item.exit_code})'
        if item.state == BatchItem.CANCELLED:
            return 'Cancelled'
        return 'Unsupported type'

    def _refresh(self, index):
        item = self.queue.items[index]
        status, cancel = self.rows[index]
        status.setText(self._status_text(item))
        active = item.state in (BatchItem.QUEUED, BatchItem.RUNNING)
        cancel.setEnabled(active)
        cancel.setVisible(active)

    def _refresh_all(self):
        for index in self.rows:
            self._refresh(index)

    def append(self, paths):
        """Add more dropped files to a dialog that is already open."""
        for path in paths:
            index = len(self.queue.items)
            self.queue.items.append(BatchItem(path))
            self._add_row(index, self.queue.items[index])
        if not self.queue.busy():
            self._run_next()

    def reject(self):
        """Close button (X / Escape / the Close button) cancels the active
        review, marks it Cancelled, then shuts the dialog. The terminated
        review becomes an independent orphan process; the queue never starts
        the next item after a close."""
        if self._active_index is not None:
            self.queue.cancel(self._active_index)
            self._refresh(self._active_index)
        if self.process is not None:
            self.process.terminate()
        self._closed = True
        self.process = None
        self._active_index = None
        super().reject()

    def _force_kill_and_close(self):
        self._kill_timer = None
        if self.process is not None:
            self.process.kill()
            self._closed = True
        super().reject()

    def _run_next(self):
        if self._closed:
            self.process = None
            self._active_index = None
            return
        index = self.queue.runnable()
        if index is None:
            self.process = None
            self._active_index = None
            return
        item = self.queue.items[index]
        self.queue.started(index)
        self._refresh(index)
        self._active_index = index
        self.process = QProcess(self)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_process_error)
        self.process.start(str(_appinstall_command()), ['--', str(item.path)])

    def _on_finished(self, exit_code=None, status=None):
        if self._kill_timer is not None:
            self._kill_timer.stop()
            self._kill_timer = None
        process = self.process
        self.process = None
        if self._active_index is None:
            return
        index = self._active_index
        self._active_index = None
        code = process.exitCode() if exit_code is None else exit_code
        self.queue.finished(index, code)
        self._refresh(index)
        self._run_next()

    def _on_process_error(self, error):
        # finished() is not emitted when the process never started.
        if error == QProcess.ProcessError.FailedToStart:
            self._on_finished(-1)

    def _cancel(self, index):
        item = self.queue.items[index]
        if item.state not in (BatchItem.QUEUED, BatchItem.RUNNING):
            return
        running = item.state == BatchItem.RUNNING
        self.queue.cancel(index)
        self._refresh(index)
        if running and self.process is not None:
            self.process.terminate()
            kill_timer = QTimer(self)
            kill_timer.setSingleShot(True)
            kill_timer.timeout.connect(self._force_kill)
            kill_timer.start(3000)
            self._kill_timer = kill_timer
        elif not self.queue.busy():
            self._run_next()

    def _force_kill(self):
        self._kill_timer = None
        if self.process is not None:
            self.process.kill()


class HealthDialog(QDialog):
    """Health report for one container-backed app, with repair actions.

    Shows per-check results (container exists, responsive, exports intact)
    and any issues. Repair and re-export are exposed as signals so the
    window can run them and refresh the inventory afterward.
    """

    repair_requested = Signal()
    reexport_requested = Signal()

    def __init__(self, app, report, parent=None):
        super().__init__(parent)
        self.app = app
        self.report = report
        self.setWindowTitle('Container Health — '+app['name'])
        self.setMinimumWidth(560)
        self.setModal(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 20)
        root.setSpacing(14)

        title = QLabel('Container '+app.get('container',''))
        font = title.font(); font.setPointSizeF(font.pointSizeF()*1.3); font.setBold(True)
        title.setTextFormat(Qt.TextFormat.PlainText)
        root.addWidget(title)

        checks = report.get('checks', {})
        labels = {
            'container_exists': 'Container exists',
            'container_responsive': 'Container responds',
            'exports_intact': 'Exported launchers intact',
        }
        for key, label in labels.items():
            row = QHBoxLayout()
            ok = checks.get(key, False)
            dot = QLabel('●' if ok else '○')
            dot.setStyleSheet('color: #2e7d32;' if ok else 'color: #b3402e;')
            dot.setFixedWidth(14)
            text = QLabel(label + ' — ' + ('OK' if ok else 'Problem'))
            text.setTextFormat(Qt.TextFormat.PlainText)
            row.addWidget(dot)
            row.addWidget(text, 1)
            root.addLayout(row)

        issues = report.get('issues', [])
        if issues:
            box = QFrame()
            box.setFrameShape(QFrame.Shape.StyledPanel)
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(12, 10, 12, 10)
            box_layout.setSpacing(6)
            head = QLabel('Issues')
            head_font = head.font(); head_font.setBold(True); head.setFont(head_font)
            box_layout.addWidget(head)
            for issue in issues:
                line = QLabel('• '+issue)
                line.setTextFormat(Qt.TextFormat.PlainText)
                line.setWordWrap(True)
                box_layout.addWidget(line)
            root.addWidget(box)

        buttons = QDialogButtonBox()
        repair = buttons.addButton('Repair Container', QDialogButtonBox.ButtonRole.ActionRole)
        repair.clicked.connect(self._repair)
        reexport = buttons.addButton('Re-export Launcher', QDialogButtonBox.ButtonRole.ActionRole)
        reexport.clicked.connect(self._reexport)
        close = buttons.addButton('Close', QDialogButtonBox.ButtonRole.RejectRole)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.repair_btn = repair
        self.reexport_btn = reexport
        self._refresh_buttons()

    def _refresh_buttons(self):
        healthy = self.report.get('healthy', False)
        self.repair_btn.setEnabled(not healthy)
        self.reexport_btn.setEnabled(not healthy)

    def _repair(self):
        self.repair_requested.emit()

    def _reexport(self):
        self.reexport_requested.emit()


class UninstallDialog(QDialog):
    """Confirm uninstall and choose which app-tied data to clean up.

    Every cleanup checkbox is unchecked by default — nothing is silently
    deleted. Only data that can be reliably tied to this app is offered:
    exported launchers, installed icons, launch logs/history, and (for
    DEB/RPM) the container. Exact paths are shown so the user knows what
    will be removed.
    """

    def __init__(self, app, items, parent=None):
        super().__init__(parent)
        self.app = app
        self.items = items  # list of (label, path)
        self.setWindowTitle('Uninstall — '+app['name'])
        self.setMinimumWidth(640)
        self.setModal(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 20)
        root.setSpacing(14)

        head = QLabel('Uninstall '+app['name']+'?')
        font = head.font(); font.setPointSizeF(font.pointSizeF()*1.3); font.setBold(True)
        head.setTextFormat(Qt.TextFormat.PlainText)
        root.addWidget(head)

        sub = QLabel('Only AppInstall-managed files will be removed. Personal '
                     'application data is always kept. Choose additional data '
                     'to clean up below (nothing is selected by default).')
        sub.setTextFormat(Qt.TextFormat.PlainText)
        sub.setWordWrap(True)
        sub.setStyleSheet('color: palette(text); font-size: 12px;')
        root.addWidget(sub)

        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        bl = QVBoxLayout(box)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.setSpacing(8)
        bl.addWidget(QLabel('Clean up'))
        self.checks = {}
        for label, path in items:
            cb = QCheckBox(label+' — '+path)
            cb.setChecked(False)
            cb.setToolTip('Remove '+path)
            bl.addWidget(cb)
            self.checks[path] = cb
        root.addWidget(box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Uninstall')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def selected_paths(self):
        return {path for path, cb in self.checks.items() if cb.isChecked()}


class ManagerWindow(QMainWindow):
    """Main window of the Installed Applications Manager."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle('AppInstall — My Applications')
        self.setWindowIcon(QIcon.fromTheme('appinstall'))
        self.setMinimumWidth(760)
        self.resize(1000, 640)
        self.inventory = []
        self.filtered = []
        self.cards = {}
        self.favorites = set(settings.read().get('favorites', []))
        self.loader = None
        self.setAcceptDrops(True)
        self.batch_dialog = None
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
        self.update_helper = Path(__file__).with_name('appinstall-installer')
        self.update_process = QProcess(self)
        self.update_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.update_process.finished.connect(self._update_finished)
        self.update_process.errorOccurred.connect(self._update_process_error)
        self.update_operation = ''
        self.update_tag = ''
        if self.update_helper.is_file():
            self.update_row.show()
            QTimer.singleShot(1200, self._check_updates)
            self.update_timer = QTimer(self)
            self.update_timer.setInterval(4 * 60 * 60 * 1000)
            self.update_timer.timeout.connect(self._check_updates)
            self.update_timer.start()


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
        self.install_file_btn = QPushButton('Install from File…')
        self.install_file_btn.setObjectName('ghost')
        self.install_file_btn.clicked.connect(lambda: ui_style.open_package(self))
        header.addWidget(self.install_file_btn)
        self.install_url_btn = QPushButton('Install from URL…')
        self.install_url_btn.setObjectName('ghost')
        self.install_url_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_url_btn.clicked.connect(self._install_from_url)
        header.addWidget(self.install_url_btn)
        header.addStretch(1)
        self.theme_button = QPushButton('Theme')
        self.theme_button.setObjectName('ghost')
        self.theme_menu = QMenu(self.theme_button)
        self.theme_actions = {}
        for theme_id, label in (('auto', 'Follow system'), ('light', 'Light'), ('dark', 'Dark')):
            action = self.theme_menu.addAction(label)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, t=theme_id: self._set_theme(t))
            self.theme_actions[theme_id] = action
        self.theme_button.setMenu(self.theme_menu)
        self._sync_theme_menu()
        header.addWidget(self.theme_button)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search applications…')
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(self._refilter)
        header.addWidget(self.search)
        root.addLayout(header)

        self.update_row = QWidget()
        updates = QHBoxLayout(self.update_row)
        updates.setContentsMargins(0, 0, 0, 0)
        self.update_status = QLabel('AppInstall updates')
        self.update_status.setTextFormat(Qt.TextFormat.PlainText)
        updates.addWidget(self.update_status, 1)
        self.update_check_button = QPushButton('Check for Updates')
        self.update_check_button.clicked.connect(lambda: self._check_updates(manual=True))
        updates.addWidget(self.update_check_button)
        self.update_button = QPushButton('Update AppInstall')
        self.update_button.clicked.connect(self._install_update)
        self.update_button.hide()
        updates.addWidget(self.update_button)
        self.update_row.hide()
        root.addWidget(self.update_row)

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
        self.status_filter = QComboBox()
        self.status_filter.addItem('All statuses', None)
        for label, status in (('Installed', STATUS_INSTALLED),
                              ('Needs repair', STATUS_NEEDS_REPAIR),
                              ('Files missing', STATUS_MISSING),
                              ('Stale record', STATUS_STALE),
                              ('Corrupted', STATUS_CORRUPTED)):
            self.status_filter.addItem(label, status)
        self.status_filter.currentIndexChanged.connect(lambda index: self._refilter())
        filters.addWidget(self.status_filter)
        filters.addStretch(1)
        self.sort_combo = QComboBox()
        for label, sort_key in (('Name (A–Z)', 'name-asc'), ('Name (Z–A)', 'name-desc'),
                                ('Recently launched', 'recent'), ('Size (largest)', 'size')):
            self.sort_combo.addItem(label, sort_key)
        self.sort_combo.currentIndexChanged.connect(lambda index: self._refilter())
        filters.addWidget(self.sort_combo)
        root.addLayout(filters)

        # List.
        self.list = QListWidget()
        self.list.setSpacing(10)
        self.list.setUniformItemSizes(False)

        # Empty state (stacked behind the list, shown when nothing matches).
        self.empty = QLabel('No AppInstall-managed applications found. Install a file to begin.')
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet('color: palette(text); font-size: 14px;')

        self.content_stack = QStackedLayout()
        self.content_stack.addWidget(self.list)     # index 0: list
        self.content_stack.addWidget(self.empty)    # index 1: empty message
        content_widget = QWidget()
        content_widget.setLayout(self.content_stack)
        root.addWidget(content_widget, 1)

        # Status bar.
        self.status = QLabel('Loading…')
        self.status.setStyleSheet('color: palette(text); font-size: 12px;')
        root.addWidget(self.status)

        # Empty state (hidden by default).
        self.empty = QLabel('No AppInstall-managed applications found. Install a file to begin.')
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self._set_status_count()

    def _set_status_count(self):
        count = len(self.filtered)
        noun = 'application' if count == 1 else 'applications'
        self.status.setText(f'{count} {noun} managed by AppInstall')

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
        status = self.status_filter.currentData()
        sort_key = self.sort_combo.currentData() or 'name-asc'
        result = []
        for app in self.inventory:
            if fmt is not None and app['format'] != fmt:
                continue
            if status is not None and app['status'] != status:
                continue
            if text and text not in app['name'].casefold() and text not in app['package_id'].casefold():
                continue
            result.append(app)
        self.filtered = self._sorted(result, sort_key)
        self._rebuild()
        self._set_status_count()

    def _sorted(self, apps, sort_key):
        """Apply the chosen ordering; favorites always sort to the top."""
        def base(app):
            return app['name'].casefold()

        if sort_key == 'name-desc':
            ordered = sorted(apps, key=base, reverse=True)
        elif sort_key == 'recent':
            def stamp(app):
                last = app.get('last_launch') or {}
                return last.get('started') or ''
            ordered = sorted(apps, key=stamp, reverse=True)
        elif sort_key == 'size':
            def bulk(app):
                size = app_disk_usage(app)
                return (size is None, -(size or 0))
            ordered = sorted(apps, key=bulk)
        else:
            ordered = sorted(apps, key=base)
        pinned = [app for app in ordered if app['key'] in self.favorites]
        rest = [app for app in ordered if app['key'] not in self.favorites]
        return pinned + rest

    def _rebuild(self):
        self.list.clear()
        self.cards.clear()
        for app in self.filtered:
            card = AppCard(app, pinned=app['key'] in self.favorites)
            card.open_requested = self._open_app
            card.details_requested = self._show_details
            card.pin_requested = self._toggle_pin
            card.reinstall_requested = self._reinstall_app
            card.update_requested = self._update_app
            card.uninstall_requested = self._uninstall_app
            card.logs_requested = self._show_logs
            card.repair_requested = self._repair_app
            card.diagnostics_requested = self._open_diagnostics
            card.health_requested = self._health_app
            card.container_repair_requested = self._repair_container_app
            card.reexport_requested = self._reexport_app
            item = QListWidgetItem(self.list)
            item.setSizeHint(card.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, card)
            self.cards[app['key']] = card
        loading = self.loader is not None and self.loader.isRunning()
        self.content_stack.setCurrentIndex(
            1 if (len(self.filtered) == 0 and not loading) else 0)

    def _toggle_pin(self, app):
        key = app['key']
        if key in self.favorites:
            self.favorites.discard(key)
        else:
            self.favorites.add(key)
        try:
            settings.update('favorites', sorted(self.favorites))
        except OSError:
            # Settings are best-effort; the pin still applies for this session.
            pass
        self._refilter()

    def _set_theme(self, theme):
        try:
            settings.update('theme', theme)
        except OSError:
            pass
        ui_style.apply_theme(QApplication.instance(), theme)
        self._sync_theme_menu()
        self._apply_style()
        for card in self.cards.values():
            card.setStyleSheet(ui_style.primary_button_stylesheet(card) +
                               ui_style.ghost_button_stylesheet(card))

    def _sync_theme_menu(self):
        theme = settings.read().get('theme', 'auto')
        for theme_id, action in self.theme_actions.items():
            action.setChecked(theme_id == theme)

    # ── Drag-and-drop batch install ──────────────────────────────────────

    def dragEnterEvent(self, event):
        if self._acceptable(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    @staticmethod
    def _acceptable(mime_data):
        if not mime_data.hasUrls():
            return False
        return any(classify_package(url.toLocalFile())
                   for url in mime_data.urls())

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls()
                 if url.isLocalFile()]
        if paths:
            self.open_batch(paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    def open_batch(self, paths):
        """Queue dropped files; reuse the open batch dialog if there is one."""
        if self.batch_dialog is not None and self.batch_dialog.isVisible():
            self.batch_dialog.append(paths)
            self.batch_dialog.raise_()
            self.batch_dialog.activateWindow()
            return self.batch_dialog
        dialog = BatchQueueDialog(BatchQueue(paths), self)
        dialog.finished.connect(self._batch_dialog_closed)
        dialog.show()
        self.batch_dialog = dialog
        return dialog

    def _batch_dialog_closed(self, result=None):
        self.batch_dialog = None

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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
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
        items = uninstall_cleanup_items(app)
        dialog = UninstallDialog(app, items, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            message = uninstall_app(app, cleanup=dialog.selected_paths())
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

    def _health_app(self, app):
        report = container_health_report(app)
        if report is None:
            QMessageBox.information(self, 'AppInstall', 'Container health is not tracked for '+app['format']+' applications.')
            return
        dialog = HealthDialog(app, report, self)
        dialog.repair_requested.connect(lambda: self._repair_container_app(app))
        dialog.reexport_requested.connect(lambda: self._reexport_app(app))
        dialog.exec()

    def _repair_container_app(self, app):
        try:
            message = repair_container_app(app)
            QMessageBox.information(self, 'AppInstall', message)
            self.refresh()
        except Exception as error:
            QMessageBox.warning(self, 'AppInstall', 'Container repair failed: '+str(error))

    def _reexport_app(self, app):
        try:
            message = reexport_launcher(app)
            QMessageBox.information(self, 'AppInstall', message)
            self.refresh()
        except Exception as error:
            QMessageBox.warning(self, 'AppInstall', 'Launcher re-export failed: '+str(error))

    def _check_updates(self, manual=False):
        if self.update_operation or self.update_tag:
            return
        if not manual:
            last_check = settings.read().get('last_update_check', 0)
            now = time.time()
            if now - last_check < UPDATE_TTL_SECONDS:
                # Within TTL: do not re-check automatically.
                if self.update_tag:
                    self.update_status.setText(
                        f'AppInstall {self.update_tag} is available')
                    self.update_check_button.hide()
                    self.update_button.show()
                else:
                    self.update_status.setText('AppInstall is up to date')
                return
        self.update_operation = 'check'
        self.update_manual = manual
        self.update_status.setText('Checking for updates…')
        self.update_check_button.setEnabled(False)
        self.update_process.start('/usr/bin/bash', [str(self.update_helper), '--desktop-check'])
        self.update_process.closeWriteChannel()

    def _install_update(self):
        if self.update_operation or not self.update_tag:
            return
        self.update_operation = 'install'
        self.update_button.setEnabled(False)
        self.update_check_button.setEnabled(False)
        self.update_status.setText(f'Installing AppInstall {self.update_tag}…')
        self.update_process.start('/usr/bin/bash', [
            str(self.update_helper), '--desktop-update', self.update_tag,
        ])
        self.update_process.closeWriteChannel()

    def _update_process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._update_finished(1, QProcess.ExitStatus.CrashExit)

    def _update_finished(self, exit_code, exit_status):
        operation, self.update_operation = self.update_operation, ''
        output = bytes(self.update_process.readAll()).decode(errors='replace')
        self.update_check_button.setEnabled(True)
        self.update_button.setEnabled(True)
        ok = exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit
        if operation == 'check':
            # Record that a check was performed so auto checks respect the TTL.
            try:
                settings.update('last_update_check', int(time.time()))
            except OSError:
                pass
            import re
            match = re.search(r'^APPINSTALL_UPDATE=(v[0-9]+\.[0-9]+\.[0-9]+)$', output, re.M)
            if ok and match:
                self.update_tag = match[1]
                self.update_status.setText(f'AppInstall {self.update_tag} is available')
                self.update_check_button.hide()
                self.update_button.show()
                self._notify_update(match[1])
            elif ok:
                self.update_status.setText('AppInstall is up to date')
            else:
                self.update_status.setText('Could not check for updates')
                if self.update_manual:
                    self._show_update_details('Update check failed', output)
        elif operation == 'install':
            tag = self.update_tag
            self.update_tag = ''
            self.update_button.hide()
            self.update_check_button.show()
            if not ok or f'APPINSTALL_UPDATED={tag}' not in output.splitlines():
                self.update_status.setText('Update did not complete')
                self._show_update_details('AppInstall update did not complete', output)
                return
            self.update_status.setText(f'AppInstall {tag} installed. Reopen AppInstall to use it.')
            notes_path = Path('/usr/share/appinstall/RELEASE_NOTES.md')
            try:
                notes = notes_path.read_text(encoding='utf-8')
            except (OSError, UnicodeError):
                notes = f'https://github.com/aboodmohd/-AppInstall/releases/tag/{tag}'
            self._show_update_details(f'What’s new in AppInstall {tag}', notes)

    def _notify_update(self, tag):
        """Best-effort desktop notification; headless-safe."""
        if not settings.read().get('notifications', False):
            return
        try:
            subprocess.run(
                ['notify-send', 'AppInstall',
                 f'Version {tag} is available'],
                capture_output=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass

    def _show_update_details(self, title, text):
        message = QMessageBox(self)
        message.setWindowTitle('AppInstall')
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setText(title)
        message.setDetailedText(text[-12000:])
        if title.startswith('What’s new'):
            message.setInformativeText(text[:2500])
        message.exec()

    def closeEvent(self, event):
        if self.update_operation == 'install':
            event.ignore()
            return
        if self.update_operation == 'check':
            self.update_process.kill()
            self.update_process.waitForFinished(1000)
        super().closeEvent(event)

    def _install_from_url(self):
        dialog = UrlInstallDialog(self)
        dialog.installed.connect(self.refresh)
        dialog.exec()


if __name__ == '__main__':
    app = QApplication(sys.argv[:1])
    app.setDesktopFileName("appinstall")
    ui_style.maybe_dark(app)
    app.setWindowIcon(QIcon.fromTheme('appinstall'))
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

