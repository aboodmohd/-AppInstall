#!/usr/bin/env python3
"""Benchmark the QML My Applications preview.

The QML preview (manager_qml.py) ships next to the WebView preview, so
this runner measures it in place — or in any other checkout that has
it. It reports the same three numbers the WebView preview does:

* startup: process start to the first painted frame with the inventory
* search: a search keystroke to the frame that shows the result
* memory: the process tree's RSS and PSS while idle

The result is printed as one JSON object after the BENCH marker, the
same shape tools/bench_manager.py reads from both previews.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

QUERIES = ('a', 'app', 'code', 'x', 'flatpak', 'a')


def process_age_ms():
    """How long this process has been running, in milliseconds."""
    try:
        with open('/proc/self/stat', encoding='utf-8') as handle:
            fields = handle.read().rsplit(')', 1)[1].split()
        starttime = int(fields[19]) / os.sysconf('SC_CLK_TCK')
        with open('/proc/uptime', encoding='utf-8') as handle:
            uptime = float(handle.read().split()[0])
    except (OSError, IndexError, ValueError):
        return 0.0
    return max(0.0, uptime - starttime) * 1000.0


def process_tree_memory(root_pid):
    """Memory of a process and its descendants (see manager_web.py)."""
    children = {}
    rss = {}
    pss = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / 'stat').read_text()
            status = (entry / 'status').read_text()
        except OSError:
            continue
        try:
            parent = int(stat.rsplit(')', 1)[1].split()[1])
        except (IndexError, ValueError):
            continue
        children.setdefault(parent, []).append(int(entry.name))
        for line in status.splitlines():
            if line.startswith('VmRSS:'):
                rss[int(entry.name)] = int(line.split()[1]) * 1024
                break
        try:
            rollup = (entry / 'smaps_rollup').read_text()
        except OSError:
            rollup = ''
        for line in rollup.splitlines():
            if line.startswith('Pss:'):
                pss[int(entry.name)] = int(line.split()[1]) * 1024
                break

    totals = {'rss_bytes': 0, 'pss_bytes': 0}
    stack = [root_pid]
    seen = set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        totals['rss_bytes'] += rss.get(pid, 0)
        totals['pss_bytes'] += pss.get(pid, 0)
        stack.extend(children.get(pid, []))
    return totals


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Benchmark the QML My Applications preview')
    parser.add_argument('--qml-checkout', default=str(ROOT),
                        help='path to a checkout that contains manager_qml.py')
    parser.add_argument('--timeout', type=float, default=60.0,
                        help='seconds to wait for the first frame')
    args = parser.parse_args(argv)

    checkout = Path(args.qml_checkout).resolve()
    if not (checkout / 'manager_qml.py').is_file():
        print('no manager_qml.py in ' + str(checkout), file=sys.stderr)
        return 2

    # The QML preview must not touch the network while it is measured.
    os.environ.setdefault('APPINSTALL_DISABLE_UPDATE_TIMER', '1')
    if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

    sys.path.insert(0, str(checkout))
    import manager_qml  # noqa: E402  (the path comes from the argument)

    from qt_compat import QtCore, QtGui, QtWidgets  # noqa: E402

    try:
        from PySide6 import QtQml
    except ModuleNotFoundError as error:
        if error.name != 'PySide6':
            raise
        from PyQt6 import QtQml  # type: ignore
        QtCore.Signal = QtCore.pyqtSignal
        QtCore.Slot = QtCore.pyqtSlot
        QtCore.Property = QtCore.pyqtProperty

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('AppInstall')
    app.setOrganizationName('AppInstall')

    anchor = QtWidgets.QWidget()
    bridge = manager_qml.Bridge(anchor)
    bridge.applyTheme()
    bridge.refresh()

    def _log_qml_message(mode, context, message):
        print('QML: ' + message, file=sys.stderr, flush=True)

    QtCore.qInstallMessageHandler(_log_qml_message)
    engine = QtQml.QQmlApplicationEngine()
    engine.rootContext().setContextProperty('bridge', bridge)
    engine.rootContext().setContextProperty('appsModel', bridge.model)
    engine.addImportPath(str(manager_qml.QML_DIR.parent))
    engine.load(str(manager_qml.QML_DIR / 'main.qml'))
    if not engine.rootObjects():
        print('QML benchmark: main.qml failed to load', file=sys.stderr)
        return 4

    window = engine.rootObjects()[0]
    window.setIcon(QtGui.QIcon.fromTheme('appinstall'))

    model = bridge.model
    state = {'startup_ms': None, 'search_ms': [], 'index': -1,
             'query_started': None, 'finished': False}

    def ask_next_query():
        state['index'] += 1
        if state['index'] >= len(QUERIES):
            QtCore.QTimer.singleShot(1000, finish)
            return
        state['query_started'] = time.perf_counter()
        model.setSearch(QUERIES[state['index']])

    def on_frame():
        """A frame was painted."""
        if state['startup_ms'] is None:
            if model.rowCount() == 0:
                return
            # The first painted frame with the inventory in the model:
            # that is the moment the screen is actually usable.
            state['startup_ms'] = process_age_ms()
            ask_next_query()
            return
        if state['query_started'] is None:
            return
        elapsed = (time.perf_counter() - state['query_started']) * 1000.0
        state['query_started'] = None
        state['search_ms'].append(elapsed)
        ask_next_query()

    def finish():
        if state['finished']:
            return
        state['finished'] = True
        memory = process_tree_memory(os.getpid())
        result = {
            'target': 'qml',
            'startup_ms': round(state['startup_ms'] or 0.0, 1),
            # The first query is a warm-up, like in the WebView preview.
            'search_ms': [round(value, 2) for value in state['search_ms'][1:]],
            'rss_bytes': memory['rss_bytes'],
            'pss_bytes': memory['pss_bytes'],
            'apps': model.rowCount(),
        }
        print('BENCH ' + json.dumps(result), flush=True)
        app.quit()

    def on_timeout():
        print('QML benchmark: the preview never painted a frame',
              file=sys.stderr)
        app.quit()

    window.afterRendering.connect(on_frame)
    # The inventory arrives asynchronously; make sure the scene paints
    # once it has rows, so the startup frame is measured, not guessed.
    model.countChanged.connect(window.requestUpdate)
    QtCore.QTimer.singleShot(int(args.timeout * 1000), on_timeout)
    app.exec()
    return 0 if state['finished'] else 6

if __name__ == '__main__':
    sys.exit(main())
