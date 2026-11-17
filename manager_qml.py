#!/usr/bin/env python3
"""QML prototype of the My Applications manager screen.

Prototype only — the widgets manager window (manager.py ManagerWindow) stays
the shipping UI until this design is accepted. This entry point rebuilds the
same screen in Qt Quick on top of the existing backend: every action routes
through the normal manager entry points (load_inventory, open_app,
uninstall_app, reinstall_app, update_app, settings, BatchQueueDialog,
UninstallDialog, AppDetailsDialog, HealthDialog), never through a copy.

Run with:  python3 manager_qml.py
"""
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from qt_compat import QtCore, QtGui, QtWidgets

try:
    from PySide6 import QtQml, QtQuick
except ModuleNotFoundError as error:
    if error.name != "PySide6":
        raise
    from PyQt6 import QtQml, QtQuick  # type: ignore
    # Keep the QML declarations compatible with the distro's PyQt6 binding.
    QtCore.Signal = QtCore.pyqtSignal
    QtCore.Slot = QtCore.pyqtSlot
    QtCore.Property = QtCore.pyqtProperty

import manager
import settings
import flathub_catalog
import repository_catalog
import update_engine

QML_DIR = Path(__file__).resolve().with_name('manager_ui')


def find_update_helper():
    """Locate the AppInstall self-updater for this kind of checkout.

    Native packages ship appinstall-installer next to this module; a source
    checkout only has install.sh (same --desktop-check/--desktop-update
    protocol). PATH is the last resort. Returns the candidate path even when
    missing so callers can treat 'no helper' as 'update UI unavailable'.
    """
    here = Path(__file__).resolve().parent
    adjacent = here / 'appinstall-installer'
    if adjacent.is_file():
        return adjacent
    local = here / 'install.sh'
    if local.is_file():
        return local
    found = shutil.which('appinstall-installer')
    if found:
        return Path(found)
    return adjacent


RELEASE_NOTES_PATH = Path('/usr/share/appinstall/RELEASE_NOTES.md')


def release_notes(tag):
    """What's new text for a freshly installed tag: the packaged release
    notes when present, otherwise the GitHub release URL."""
    try:
        return RELEASE_NOTES_PATH.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        return 'https://github.com/aboodmohd/-AppInstall/releases/tag/' + tag



# ── status presentation ────────────────────────────────────────────────────

STATUS_LABELS = {
    manager.STATUS_INSTALLED: 'Installed',
    manager.STATUS_NEEDS_REPAIR: 'Needs repair',
    manager.STATUS_MISSING: 'Files missing',
    manager.STATUS_STALE: 'Stale record',
    manager.STATUS_CORRUPTED: 'Corrupted',
    manager.STATUS_UNKNOWN: 'Unknown',
}

STATUS_TONES = {
    manager.STATUS_INSTALLED: 'success',
    manager.STATUS_NEEDS_REPAIR: 'warning',
    manager.STATUS_MISSING: 'danger',
    manager.STATUS_STALE: 'neutral',
    manager.STATUS_CORRUPTED: 'danger',
    manager.STATUS_UNKNOWN: 'neutral',
}


class AppModel(QtCore.QAbstractListModel):
    """Installed apps for the QML list, reusing manager's record shape."""

    KeyRole = QtCore.Qt.ItemDataRole.UserRole + 1
    NameRole = QtCore.Qt.ItemDataRole.UserRole + 2
    FormatRole = QtCore.Qt.ItemDataRole.UserRole + 3
    FormatLabelRole = QtCore.Qt.ItemDataRole.UserRole + 4
    VersionRole = QtCore.Qt.ItemDataRole.UserRole + 5
    ContainerRole = QtCore.Qt.ItemDataRole.UserRole + 6
    SizeTextRole = QtCore.Qt.ItemDataRole.UserRole + 7
    StatusRole = QtCore.Qt.ItemDataRole.UserRole + 8
    StatusLabelRole = QtCore.Qt.ItemDataRole.UserRole + 9
    StatusToneRole = QtCore.Qt.ItemDataRole.UserRole + 10
    ProblemsRole = QtCore.Qt.ItemDataRole.UserRole + 11
    PinnedRole = QtCore.Qt.ItemDataRole.UserRole + 12
    IconUrlRole = QtCore.Qt.ItemDataRole.UserRole + 13
    InitialRole = QtCore.Qt.ItemDataRole.UserRole + 14
    CanOpenRole = QtCore.Qt.ItemDataRole.UserRole + 15
    CanUninstallRole = QtCore.Qt.ItemDataRole.UserRole + 16
    CanUpdateRole = QtCore.Qt.ItemDataRole.UserRole + 17
    IsContainerRole = QtCore.Qt.ItemDataRole.UserRole + 18
    LastLaunchRole = QtCore.Qt.ItemDataRole.UserRole + 19
    DescriptionRole = QtCore.Qt.ItemDataRole.UserRole + 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._inventory = []
        self._rows = []
        self._favorites = set(settings.read().get('favorites', []))
        self._search = ''
        self._format = None
        self._status = None
        self._sort_key = 'name-asc'

    countChanged = QtCore.Signal()

    @QtCore.Property(int, notify=countChanged)
    def count(self):
        return len(self._rows)

    def roleNames(self):
        return {
            self.KeyRole: b'key',
            self.NameRole: b'name',
            self.FormatRole: b'format',
            self.FormatLabelRole: b'formatLabel',
            self.VersionRole: b'version',
            self.ContainerRole: b'container',
            self.SizeTextRole: b'sizeText',
            self.StatusRole: b'status',
            self.StatusLabelRole: b'statusLabel',
            self.StatusToneRole: b'statusTone',
            self.ProblemsRole: b'problems',
            self.PinnedRole: b'pinned',
            self.IconUrlRole: b'iconUrl',
            self.InitialRole: b'initial',
            self.CanOpenRole: b'canOpen',
            self.CanUninstallRole: b'canUninstall',
            self.CanUpdateRole: b'canUpdate',
            self.IsContainerRole: b'isContainer',
            self.LastLaunchRole: b'lastLaunch',
            self.DescriptionRole: b'description',
        }

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        row = self._rows[index.row()] if index.isValid() else None
        if row is None:
            return None
        app, pinned = row
        if role == self.KeyRole:
            return app['key']
        if role == self.NameRole:
            return app['name']
        if role == self.FormatRole:
            return app['format']
        if role == self.FormatLabelRole:
            return manager.FORMAT_LABELS.get(app['format'], app['format'])
        if role == self.VersionRole:
            return app['version'] or ''
        if role == self.ContainerRole:
            return app.get('container') or ''
        if role == self.SizeTextRole:
            return manager.format_size(manager.app_disk_usage(app))
        if role == self.StatusRole:
            return app['status']
        if role == self.StatusLabelRole:
            return STATUS_LABELS.get(app['status'], app['status'])
        if role == self.StatusToneRole:
            return STATUS_TONES.get(app['status'], 'neutral')
        if role == self.ProblemsRole:
            return '; '.join(app.get('problems') or [])
        if role == self.PinnedRole:
            return pinned
        if role == self.IconUrlRole:
            icon_path = app.get('icon') or ''
            if not icon_path:
                return ''
            # Only use absolute file paths that exist on disk. Theme icon
            # names (e.g. "com.stremio.Stremio") are not file URLs -- leave
            # them empty so the QML letter-avatar fallback is used instead.
            p = Path(icon_path)
            if p.is_absolute() and p.is_file():
                return 'file://' + str(p)
            return ''
        if role == self.InitialRole:
            name = app['name'] or '?'
            return name[0].upper()
        if role == self.CanOpenRole:
            return app['format'] in ('appimage', 'flatpak', 'deb', 'rpm') \
                and manager._launcher_exists(app, app['key'])
        if role == self.CanUninstallRole:
            return manager.can_uninstall(app)
        if role == self.CanUpdateRole:
            return manager.can_update(app)
        if role == self.IsContainerRole:
            return app['format'] in ('deb', 'rpm')
        if role == self.LastLaunchRole:
            last = app.get('last_launch') or {}
            return str(last.get('started') or '')
        if role == self.DescriptionRole:
            return app.get('description') or ''
        return None

    def app_record(self, key):
        """The underlying app dict for bridge actions (normal record shape)."""
        for app, _pinned in self._rows:
            if app['key'] == key:
                return app
        for app in self._inventory:
            if app['key'] == key:
                return app
        raise KeyError(key)

    def refresh_inventory(self, inventory):
        self._inventory = list(inventory)
        self.refilter()

    def set_favorites(self, favorites):
        self._favorites = set(favorites)
        self.refilter()

    # ── filter/sort slots (called from QML controls) ─────────────────────

    @QtCore.Slot(str)
    def setSearch(self, text):
        self._search = text.strip().casefold()
        self.refilter()

    @QtCore.Slot(str)
    def setFormatFilter(self, fmt):
        self._format = None if fmt == 'all' else fmt
        self.refilter()

    @QtCore.Slot(str)
    def setStatusFilter(self, status):
        self._status = None if status == 'all' else status
        self.refilter()

    @QtCore.Slot(str)
    def setSort(self, sort_key):
        self._sort_key = sort_key or 'name-asc'
        self.refilter()

    def refilter(self):
        self.beginResetModel()
        text = self._search
        result = []
        for app in self._inventory:
            if self._format is not None and app['format'] != self._format:
                continue
            if self._status is not None and app['status'] != self._status:
                continue
            if text and text not in app['name'].casefold() and text not in app['key'].casefold():
                continue
            result.append(app)
        self._rows = [(app, app['key'] in self._favorites)
                      for app in self._sorted(result)]
        self.endResetModel()
        self.countChanged.emit()

    def _sorted(self, apps):
        """Same ordering semantics as ManagerWindow._sorted: favorites first."""
        def base(app):
            return app['name'].casefold()
        if self._sort_key == 'name-desc':
            ordered = sorted(apps, key=base, reverse=True)
        elif self._sort_key == 'recent':
            def stamp(app):
                last = app.get('last_launch') or {}
                return last.get('started') or ''
            ordered = sorted(apps, key=stamp, reverse=True)
        elif self._sort_key == 'size':
            def bulk(app):
                size = manager.app_disk_usage(app)
                return (size is None, -(size or 0))
            ordered = sorted(apps, key=bulk)
        else:
            ordered = sorted(apps, key=base)
        pinned = [app for app in ordered if app['key'] in self._favorites]
        rest = [app for app in ordered if app['key'] not in self._favorites]
        return pinned + rest


class CatalogModel(QtCore.QAbstractListModel):
    """Flathub search results, separate from the installed-app inventory."""

    AppIdRole = QtCore.Qt.ItemDataRole.UserRole + 1
    NameRole = QtCore.Qt.ItemDataRole.UserRole + 2
    SummaryRole = QtCore.Qt.ItemDataRole.UserRole + 3
    IconRole = QtCore.Qt.ItemDataRole.UserRole + 4
    CategoryRole = QtCore.Qt.ItemDataRole.UserRole + 5
    ManagedRole = QtCore.Qt.ItemDataRole.UserRole + 6
    SourceRole = QtCore.Qt.ItemDataRole.UserRole + 7
    InstallUrlRole = QtCore.Qt.ItemDataRole.UserRole + 8
    countChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._managed = set()
        self._managed_packages = set()

    @QtCore.Property(int, notify=countChanged)
    def count(self):
        return len(self._rows)

    def roleNames(self):
        return {
            self.AppIdRole: b'appId',
            self.NameRole: b'name',
            self.SummaryRole: b'summary',
            self.IconRole: b'iconUrl',
            self.CategoryRole: b'category',
            self.ManagedRole: b'managed',
            self.SourceRole: b'source',
            self.InstallUrlRole: b'installUrl',
        }

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        row = self._rows[index.row()]
        return {
            self.AppIdRole: row['appId'],
            self.NameRole: row['name'],
            self.SummaryRole: row['summary'],
            self.IconRole: row['iconUrl'],
            self.CategoryRole: row['category'],
            self.ManagedRole: (
                row['appId'] in self._managed
                if row.get('source', 'Flatpak') == 'Flatpak'
                else (row.get('source'), row['appId']) in self._managed_packages
            ),
            self.SourceRole: row.get('source', 'Flatpak'),
            self.InstallUrlRole: row.get('installUrl', ''),
        }.get(role)

    def replace(self, rows):
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()
        self.countChanged.emit()

    def append(self, rows):
        if not rows:
            return
        start = len(self._rows)
        self.beginInsertRows(QtCore.QModelIndex(), start, start + len(rows) - 1)
        self._rows.extend(rows)
        self.endInsertRows()
        self.countChanged.emit()

    def apply_icons(self, icons):
        """Update visible card artwork without resetting positions or selection."""
        for index, row in enumerate(self._rows):
            icon = icons.get(row['appId'])
            if icon and icon != row.get('iconUrl', ''):
                row['iconUrl'] = icon
                item = self.index(index, 0)
                self.dataChanged.emit(item, item, [self.IconRole])

    def set_managed(self, inventory):
        managed = {app['key'].split(':', 1)[-1] for app in inventory
                   if app['format'] == 'flatpak' and app['key'].startswith('flatpak:')}
        managed_packages = {
            (app['format'].upper(), app['key'].split(':', 1)[-1])
            for app in inventory
            if app['format'] in ('deb', 'rpm')
            and app['key'].startswith(app['format'] + ':')
        }
        if managed != self._managed or managed_packages != self._managed_packages:
            self._managed = managed
            self._managed_packages = managed_packages
            if self._rows:
                self.dataChanged.emit(self.index(0, 0),
                                      self.index(len(self._rows) - 1, 0),
                                      [self.ManagedRole])


class CatalogWorker(QtCore.QThread):
    """Network requests run exclusively off the Qt/UI thread."""

    ready = QtCore.Signal(str, list)
    iconsReady = QtCore.Signal(str, str, dict)
    failed = QtCore.Signal(str, str)

    setup_required = QtCore.Signal(str)

    def __init__(self, query, source="Flatpak", parent=None, initialize=False):
        super().__init__(parent)
        self.query = query
        self.source = source
        self.initializing = initialize

    def run(self):
        try:
            if self.source in ("DEB", "RPM"):
                kind = repository_catalog.kind_for(self.source)
                if self.initializing:
                    repository_catalog.prepare(kind)
                if not repository_catalog.ready(kind):
                    raise repository_catalog.CatalogNotReady("Repository not prepared.")
                results = (repository_catalog.search(kind, self.query)
                           if self.query else repository_catalog.browse(kind))
            elif self.source == "AppImage":
                results = (flathub_catalog.appimage_search(self.query)
                           if self.query else flathub_catalog.appimage_browse())
            else:
                results = (flathub_catalog.search(self.query)
                           if self.query else flathub_catalog.popular())
            self.ready.emit(self.query, results)
            # Blank-query native browse returns packages from the official
            # repository, just as a typed search does.
            # Show package cards immediately. Official AppStream icons resolve
            # later on this worker, never holding up the main QML/UI thread.
            if self.source in ("DEB", "RPM") and results:
                icons = repository_catalog.icons_for_results(results)
                if icons:
                    self.iconsReady.emit(self.query, self.source, icons)
        except repository_catalog.CatalogNotReady:
            self.setup_required.emit(self.source)
        except (flathub_catalog.CatalogError, ValueError) as error:
            self.failed.emit(self.query, str(error))
        except Exception as error:
            self.failed.emit(self.query, 'Flathub search failed: ' + str(error))


class UpdateModel(QtCore.QAbstractListModel):
    """Result rows for the separate installed-app Updates page."""

    KeyRole = QtCore.Qt.ItemDataRole.UserRole + 1
    NameRole = QtCore.Qt.ItemDataRole.UserRole + 2
    FormatRole = QtCore.Qt.ItemDataRole.UserRole + 3
    StateRole = QtCore.Qt.ItemDataRole.UserRole + 4
    CurrentRole = QtCore.Qt.ItemDataRole.UserRole + 5
    AvailableRole = QtCore.Qt.ItemDataRole.UserRole + 6
    OriginRole = QtCore.Qt.ItemDataRole.UserRole + 7
    ReasonRole = QtCore.Qt.ItemDataRole.UserRole + 8
    ActionableRole = QtCore.Qt.ItemDataRole.UserRole + 9
    ReferenceRole = QtCore.Qt.ItemDataRole.UserRole + 10
    countChanged = QtCore.Signal()
    availableCountChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all = []
        self._rows = []
        self._filter = "all"

    @QtCore.Property(int, notify=countChanged)
    def count(self):
        return len(self._rows)

    @QtCore.Property(int, notify=availableCountChanged)
    def availableCount(self):
        return sum(row["candidate"].state == update_engine.AVAILABLE for row in self._all)

    def roleNames(self):
        return {
            self.KeyRole: b"key", self.NameRole: b"name",
            self.FormatRole: b"format", self.StateRole: b"updateState",
            self.CurrentRole: b"currentVersion", self.AvailableRole: b"availableVersion",
            self.OriginRole: b"origin", self.ReasonRole: b"reason",
            self.ActionableRole: b"actionable", self.ReferenceRole: b"reference",
        }

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        candidate = row["candidate"]
        app = row["app"]
        return {
            self.KeyRole: candidate.key,
            self.NameRole: str(app.get("name") or candidate.key),
            self.FormatRole: candidate.format.upper() if candidate.format != "appimage" else "AppImage",
            self.StateRole: candidate.state,
            self.CurrentRole: candidate.installed_version or "Unknown",
            self.AvailableRole: candidate.available_version or "—",
            self.OriginRole: candidate.source or "Local file / unknown source",
            self.ReasonRole: candidate.reason,
            self.ActionableRole: bool(
                candidate.format == "flatpak"
                and candidate.state == update_engine.AVAILABLE
                and candidate.reference
                and candidate.available_revision),
            self.ReferenceRole: candidate.reference,
        }.get(role)

    def replace_results(self, apps, candidates):
        by_key = {app.get("key"): app for app in apps}
        self._all = [
            {"app": by_key[c.key], "candidate": c}
            for c in candidates if c.key in by_key
        ]
        self._refilter()

    @QtCore.Slot(str)
    def setFilter(self, state):
        if state not in ("all", "available", "up-to-date",
                         "manual-required", "unsupported", "error"):
            return
        self._filter = state
        self._refilter()

    def _refilter(self):
        self.beginResetModel()
        self._rows = [
            row for row in self._all
            if self._filter == "all" or row["candidate"].state == self._filter
        ]
        self.endResetModel()
        self.countChanged.emit()
        self.availableCountChanged.emit()

    def candidate(self, key):
        for row in self._all:
            if row["candidate"].key == key:
                return row["candidate"]
        return None


class UpdateScanWorker(QtCore.QThread):
    """Runs read-only provider checks off the GUI thread, never installs."""

    ready = QtCore.Signal(list)
    failed = QtCore.Signal(str)

    def __init__(self, inventory, *, force=False, parent=None):
        super().__init__(parent)
        self._inventory = list(inventory)
        self._force = force

    def run(self):
        try:
            results = manager.inspect_application_updates(
                self._inventory, force=self._force,
                cancelled=self.isInterruptionRequested)
            if not self.isInterruptionRequested():
                self.ready.emit(results)
        except Exception as error:
            if not self.isInterruptionRequested():
                self.failed.emit(str(error))


class Bridge(QtCore.QObject):
    """Actions and state the QML screen reads; every action calls the
    existing manager backend through its normal entry point."""

    countChanged = QtCore.Signal(int)
    loadingChanged = QtCore.Signal(bool)
    statusTextChanged = QtCore.Signal(str)
    themeChanged = QtCore.Signal()
    preferencesChanged = QtCore.Signal()
    updateStatusChanged = QtCore.Signal(str)
    updateActionVisibleChanged = QtCore.Signal(bool)
    catalogLoadingChanged = QtCore.Signal(bool)
    catalogStatusChanged = QtCore.Signal(str)
    catalogResultsChanged = QtCore.Signal()
    appUpdateBusyChanged = QtCore.Signal(bool)
    appUpdateStatusChanged = QtCore.Signal(str)
    appUpdateProgressChanged = QtCore.Signal(str)
    appUpdateRunningChanged = QtCore.Signal(bool)

    @QtCore.Property(bool, notify=updateActionVisibleChanged)
    def actionVisible(self):
        return self._update_action_visible

    darkChanged = QtCore.Signal(bool)
    updateTagChanged = QtCore.Signal(str)

    def __init__(self, anchor, parent=None):
        super().__init__(parent)
        self.anchor = anchor  # hidden QWidget used to parent the existing dialogs
        self._model = AppModel(self)
        self._catalog = CatalogModel(self)
        self._catalog_loading = False
        self._catalog_setup_required = False
        self._catalog_initializing = False
        self._catalog_status = 'Search Flathub or browse popular applications.'
        self._catalog_source = 'Flatpak'
        self._catalog_query = ''
        self._catalog_all = []
        self._catalog_worker = None
        self._catalog_pending = None
        self._updates = UpdateModel(self)
        self._app_update_status = 'Select Check now to inspect managed applications.'
        self._app_update_progress = ''
        self._app_update_worker = None
        self._app_update_snapshot = []
        self._app_update_busy = False
        self._flatpak_preflight_worker = None
        self._flatpak_pending_key = None
        self._flatpak_pending_candidate = None
        self._flatpak_active_key = ''
        self._flatpak_cancelled = False
        self._flatpak_process = QtCore.QProcess(self)
        self._flatpak_process.setProcessChannelMode(
            QtCore.QProcess.ProcessChannelMode.MergedChannels)
        self._flatpak_process.readyReadStandardOutput.connect(self._flatpak_progress_read)
        self._flatpak_process.finished.connect(self._flatpak_finished)
        # APPINSTALL_UI_DARK=1 forces dark mode for evidence capture,
        # overriding settings and system preference.
        env_dark = os.environ.get('APPINSTALL_UI_DARK')
        self._dark = env_dark == '1' if env_dark is not None else False
        self._loading = False
        self._status_text = 'Loading…'
        self._reduced_motion = os.environ.get('APPINSTALL_REDUCED_MOTION') == '1'
        self._batch_dialog = None
        self._update_tag = ''
        self._update_status = ''
        self._update_action_visible = True
        self._update_operation = ''
        self._update_process = QtCore.QProcess(self)
        self._update_process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        self._update_process.finished.connect(self._update_finished)
        self._update_helper = find_update_helper()
        self._update_manual = False
        # Same cadence as the widgets window: a check ~1.2s after launch,
        # then every 4h. The 12h TTL gate inside checkUpdates keeps the real
        # network cadence at one automatic check per 12 hours.
        if self._update_helper.is_file() and \
                os.environ.get('APPINSTALL_DISABLE_UPDATE_TIMER') != '1':
            QtCore.QTimer.singleShot(1200, lambda: self.checkUpdates(False))
            self._update_timer = QtCore.QTimer(self)
            self._update_timer.setInterval(4 * 60 * 60 * 1000)
            self._update_timer.timeout.connect(lambda: self.checkUpdates(False))
            self._update_timer.start()

    # ── exposed properties ───────────────────────────────────────────────

    @QtCore.Property(bool, notify=darkChanged)
    def dark(self):
        return self._dark

    @QtCore.Property(bool, notify=loadingChanged)
    def loading(self):
        return self._loading

    @QtCore.Property(str, notify=statusTextChanged)
    def statusText(self):
        return self._status_text

    @QtCore.Property(str, notify=themeChanged)
    def themeChoice(self):
        return settings.read().get('theme', 'auto')

    @QtCore.Property(bool, notify=preferencesChanged)
    def notificationsEnabled(self):
        return settings.read().get('notifications', False)

    @QtCore.Property(str, notify=preferencesChanged)
    def uninstallMode(self):
        return settings.read().get('uninstall_mode', 'ask')

    @QtCore.Slot(bool)
    def setNotificationsEnabled(self, enabled):
        try:
            settings.update('notifications', bool(enabled))
            self.preferencesChanged.emit()
        except OSError as error:
            self._set_status('Unable to save notifications preference: ' + str(error))

    @QtCore.Slot(str)
    def setUninstallMode(self, mode):
        if mode not in settings.UNINSTALL_MODES:
            self._set_status('Invalid uninstall preference.')
            return
        try:
            settings.update('uninstall_mode', mode)
            self.preferencesChanged.emit()
        except OSError as error:
            self._set_status('Unable to save uninstall preference: ' + str(error))

    @QtCore.Property(bool, constant=True)
    def reducedMotion(self):
        return self._reduced_motion

    @QtCore.Property(QtCore.QObject, constant=True)
    def model(self):
        return self._model

    @QtCore.Property(QtCore.QObject, constant=True)
    def catalogModel(self):
        return self._catalog

    @QtCore.Property(bool, notify=catalogLoadingChanged)
    def catalogLoading(self):
        return self._catalog_loading

    @QtCore.Property(str, notify=catalogStatusChanged)
    def catalogStatus(self):
        return self._catalog_status

    @QtCore.Property(bool, notify=catalogResultsChanged)
    def catalogSetupRequired(self):
        return self._catalog_setup_required

    @QtCore.Property(bool, notify=catalogResultsChanged)
    def catalogHasMore(self):
        return self._catalog.count < len(self._catalog_all)

    def _set_catalog_status(self, message):
        self._catalog_status = str(message)
        self.catalogStatusChanged.emit(self._catalog_status)

    @QtCore.Property(str, notify=updateStatusChanged)
    def updateStatus(self):
        return self._update_status

    @QtCore.Property(str, notify=updateTagChanged)
    def updateTag(self):
        return self._update_tag

    # ── Managed application updates (distinct from AppInstall self-upgrade) ──

    @QtCore.Property(QtCore.QObject, constant=True)
    def updatesModel(self):
        return self._updates

    @QtCore.Property(bool, notify=appUpdateBusyChanged)
    def appUpdatesBusy(self):
        return self._app_update_busy

    @QtCore.Property(str, notify=appUpdateStatusChanged)
    def appUpdatesStatus(self):
        return self._app_update_status

    @QtCore.Property(str, notify=appUpdateProgressChanged)
    def appUpdateProgress(self):
        return self._app_update_progress

    @QtCore.Property(bool, notify=appUpdateRunningChanged)
    def appUpdateRunning(self):
        return self._flatpak_process.state() != QtCore.QProcess.ProcessState.NotRunning

    def _set_app_update_status(self, message):
        self._app_update_status = str(message)[:1000]
        self.appUpdateStatusChanged.emit(self._app_update_status)

    def _set_app_update_busy(self, value):
        self._app_update_busy = bool(value)
        self.appUpdateBusyChanged.emit(self._app_update_busy)

    @QtCore.Slot()
    @QtCore.Slot(bool)
    def checkApplicationUpdates(self, force=True):
        """Provider reads only. Never creates containers or installs anything."""
        if (self._app_update_busy or self._flatpak_preflight_worker is not None
                or self.appUpdateRunning):
            return
        self._app_update_snapshot = list(self._model._inventory)
        self._app_update_progress = ''
        self.appUpdateProgressChanged.emit('')
        if not self._app_update_snapshot:
            self._updates.replace_results([], [])
            self._set_app_update_status('No AppInstall-managed applications found.')
            return
        self._set_app_update_busy(True)
        self._set_app_update_status('Checking application updates (read-only)…')
        worker = UpdateScanWorker(self._app_update_snapshot, force=bool(force), parent=self)
        self._app_update_worker = worker
        worker.ready.connect(self._app_updates_ready)
        worker.failed.connect(self._app_updates_failed)
        worker.finished.connect(self._app_updates_worker_finished)
        worker.start()

    @QtCore.Slot()
    def cancelApplicationUpdateCheck(self):
        worker = self._app_update_worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            self._set_app_update_status('Cancelling update check…')

    def _app_updates_ready(self, candidates):
        self._updates.replace_results(self._app_update_snapshot, candidates)
        available = self._updates.availableCount
        self._set_app_update_status(
            f'{available} app update(s) found across {len(candidates)} managed applications. '
            'Updates do not run automatically.')

    def _app_updates_failed(self, error):
        self._set_app_update_status('Update check failed: ' + str(error))

    def _app_updates_worker_finished(self):
        worker = self._app_update_worker
        if worker is not None and worker.isInterruptionRequested():
            self._set_app_update_status('Update check cancelled; no packages changed.')
        self._app_update_worker = None
        self._set_app_update_busy(False)

    @QtCore.Slot(str)
    def requestFlatpakUpdate(self, key):
        """Revalidate a scanned, explicit user-scope Flatpak before approval."""
        if (self._app_update_busy or self._flatpak_preflight_worker is not None
                or self.appUpdateRunning):
            return
        candidate = self._updates.candidate(key)
        if not candidate or candidate.state != update_engine.AVAILABLE \
                or candidate.format != 'flatpak':
            self._set_app_update_status('No verified Flatpak update is selected.')
            return
        if not (update_engine.REF_RE.fullmatch(candidate.reference)
                and update_engine.COMMIT_RE.fullmatch(candidate.available_revision)
                and update_engine.COMMIT_RE.fullmatch(candidate.installed_revision)):
            self._set_app_update_status('Update reference or revision is invalid. Check again.')
            return
        try:
            app = self._model.app_record(key)
        except KeyError:
            self._set_app_update_status('Application is no longer managed. Refresh the list.')
            return
        self._flatpak_pending_key = key
        self._flatpak_pending_candidate = candidate
        self._set_app_update_busy(True)
        self._set_app_update_status('Revalidating the selected Flatpak before confirmation…')
        worker = UpdateScanWorker([app], force=True, parent=self)
        self._flatpak_preflight_worker = worker
        worker.ready.connect(self._flatpak_preflight_ready)
        worker.failed.connect(self._flatpak_preflight_failed)
        worker.finished.connect(self._flatpak_preflight_finished)
        worker.start()

    def _flatpak_preflight_ready(self, results):
        old = self._flatpak_pending_candidate
        key = self._flatpak_pending_key
        fresh = results[0] if len(results) == 1 else None
        if (fresh is None or old is None or key is None
                or fresh.key != key or fresh.state != update_engine.AVAILABLE
                or fresh.reference != old.reference or fresh.source != old.source
                or fresh.installed_revision != old.installed_revision
                or not update_engine.COMMIT_RE.fullmatch(fresh.available_revision)
                or not update_engine.REF_RE.fullmatch(fresh.reference)):
            self._set_app_update_status(
                'Available Flatpak update changed or was not verified. Check again.')
            return
        if fresh.available_revision != old.available_revision:
            self._set_app_update_status(
                'Flatpak upstream revision changed. Check again before updating.')
            return
        prompt = (
            'Update this AppInstall-managed Flatpak?\n\n'
            'Application: ' + key + '\n'
            'Source: ' + fresh.source + '\n'
            'Exact ref: ' + fresh.reference + '\n'
            'Installed commit: ' + fresh.installed_revision[:12] + '\n'
            'Target commit: ' + fresh.available_revision[:12] + '\n\n'
            'Only this exact user-scope app ref will be requested. '
            'The --no-deps and --no-related options limit ancillary work, '
            'but this preview cannot enumerate all Flatpak transaction effects. '
            'No system-wide or all-app update will be requested.\n\n'
            'Continue?')
        answer = QtWidgets.QMessageBox.question(
            self.anchor, 'Review Flatpak update', prompt,
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No)
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            self._set_app_update_status('Flatpak update declined. No packages changed.')
            return
        self._flatpak_active_key = key
        self._flatpak_cancelled = False
        self._app_update_progress = 'Starting selected Flatpak update…'
        self.appUpdateProgressChanged.emit(self._app_update_progress)
        self._set_app_update_status('Updating ' + key + '…')
        self._flatpak_process.start('flatpak', [
            'update', '--user', '--noninteractive', '--assumeyes',
            '--no-deps', '--no-related',
            '--commit=' + fresh.available_revision, fresh.reference])
        self._flatpak_process.closeWriteChannel()
        self.appUpdateRunningChanged.emit(True)

    def _flatpak_preflight_failed(self, error):
        self._set_app_update_status('Flatpak preflight failed: ' + str(error))

    def _flatpak_preflight_finished(self):
        self._flatpak_preflight_worker = None
        self._flatpak_pending_key = None
        self._flatpak_pending_candidate = None
        self._set_app_update_busy(False)

    def _flatpak_progress_read(self):
        chunk = bytes(self._flatpak_process.readAllStandardOutput()).decode(errors='replace')
        if chunk:
            cleaned = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', chunk)
            self._app_update_progress = (self._app_update_progress + cleaned)[-3200:]
            self.appUpdateProgressChanged.emit(self._app_update_progress)

    @QtCore.Slot()
    def cancelRunningFlatpakUpdate(self):
        if not self.appUpdateRunning:
            return
        reply = QtWidgets.QMessageBox.question(
            self.anchor, 'Interrupt Flatpak update',
            'Stop the running Flatpak command? Its state may be incomplete. '
            'AppInstall will check again after interruption. '
            'No additional packages will be installed automatically.',
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self._flatpak_cancelled = True
            self._flatpak_process.kill()
            self._set_app_update_status('Interrupting Flatpak update; checking state after exit…')

    def _flatpak_finished(self, code, status):
        self._flatpak_progress_read()
        was_cancelled = self._flatpak_cancelled
        key = self._flatpak_active_key
        self._flatpak_active_key = ''
        self._flatpak_cancelled = False
        self.appUpdateRunningChanged.emit(False)
        if was_cancelled:
            self._set_app_update_status(
                'Flatpak operation interrupted. Its final package state is unknown; '
                'a fresh check will follow.')
        elif code != 0 or status != QtCore.QProcess.ExitStatus.NormalExit:
            self._set_app_update_status('Flatpak update failed for ' + key +
                                        '. Read the operation output below.')
        else:
            self._set_app_update_status('Flatpak update command completed for ' + key +
                                        '. Verifying installed versions…')
        # Refresh inventory and update checks only after QProcess termination.
        self.refresh()
        # The inventory loader is asynchronous. A fresh scan via the user-visible
        # Check now button remains available once it finishes.

    # ── inventory ────────────────────────────────────────────────────────

    def _set_status(self, text):
        self._status_text = str(text)
        self.statusTextChanged.emit(self._status_text)

    @QtCore.Slot()
    def refresh(self):
        """Load the inventory on the existing background loader."""
        self._loader = manager.InventoryLoader()
        self._loading = True
        self.loadingChanged.emit(True)
        self._loader.done.connect(self._loaded)
        self._loader.failed.connect(self._load_failed)
        self._loader.start()

    def _loaded(self, inventory):
        self._model.refresh_inventory(inventory)
        self._catalog.set_managed(inventory)
        self._loading = False
        self.loadingChanged.emit(False)
        self._announce_count()

    def _count_text(self):
        count = self._model.rowCount()
        noun = 'application' if count == 1 else 'applications'
        return f'{count} {noun} managed by AppInstall'

    def _announce_count(self):
        self._set_status(self._count_text())
        self.countChanged.emit(self._model.rowCount())

    def _load_failed(self, message):
        self._loading = False
        self.loadingChanged.emit(False)
        self._set_status('Could not load inventory: ' + message)

    # ── Live Discover sources, never coupled to the installed-app inventory ──
    @QtCore.Slot(str)
    @QtCore.Slot(str, str)
    def searchCatalog(self, query, source='Flatpak'):
        """Latest-wins search using a single asynchronous worker."""
        query = str(query).strip()[:90]
        source = source if source in ('Flatpak', 'AppImage', 'DEB', 'RPM') else 'Flatpak'
        was_setup_required = (self._catalog_source == source
                              and self._catalog_setup_required)
        self._catalog_source = source
        self._catalog_query = query
        self._catalog_setup_required = was_setup_required if query and len(query) < 2 else False
        self.catalogResultsChanged.emit()
        if query and len(query) < 2:
            self._catalog_pending = None
            self._catalog_all = []
            self._catalog.replace([])
            self.catalogResultsChanged.emit()
            self._set_catalog_status('Enter at least two characters.')
            return
        self._catalog_pending = (query, source)
        if self._catalog_worker is not None and self._catalog_worker.isRunning():
            return
        self._start_catalog_worker()

    def _start_catalog_worker(self, initialize=False):
        pending = self._catalog_pending
        if pending is None:
            return
        self._catalog_pending = None
        query, source = pending
        self._catalog_loading = True
        self.catalogLoadingChanged.emit(True)
        self._catalog_initializing = initialize
        if initialize:
            self._set_catalog_status('Preparing ' + source + ' repository metadata…')
        else:
            provider = ('AppImageHub' if source == 'AppImage' else
                        'Flathub' if source == 'Flatpak' else
                        'Debian APT' if source == 'DEB' else 'Fedora DNF')
            self._set_catalog_status('Searching ' + provider + '…')
        worker = CatalogWorker(query, source, self, initialize=initialize)
        self._catalog_worker = worker
        worker.ready.connect(self._catalog_ready)
        worker.iconsReady.connect(self._catalog_icons_ready)
        worker.failed.connect(self._catalog_failed)
        worker.setup_required.connect(self._catalog_needs_setup)
        worker.finished.connect(self._catalog_finished)
        worker.start()

    @QtCore.Slot(str)
    @QtCore.Slot(str, str)
    def prepareCatalogSource(self, source, query=''):
        """One-time explicit approval to create/index a persistent rootless container."""
        if source not in ('DEB', 'RPM') or self._catalog_source != source:
            return
        if self._catalog_worker is not None and self._catalog_worker.isRunning():
            return
        name = 'Debian 13' if source == 'DEB' else 'Fedora 44'
        answer = QtWidgets.QMessageBox.question(
            self.anchor, 'Enable ' + source + ' discovery',
            'Prepare the AppInstall-managed ' + name + ' rootless Distrobox container '
            'and refresh its official package index? The first setup may download '
            'a large container image and dependencies. Distrobox shares your home '
            'directory and desktop; it is not a security sandbox. '
            'No application packages will be installed without a later review.')
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._catalog_setup_required = False
        self.catalogResultsChanged.emit()
        query = str(query).strip()[:90]
        self._catalog_query = query if len(query) >= 2 else ''
        self._catalog_pending = (self._catalog_query, source)
        self._start_catalog_worker(initialize=True)

    def _catalog_needs_setup(self, source):
        if source == self._catalog_source and self._catalog_pending is None:
            self._catalog_setup_required = True
            self._catalog_all = []
            self._catalog.replace([])
            self.catalogResultsChanged.emit()
            self._set_catalog_status('Enable the ' + source + ' repository to search available packages.')

    def _catalog_ready(self, query, entries):
        worker = self._catalog_worker
        if worker is None:
            return
        if worker.initializing:
            self._catalog_setup_required = False
            self.catalogResultsChanged.emit()
        if self._catalog_pending is not None or worker.source != self._catalog_source:
            return
        self._catalog_all = list(entries)
        self._catalog.replace(self._catalog_all[:24])
        self.catalogResultsChanged.emit()
        self._announce_catalog_results()

    def _catalog_icons_ready(self, query, source, icons):
        worker = self._catalog_worker
        if (worker is None or self._catalog_pending is not None
                or source != self._catalog_source or worker.source != source
                or worker.query != query):
            return
        for row in self._catalog_all:
            icon = icons.get(row['appId'])
            if icon:
                row['iconUrl'] = icon
        self._catalog.apply_icons(icons)

    def _announce_catalog_results(self):
        total = len(self._catalog_all)
        shown = self._catalog.count
        provider = {'Flatpak': 'Flathub', 'AppImage': 'AppImageHub',
                    'DEB': 'Debian APT', 'RPM': 'Fedora DNF'}[self._catalog_source]
        if not total and self._catalog_source in ('DEB', 'RPM') \
                and not self._catalog_setup_required and not self._catalog_query:
            status = ('No browse results from ' + provider
                      + '. Search by package name or refresh the repository.')
        elif not total:
            status = 'No applications matched this search on ' + provider + '.'
        elif shown < total:
            status = f'Showing {shown} of {total} applications on {provider}.'
        else:
            status = (f'{total} application found on {provider}.'
                      if total == 1 else f'{total} applications found on {provider}.')
        self._set_catalog_status(status)

    @QtCore.Slot()
    def loadMoreCatalog(self):
        if self._catalog_loading or not self.catalogHasMore:
            return
        n = self._catalog.count
        self._catalog.append(self._catalog_all[n:n + 24])
        self.catalogResultsChanged.emit()
        self._announce_catalog_results()

    def _catalog_failed(self, query, message):
        if self._catalog_pending is None and self._catalog_worker is not None and \
                self._catalog_worker.source == self._catalog_source:
            if self._catalog_worker.initializing:
                self._catalog_setup_required = True
            self._catalog_all = []
            self._catalog.replace([])
            self.catalogResultsChanged.emit()
            self._set_catalog_status(message)

    def _catalog_finished(self):
        self._catalog_worker = None
        self._catalog_initializing = False
        if self._catalog_pending is not None:
            self._start_catalog_worker()
        else:
            self._catalog_loading = False
            self.catalogLoadingChanged.emit(False)

    @QtCore.Slot(str)
    def installFromFlathub(self, app_id):
        """Open the existing URL confirmation dialog, never install silently."""
        try:
            url = flathub_catalog.flathub_ref_url(app_id)
        except ValueError:
            self._set_catalog_status('Invalid Flathub application ID.')
            return
        if app_id in self._catalog._managed:
            self._set_catalog_status('This app is already managed by AppInstall.')
            return
        dialog = manager.UrlInstallDialog(self.anchor)
        dialog.url_edit.setText(url)
        dialog.installed.connect(self.refresh)
        dialog.exec()

    @QtCore.Slot(str, str)
    def installCatalogEntry(self, app_id, source):
        """Never install from a browsing-page URL or arbitrary QML input."""
        if source == 'Flatpak':
            if any(row['appId'] == app_id for row in self._catalog_all):
                self.installFromFlathub(app_id)
            return
        if source in ('DEB', 'RPM'):
            if self._catalog_source != source or not any(
                    row['appId'] == app_id and row.get('source') == source
                    for row in self._catalog_all):
                return
            if (source, app_id) in self._catalog._managed_packages:
                self._set_catalog_status('This package is already managed by AppInstall.')
                return
            try:
                repository_catalog.validate_name(app_id)
            except ValueError:
                self._set_catalog_status('Invalid repository package name.')
                return
            import container_ui
            workflow = container_ui.Workflow(
                ['--repo', repository_catalog.kind_for(source), app_id])
            workflow.exec()
            if workflow.batch_result == 0:
                self.refresh()
            return
        if source != 'AppImage' or self._catalog_source != 'AppImage':
            return
        row = next((row for row in self._catalog_all
                    if row['appId'] == app_id and row.get('source') == 'AppImage'), None)
        if row is None:
            return
        url = row.get('installUrl', '')
        if url and url == flathub_catalog._appimage_download(
                {'links': [{'type': 'Download', 'url': url}]}):
            dialog = manager.UrlInstallDialog(self.anchor)
            dialog.url_edit.setText(url)
            dialog.installed.connect(self.refresh)
            dialog.exec()
        else:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(row['sourceUrl']))

    @QtCore.Slot(str, str)
    def openOfficialCatalog(self, source, query):
        """Open official directories; no unverified package-name installation."""
        search = urllib.parse.quote(str(query).strip()[:90], safe='')
        if source == 'DEB':
            url = ('https://packages.debian.org/search?keywords=' + search
                   + '&searchon=names&suite=trixie&section=all')
        elif source == 'RPM':
            url = 'https://packages.fedoraproject.org/?q=' + search
        else:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def shutdownCatalog(self):
        """Drain read-only catalog searches before QApplication tears down QThreads."""
        if self._catalog_worker is not None and self._catalog_worker.isRunning():
            self._catalog_pending = None
            self._catalog_worker.requestInterruption()
            self._catalog_worker.wait(18000)

    # ── theme ────────────────────────────────────────────────────────────

    @QtCore.Slot(str)
    def setTheme(self, theme):
        try:
            settings.update('theme', theme)
        except OSError:
            pass
        self.applyTheme()

    def applyTheme(self):
        # APPINSTALL_UI_DARK=1 forces dark mode for evidence capture,
        # overriding settings and system preference.
        if os.environ.get('APPINSTALL_UI_DARK') == '1':
            self._dark = True
        else:
            theme = settings.read().get('theme', 'auto')
            hints = QtGui.QGuiApplication.styleHints()
            if hasattr(hints, 'colorScheme'):
                system_dark = hints.colorScheme() == QtCore.Qt.ColorScheme.Dark
            else:
                # Qt 6.4 (Ubuntu 24.04) predates QStyleHints.colorScheme.
                palette = QtGui.QGuiApplication.palette()
                system_dark = palette.color(QtGui.QPalette.ColorRole.Window).lightness() < 128
            self._dark = (theme == 'dark') or (theme == 'auto' and system_dark)
        self.darkChanged.emit(self._dark)
        self.themeChanged.emit()

    # ── actions: every one routes through the normal entry point ────────

    @QtCore.Slot(str)
    def openApp(self, key):
        """Same handler as the widgets window: launch, report only failures."""
        app = self._model.app_record(key)
        try:
            manager.open_app(app)
        except Exception as error:
            self._set_status('Could not launch ' + app['name'] + ': ' + str(error))

    @QtCore.Slot(str)
    def showDetails(self, key):
        from manager import AppDetailsDialog
        AppDetailsDialog(self._model.app_record(key), self.anchor).open()

    @QtCore.Slot(str)
    def togglePin(self, key):
        favorites = set(settings.read().get('favorites', []))
        favorites.symmetric_difference_update({key})
        try:
            settings.update('favorites', sorted(favorites))
        except OSError:
            pass
        self._model.set_favorites(favorites)
        self._announce_count()

    @QtCore.Slot(str)
    def reinstallApp(self, key):
        self._guard(manager.reinstall_app, key, 'Reinstall failed', refresh=True)

    @QtCore.Slot(str)
    def updateApp(self, key):
        app = self._model.app_record(key)
        if not manager.can_update(app):
            self._set_status(
                'Automatic updates are not supported for this application.')
            return
        self._guard(manager.update_app, key, 'Update failed', refresh=True)

    @QtCore.Slot(str)
    def uninstallApp(self, key):
        """Open the existing UninstallDialog; only its selection is passed on."""
        app = self._model.app_record(key)
        if not manager.can_uninstall(app):
            self._set_status(
                'Uninstall is not supported for ' + app['format'] + ' applications.')
            return
        from manager import UninstallDialog
        dialog = UninstallDialog(app, manager.uninstall_cleanup_items(app), self.anchor)
        dialog.accepted.connect(
            lambda: self._uninstall_confirmed(app, dialog.selected_paths()))
        dialog.open()

    def _uninstall_confirmed(self, app, cleanup):
        self._guard(lambda: manager.uninstall_app(app, cleanup=set(cleanup)),
                    None, 'Uninstall failed', refresh=True)

    @QtCore.Slot(str)
    def showLogs(self, key):
        app = self._model.app_record(key)
        last = app.get('last_launch') or {}
        if not last.get('log'):
            self._set_status('No launch log is available for ' + app['name'] + '.')
            return
        manager._show_log(last['log'], self.anchor)

    @QtCore.Slot(str)
    def repairApp(self, key):
        self._guard(manager.repair_launcher, key, 'Repair failed', refresh=True)

    @QtCore.Slot(str)
    def openDiagnostics(self, key):
        # Same handler as the widgets window: spawn the diagnostics tool.
        import subprocess
        ui = Path(__file__).resolve().with_name('diagnostics_ui.py')
        subprocess.Popen([sys.executable, str(ui)], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)

    @QtCore.Slot(str)
    def showHealth(self, key):
        app = self._model.app_record(key)
        report = manager.container_health_report(app)
        if report is None:
            self._set_status(
                'Container health is not tracked for ' + app['format'] + ' applications.')
            return
        from manager import HealthDialog
        dialog = HealthDialog(app, report, self.anchor)
        dialog.repair_requested.connect(lambda: self.repairContainer(key))
        dialog.reexport_requested.connect(lambda: self.reexportLauncher(key))
        dialog.open()

    @QtCore.Slot(str)
    def repairContainer(self, key):
        self._guard(manager.repair_container_app, key,
                    'Container repair failed', refresh=True)

    @QtCore.Slot(str)
    def reexportLauncher(self, key):
        self._guard(manager.reexport_launcher, key,
                    'Launcher re-export failed', refresh=True)

    @QtCore.Slot()
    def installFromFile(self):
        """Same handler as the widgets window's header: the package picker
        routes the selection through the normal CLI package review."""
        manager.ui_style.open_package(self.anchor)

    @QtCore.Slot()
    def installFromUrl(self):
        """Same handler as the widgets window's header: UrlInstallDialog
        downloads, previews and installs through the normal backends."""
        dialog = manager.UrlInstallDialog(self.anchor)
        dialog.installed.connect(self.refresh)
        dialog.exec()

    def _guard(self, action, key, failure, refresh=False):
        """Run a backend action; report failures in the status line."""
        try:
            if key is None:
                message = action()
            else:
                message = action(self._model.app_record(key))
        except Exception as error:
            self._set_status(failure + ': ' + str(error))
            return
        self._set_status(str(message))
        if refresh:
            self.refresh()

    # ── drag and drop: same classification and batch dialog ──────────────

    @staticmethod
    def _local_paths(urls):
        paths = []
        for url in urls:
            if isinstance(url, str):
                paths.append(url)
            else:
                local = QtCore.QUrl(url).toLocalFile() if not isinstance(url, QtCore.QUrl) \
                    else url.toLocalFile()
                if local:
                    paths.append(local)
        return paths

    @QtCore.Slot(list, result=bool)
    def dropAcceptable(self, urls):
        """True when any dropped URL is a package file the old window accepts."""
        return any(manager.classify_package(p) for p in self._local_paths(urls))

    @QtCore.Slot(list)
    def dropPackages(self, urls):
        paths = [p for p in self._local_paths(urls) if manager.classify_package(p)]
        if not paths:
            self._set_status('No supported package files were dropped.')
            return
        from manager import BatchQueue, BatchQueueDialog
        if self._batch_dialog is not None and self._batch_dialog.isVisible():
            self._batch_dialog.append(paths)
            self._batch_dialog.raise_()
            return
        dialog = BatchQueueDialog(BatchQueue(paths), self.anchor)
        dialog.finished.connect(self._batch_closed)
        dialog.show()
        self._batch_dialog = dialog

    def _batch_closed(self, result=None):
        self._batch_dialog = None
        self.refresh()

    # ── AppInstall self-update: the widgets window's flow, verbatim ──────

    @QtCore.Slot(bool)
    def checkUpdates(self, manual=True):
        if self._update_operation or self._update_tag:
            return
        if not manual:
            preferences = settings.read()
            last_check = preferences.get('last_update_check', 0)
            if time.time() - last_check < manager.UPDATE_TTL_SECONDS:
                cached = preferences.get('update_check_result')
                self._update_tag = cached['tag'] if cached else ''
                if self._update_tag:
                    self._update_status = 'AppInstall ' + self._update_tag + ' is available'
                elif cached:
                    self._update_status = 'AppInstall is up to date'
                else:
                    self._update_status = 'Update status has not been checked'
                self.updateTagChanged.emit(self._update_tag)
                self.updateStatusChanged.emit(self._update_status)
                return
        if not self._update_helper.is_file():
            self._update_status = 'Update check is unavailable in this installation'
            self.updateStatusChanged.emit(self._update_status)
            return
        self._update_operation = 'check'
        self._update_manual = manual
        self._update_status = 'Checking for updates…'
        self.updateStatusChanged.emit(self._update_status)
        self._update_action_visible = False
        self.updateActionVisibleChanged.emit(False)
        self._update_process.start(
            '/usr/bin/bash', [str(self._update_helper), '--desktop-check'])
        self._update_process.closeWriteChannel()

    @QtCore.Slot()
    def installUpdate(self):
        if self._update_operation or not self._update_tag:
            return
        self._update_operation = 'install'
        self._update_status = 'Installing AppInstall ' + self._update_tag + '…'
        self.updateStatusChanged.emit(self._update_status)
        self._update_process.start('/usr/bin/bash', [
            str(self._update_helper), '--desktop-update', self._update_tag,
        ])
        self._update_process.closeWriteChannel()

    def _update_finished(self, exit_code, exit_status):
        operation, self._update_operation = self._update_operation, ''
        output = bytes(self._update_process.readAll()).decode(errors='replace')
        self._update_action_visible = True
        self.updateActionVisibleChanged.emit(True)
        ok = exit_code == 0 and exit_status == QtCore.QProcess.ExitStatus.NormalExit
        if operation == 'check':
            match = re.search(r'^APPINSTALL_UPDATE=(v[0-9]+\.[0-9]+\.[0-9]+)$', output, re.M)
            # Store the timestamp and result together; failures invalidate
            # any earlier success rather than implying "up to date".
            try:
                preferences = settings.read()
                checked_at = int(time.time())
                preferences['last_update_check'] = checked_at
                preferences['update_check_result'] = (
                    {'checked_at': checked_at, 'tag': match[1] if match else ''}
                    if ok else None)
                settings.write(preferences)
            except OSError:
                pass
            if ok and match:
                self._update_tag = match[1]
                self._update_status = 'AppInstall ' + match[1] + ' is available'
                self.updateTagChanged.emit(match[1])
                self.updateStatusChanged.emit(self._update_status)
                self._notify_update(match[1])
            elif ok:
                self._update_status = 'AppInstall is up to date'
                self.updateStatusChanged.emit(self._update_status)
            else:
                self._update_status = 'Could not check for updates'
                self.updateStatusChanged.emit(self._update_status)
                if self._update_manual:
                    self._show_update_details('Update check failed', output)
        elif operation == 'install':
            tag = self._update_tag
            if not ok or ('APPINSTALL_UPDATED=' + tag) not in output.splitlines():
                # The update is still available; keep the banner actionable.
                self._update_status = 'Update did not complete'
                self.updateStatusChanged.emit(self._update_status)
                return
            self._update_tag = ''
            try:
                settings.update('update_check_result', None)
            except OSError:
                pass
            self.updateTagChanged.emit('')
            self._update_status = 'AppInstall ' + tag + ' installed. Reopen AppInstall to use it.'
            self.updateStatusChanged.emit(self._update_status)
            self._show_update_details('What’s new in AppInstall ' + tag,
                                      release_notes(tag))

    def _notify_update(self, tag):
        """Best-effort desktop notification, honouring the user setting."""
        if not settings.read().get('notifications', False):
            return
        try:
            subprocess.run(
                ['notify-send', 'AppInstall',
                 'Version ' + tag + ' is available'],
                capture_output=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass

    def _show_update_details(self, title, text):
        """Same dialog the widgets window uses for update details/notes."""
        message = QtWidgets.QMessageBox(self.anchor)
        message.setWindowTitle('AppInstall')
        message.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        message.setText(title)
        message.setDetailedText(text[-12000:])
        if title.startswith('What’s new'):
            message.setInformativeText(text[:2500])
        message.exec()

    # ── close guard: the widgets window's closeEvent, as a slot ─────────

    @QtCore.Slot(result=bool)
    def allowClose(self):
        """True when the window may close now. A batch review with a running
        pipeline is cancelled first (the close is ignored once); an
        AppInstall upgrade in progress blocks closing; a running update
        check is killed, then the close proceeds."""
        if self._catalog_initializing and self._catalog_worker is not None \
                and self._catalog_worker.isRunning():
            self._set_catalog_status('Preparing repository metadata; close after setup completes.')
            return False
        if self._batch_dialog is not None and \
                getattr(self._batch_dialog, 'process', None) is not None:
            self._batch_dialog.reject()
            return False
        if self._update_operation == 'install':
            self._set_status('AppInstall is updating. Closing is blocked until it finishes.')
            return False
        if self._update_operation == 'check':
            self._update_process.kill()
            self._update_process.waitForFinished(1000)
        return True


def main():
    args = sys.argv[1:]
    smoke = '--smoke' in args
    shot = None
    if '--screenshot' in args:
        index = args.index('--screenshot')
        if index + 1 < len(args):
            shot = args[index + 1]
    if smoke or shot is not None:
        # Strip Qt-incompatible flags before constructing QApplication.
        filtered = []
        skip_next = False
        for a in args:
            if skip_next:
                skip_next = False
                continue
            if a == '--smoke':
                continue
            if a == '--screenshot':
                skip_next = True
                continue
            filtered.append(a)
        sys.argv = [sys.argv[0]] + filtered
        # Deterministic headless run for CI: no windowing system required,
        # and the auto update checks must never touch the network.
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        os.environ['APPINSTALL_DISABLE_UPDATE_TIMER'] = '1'

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('AppInstall')
    app.setOrganizationName('AppInstall')

    anchor = QtWidgets.QWidget()
    bridge = Bridge(anchor)
    bridge.applyTheme()
    bridge.refresh()
    app.aboutToQuit.connect(bridge.shutdownCatalog)

    def _log_qml_message(mode, context, message):
        # QML errors would otherwise be silent on a failed engine.load.
        print('QML: ' + message, file=sys.stderr, flush=True)

    QtCore.qInstallMessageHandler(_log_qml_message)
    engine = QtQml.QQmlApplicationEngine()
    engine.rootContext().setContextProperty('bridge', bridge)
    engine.rootContext().setContextProperty('appsModel', bridge.model)
    engine.rootContext().setContextProperty('catalogModel', bridge.catalogModel)
    engine.addImportPath(str(QML_DIR.parent))
    engine.load(str(QML_DIR / 'main.qml'))
    if not engine.rootObjects():
        if smoke:
            print('QML smoke: main.qml failed to load', flush=True)
            sys.exit(4)
        sys.exit(1)

    window = engine.rootObjects()[0]
    window.setIcon(QtGui.QIcon.fromTheme('appinstall'))
    if shot:
        # Same delayed-grab contract as the widgets window's --screenshot:
        # wait for the async inventory load to land, then save the window
        # image and quit. Uses QQuickWindow.grabWindow() which renders via
        # the scene graph and works on both X11 and Wayland compositors
        # (Weston, KWin) without requiring a native window handle.
        def grab():
            pixmap = window.grabWindow()
            if pixmap.isNull():
                print('ERROR: screenshot capture failed (null pixmap)', flush=True)
                app.quit()
                sys.exit(1)
            pixmap.save(shot)
            print('DEBUG: screenshot saved to', shot, flush=True)
            app.quit()
        QtCore.QTimer.singleShot(1500, grab)
    elif smoke:
        # The scene came up with no missing QML modules: quit cleanly.
        print('QML smoke: main.qml loaded', flush=True)
        QtCore.QTimer.singleShot(300, app.quit)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
