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
from pathlib import Path

from qt_compat import QtCore, QtGui, QtWidgets

try:
    from PySide6 import QtQml
except ModuleNotFoundError as error:
    if error.name != "PySide6":
        raise
    from PyQt6 import QtQml  # type: ignore

import manager
import settings

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

    KeyRole = QtCore.Qt.UserRole + 1
    NameRole = QtCore.Qt.UserRole + 2
    FormatRole = QtCore.Qt.UserRole + 3
    FormatLabelRole = QtCore.Qt.UserRole + 4
    VersionRole = QtCore.Qt.UserRole + 5
    ContainerRole = QtCore.Qt.UserRole + 6
    SizeTextRole = QtCore.Qt.UserRole + 7
    StatusRole = QtCore.Qt.UserRole + 8
    StatusLabelRole = QtCore.Qt.UserRole + 9
    StatusToneRole = QtCore.Qt.UserRole + 10
    ProblemsRole = QtCore.Qt.UserRole + 11
    PinnedRole = QtCore.Qt.UserRole + 12
    IconUrlRole = QtCore.Qt.UserRole + 13
    InitialRole = QtCore.Qt.UserRole + 14
    CanOpenRole = QtCore.Qt.UserRole + 15
    CanUninstallRole = QtCore.Qt.UserRole + 16
    CanUpdateRole = QtCore.Qt.UserRole + 17
    IsContainerRole = QtCore.Qt.UserRole + 18
    LastLaunchRole = QtCore.Qt.UserRole + 19
    DescriptionRole = QtCore.Qt.UserRole + 20

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

    def data(self, index, role=QtCore.Qt.DisplayRole):
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
            return 'file://' + app['icon'] if app.get('icon') else ''
        if role == self.InitialRole:
            name = app['name'] or '?'
            return name[0].upper()
        if role == self.CanOpenRole:
            return app['format'] in ('appimage', 'flatpak', 'deb', 'rpm') and bool(app.get('desktop'))
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


class Bridge(QtCore.QObject):
    """Actions and state the QML screen reads; every action calls the
    existing manager backend through its normal entry point."""

    countChanged = QtCore.Signal(int)
    loadingChanged = QtCore.Signal(bool)
    statusTextChanged = QtCore.Signal(str)
    themeChanged = QtCore.Signal()
    updateStatusChanged = QtCore.Signal(str)
    updateActionVisibleChanged = QtCore.Signal(bool)

    @QtCore.Property(bool, notify=updateActionVisibleChanged)
    def actionVisible(self):
        return self._update_action_visible

    darkChanged = QtCore.Signal(bool)
    updateTagChanged = QtCore.Signal(str)

    def __init__(self, anchor, parent=None):
        super().__init__(parent)
        self.anchor = anchor  # hidden QWidget used to parent the existing dialogs
        self._model = AppModel(self)
        self._dark = False
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

    @QtCore.Property(bool, constant=True)
    def reducedMotion(self):
        return self._reduced_motion

    @QtCore.Property(QtCore.QObject, constant=True)
    def model(self):
        return self._model

    @QtCore.Property(str, notify=updateStatusChanged)
    def updateStatus(self):
        return self._update_status

    @QtCore.Property(str, notify=updateTagChanged)
    def updateTag(self):
        return self._update_tag

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

    # ── theme ────────────────────────────────────────────────────────────

    @QtCore.Slot(str)
    def setTheme(self, theme):
        try:
            settings.update('theme', theme)
        except OSError:
            pass
        self.applyTheme()

    def applyTheme(self):
        theme = settings.read().get('theme', 'auto')
        hint = QtGui.QGuiApplication.styleHints().colorScheme()
        system_dark = hint == QtCore.Qt.ColorScheme.Dark
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
            last_check = settings.read().get('last_update_check', 0)
            if time.time() - last_check < manager.UPDATE_TTL_SECONDS:
                # Within the 12h TTL: surface the last known state only.
                if self._update_tag:
                    self._update_status = 'AppInstall ' + self._update_tag + ' is available'
                    self.updateTagChanged.emit(self._update_tag)
                else:
                    self._update_status = 'AppInstall is up to date'
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
            # Record the check so automatic checks respect the 12h TTL.
            try:
                settings.update('last_update_check', int(time.time()))
            except OSError:
                pass
            match = re.search(r'^APPINSTALL_UPDATE=(v[0-9]+\.[0-9]+\.[0-9]+)$', output, re.M)
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
    if smoke:
        sys.argv = [sys.argv[0]] + [a for a in args if a != '--smoke']
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

    def _log_qml_message(mode, context, message):
        # QML errors would otherwise be silent on a failed engine.load.
        print('QML: ' + message, file=sys.stderr, flush=True)

    QtCore.qInstallMessageHandler(_log_qml_message)
    engine = QtQml.QQmlApplicationEngine()
    engine.rootContext().setContextProperty('bridge', bridge)
    engine.rootContext().setContextProperty('appsModel', bridge.model)
    engine.addImportPath(str(QML_DIR.parent))
    engine.load(str(QML_DIR / 'main.qml'))
    if not engine.rootObjects():
        if smoke:
            print('QML smoke: main.qml failed to load', flush=True)
            sys.exit(4)
        sys.exit(1)

    window = engine.rootObjects()[0]
    window.setIcon(QtGui.QIcon.fromTheme('appinstall'))
    if smoke:
        # The scene came up with no missing QML modules: quit cleanly.
        print('QML smoke: main.qml loaded', flush=True)
        QtCore.QTimer.singleShot(300, app.quit)
        sys.exit(app.exec())
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
