#!/usr/bin/env python3
"""Opt-in WebView preview of the My Applications manager screen.

Plain TypeScript + HTML + CSS rendered by the system WebKitGTK (no
Electron, no browser runtime shipped, no frontend framework). The Python
side keeps ownership of the data: it serves the existing inventory and
settings over a loopback HTTP API, and the WebView window is a thin shell
around that API.

The widgets manager (manager.py) stays the default UI and the QML preview
(manager_qml.py) stays available; this entry point is an additional,
explicitly launched surface.

Run with:  python3 manager_web.py
"""
import argparse
import importlib
import json
import mimetypes
import os
import re
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

# The preview ships next to the other helpers (a checkout, /usr/bin, or
# /usr/lib/appinstall behind a symlink). Import them from wherever this
# file really lives.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import manager
import settings

PREVIEW_DIR = HERE / 'webpreview'

# The frontend lives in two shapes: a checkout keeps the sources and the
# compiled output apart, a native package ships one flat directory.
CHECKOUT_FRONTEND = ('assets/index.html', 'assets/app.css', 'dist')
PACKAGED_FRONTEND = ('index.html', 'app.css', 'js')
PACKAGED_ROOT = Path('/usr/share/appinstall/webpreview')


def frontend_paths():
    """Locate the frontend in a source checkout or a native package."""
    candidates = [PREVIEW_DIR, PACKAGED_ROOT]
    for root in candidates:
        for index, css, scripts in (CHECKOUT_FRONTEND, PACKAGED_FRONTEND):
            if (root / index).is_file() and (root / css).is_file():
                return (root / index, root / css, root / scripts)
    root = candidates[0]
    return (root / CHECKOUT_FRONTEND[0], root / CHECKOUT_FRONTEND[1],
            root / CHECKOUT_FRONTEND[2])

# Status presentation, matching the QML preview's mapping so both
# prototypes read the same way.
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

# Only these names are served from the compiled frontend; the frontend
# directory is never browsable.
JS_NAME = re.compile(r'^[A-Za-z0-9_.-]+\.js$')

MAX_BODY = 64 * 1024


def build_preview_record(app, favorites):
    """One inventory row shaped for the web client.

    The Python side owns every label, so the TypeScript view never has to
    duplicate status wording, format wording or size formatting.
    """
    size = manager.app_disk_usage(app)
    name = app.get('name') or '?'
    return {
        'key': app['key'],
        'name': name,
        'format': app.get('format') or 'unknown',
        'formatLabel': manager.FORMAT_LABELS.get(app.get('format'), app.get('format') or 'Unknown'),
        'version': app.get('version') or '',
        'container': app.get('container') or '',
        'sizeText': manager.format_size(size),
        'sizeBytes': size,
        'status': app.get('status') or manager.STATUS_UNKNOWN,
        'statusLabel': STATUS_LABELS.get(app.get('status'), app.get('status') or 'Unknown'),
        'statusTone': STATUS_TONES.get(app.get('status'), 'neutral'),
        'problems': '; '.join(app.get('problems') or []),
        'favorite': app['key'] in favorites,
        'iconUrl': '',
        'initial': name[0].upper(),
        'lastLaunch': str((app.get('last_launch') or {}).get('started') or ''),
        'description': app.get('description') or '',
    }


class PreviewState:
    """The preview's view of the world: inventory, favorites and theme.

    Every mutation goes through the normal settings module, so the
    widgets manager and the QML preview see the same preferences.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._apps = []
        self._favorites = set()
        self._theme = 'auto'
        self._error = ''
        self._icons = {}

    # ── loading ────────────────────────────────────────────────────────

    def load(self):
        """Read the inventory once, in the background, exactly like the
        widgets window does (read-only registries, no side effects)."""
        preferences = settings.read()
        with self._lock:
            self._favorites = set(preferences.get('favorites', []))
            self._theme = preferences.get('theme', 'auto')
        try:
            inventory = manager.load_inventory()
        except Exception as error:  # a broken registry must not kill the preview
            with self._lock:
                self._error = 'Could not read the application inventory: ' + str(error)
            self._ready.set()
            return
        with self._lock:
            self._apps = list(inventory)
            # Only icons that are real files can be served: an icon
            # *name* (a Flatpak app id, for example) is left to the
            # initial letter in the frontend.
            self._icons = {}
            for app in self._apps:
                icon = app.get('icon') or ''
                if icon and Path(icon).is_file():
                    self._icons[app['key']] = icon
        self._ready.set()

    def wait_ready(self, timeout=15.0):
        return self._ready.wait(timeout)

    # ── reads ──────────────────────────────────────────────────────────

    def snapshot(self):
        with self._lock:
            apps = [build_preview_record(app, self._favorites) for app in self._apps]
            for app in apps:
                if app['key'] in self._icons:
                    app['iconUrl'] = '/icon/' + quote(app['key'], safe='')
            counts = {fmt: 0 for fmt in manager.FORMATS}
            for app in apps:
                if app['format'] in counts:
                    counts[app['format']] += 1
            return {
                'ready': self._ready.is_set(),
                'error': self._error,
                'theme': self._theme,
                'favorites': sorted(self._favorites),
                'counts': counts,
                'apps': apps,
            }

    def icon_path(self, key):
        with self._lock:
            return self._icons.get(key, '')

    # ── writes ─────────────────────────────────────────────────────────

    def set_favorite(self, key, value):
        if not isinstance(key, str) or not key:
            raise ValueError('a favorite needs an application key')
        with self._lock:
            if value:
                self._favorites.add(key)
            else:
                self._favorites.discard(key)
            favorites = sorted(self._favorites)
        settings.update('favorites', favorites)
        return favorites

    def set_theme(self, theme):
        if theme not in settings.THEMES:
            raise ValueError('unknown theme: ' + str(theme))
        settings.update('theme', theme)
        with self._lock:
            self._theme = theme
        return theme


class PreviewHandler(BaseHTTPRequestHandler):
    """Static frontend plus a small JSON API, bound to loopback only."""

    server_version = 'AppInstallPreview/1.0'
    protocol_version = 'HTTP/1.1'

    # The preview is a local window, not a service: keep the console quiet.
    def log_message(self, format, *args):
        pass

    # ── helpers ────────────────────────────────────────────────────────

    def _send(self, code, body=b'', content_type='application/octet-stream', extra=None):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != 'HEAD' and body:
            self.wfile.write(body)

    def _send_json(self, code, payload):
        body = json.dumps(payload).encode('utf-8')
        self._send(code, body, 'application/json; charset=utf-8')

    def _authorized(self):
        """The API needs the per-session token.

        The token travels in a URL fragment, so it never reaches the
        server log, and the client sends it in a custom header. A custom
        header makes every state-changing request a preflighted one, so a
        random web page cannot drive this API.

        The page's own image requests cannot carry a custom header, so
        the HTML response hands them a same-origin session cookie
        instead. A cookie marked SameSite=Strict is never attached to a
        cross-site request, so a random web page cannot use it either.
        """
        token = self.headers.get('X-AppInstall-Token', '')
        if not token or not secrets.compare_digest(token, self.server.token):
            if not self._has_session_cookie():
                self._send_json(403, {'error': 'forbidden'})
                return False
        origin = self.headers.get('Origin')
        if origin and origin != self.server.origin:
            self._send_json(403, {'error': 'forbidden origin'})
            return False
        return True

    def _has_session_cookie(self):
        cookies = self.headers.get('Cookie', '')
        expected = self.server.cookie_name + '=' + self.server.cookie
        for part in cookies.split(';'):
            if part.strip() == expected:
                return True
        return False

    def _read_body(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return None
        if length <= 0 or length > MAX_BODY:
            return None
        try:
            return json.loads(self.rfile.read(length).decode('utf-8'))
        except (UnicodeError, ValueError):
            return None

    def _serve_file(self, path, content_type, extra=None):
        try:
            body = path.read_bytes()
        except OSError:
            self._send_json(404, {'error': 'not found'})
            return
        self._send(200, body, content_type, extra)

    # ── routes ─────────────────────────────────────────────────────────

    def do_GET(self):
        route = urlparse(self.path).path
        if os.environ.get('APPINSTALL_WEBVIEW_DEBUG') == '1':
            print('WebView request: ' + route, file=sys.stderr, flush=True)
        index, stylesheet, scripts = self.server.frontend
        if route == '/':
            # The page gets a session cookie for its own subresources.
            self._serve_file(index, 'text/html; charset=utf-8', {
                'Set-Cookie': (self.server.cookie_name + '=' +
                               self.server.cookie +
                               '; Path=/; SameSite=Strict; HttpOnly'),
            })
            return
        if route == '/app.css':
            self._serve_file(stylesheet, 'text/css; charset=utf-8')
            return
        if route.startswith('/js/'):
            name = route[len('/js/'):]
            if not JS_NAME.match(name):
                self._send_json(404, {'error': 'not found'})
                return
            self._serve_file(scripts / name, 'text/javascript; charset=utf-8')
            return
        if route.startswith('/icon/'):
            if not self._authorized():
                return
            key = unquote(route[len('/icon/'):])
            path = self.server.state.icon_path(key)
            if not path:
                self._send_json(404, {'error': 'no icon'})
                return
            guessed = mimetypes.guess_type(path)[0] or 'application/octet-stream'
            self._serve_file(Path(path), guessed)
            return
        if route == '/api/state':
            if not self._authorized():
                return
            self._send_json(200, self.server.state.snapshot())
            return
        self._send_json(404, {'error': 'not found'})

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        route = urlparse(self.path).path
        if not self._authorized():
            return
        if route == '/api/favorite':
            payload = self._read_body()
            if not isinstance(payload, dict):
                self._send_json(400, {'error': 'invalid request'})
                return
            try:
                favorites = self.server.state.set_favorite(
                    payload.get('key'), bool(payload.get('favorite')))
            except (ValueError, OSError) as error:
                self._send_json(400, {'error': str(error)})
                return
            self._send_json(200, {'favorites': favorites})
            return
        if route == '/api/theme':
            payload = self._read_body()
            if not isinstance(payload, dict):
                self._send_json(400, {'error': 'invalid request'})
                return
            try:
                theme = self.server.state.set_theme(payload.get('theme'))
            except (ValueError, OSError) as error:
                self._send_json(400, {'error': str(error)})
                return
            self._send_json(200, {'theme': theme})
            return
        self._send_json(404, {'error': 'not found'})


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, state, port=0):
        super().__init__(('127.0.0.1', port), PreviewHandler)
        self.state = state
        self.token = secrets.token_urlsafe(24)
        # A second secret for the page's own image requests, which
        # cannot carry the token header.
        self.cookie_name = 'appinstall_preview'
        self.cookie = secrets.token_urlsafe(16)
        self.origin = 'http://127.0.0.1:' + str(self.server_address[1])
        self.frontend = frontend_paths()

    def url(self):
        # The token stays in the fragment: it is never sent to the server
        # and never lands in a log line.
        return self.origin + '/#token=' + self.token


def load_webkit():
    """Import Gtk and the WebKit bindings this system ships.

    WebKit2 4.1 on GTK 3 is the common case (Arch, Debian, Ubuntu);
    WebKit 6.0 on GTK 4 is the newer one. Either is enough — there is no
    bundled browser runtime.
    """
    try:
        import gi
    except ImportError as error:
        raise RuntimeError(
            'PyGObject is required for the WebView preview: ' + str(error))
    failures = []
    # (GTK version, WebKit namespace, WebKit version)
    for gtk_version, namespace, webkit_version in (
            ('3.0', 'WebKit2', '4.1'), ('4.0', 'WebKit', '6.0')):
        try:
            gi.require_version('Gtk', gtk_version)
            gi.require_version(namespace, webkit_version)
        except ValueError as error:
            failures.append(gtk_version + '/' + namespace + ' ' + webkit_version
                            + ': ' + str(error))
            continue
        try:
            from gi.repository import Gtk
            webkit = importlib.import_module('gi.repository.' + namespace)
        except (ImportError, AttributeError) as error:
            failures.append(gtk_version + '/' + namespace + ' ' + webkit_version
                            + ': ' + str(error))
            continue
        return Gtk, webkit, gtk_version
    raise RuntimeError(
        'WebKitGTK is required for the WebView preview (WebKit2 4.1 on GTK 3 '
        'or WebKit 6.0 on GTK 4). ' + '; '.join(failures))


def build_view(webkit, content):
    """Create a WebView that uses the given content manager.

    WebKit2 4.1 has a constructor for this; WebKit 6.0 removed it and
    takes the manager as a construction property instead.
    """
    factory = getattr(webkit.WebView, 'new_with_user_content_manager', None)
    if factory is not None:
        return factory(content)
    from gi.repository import GObject
    return GObject.new(webkit.WebView, user_content_manager=content)


class WebPreviewWindow:
    """A desktop window around the system WebView."""

    def __init__(self, Gtk, webkit, GLib, gtk_version, url, on_message):
        self.Gtk = Gtk
        self.webkit = webkit
        self.GLib = GLib
        self.gtk_version = gtk_version
        self.url = url
        self.on_message = on_message
        self.messages = []

        self.application = None
        if gtk_version.startswith('3'):
            # GTK 3 runs on Gtk.main(): a plain window, no session bus
            # needed, which also keeps the smoke job working inside a
            # container.
            self.window = Gtk.Window(title='My Applications — AppInstall')
        else:
            self.application = Gtk.Application(
                application_id='org.appinstall.MyApplicationsPreview')
            self.window = Gtk.Window(
                application=self.application, title='My Applications — AppInstall')
        self.window.set_default_size(1040, 720)
        self.window.set_size_request(720, 480)

        content = webkit.UserContentManager()
        self._register_messages(content)
        self.view = build_view(webkit, content)
        self._build_settings()
        try:
            self.view.get_context_menu().connect('context-menu', lambda *args: True)
        except AttributeError:
            pass
        self.view.connect('load-changed', self._load_changed)
        self.view.connect('notify::title', self._title_changed)

        if gtk_version.startswith('3'):
            self.window.add(self.view)
            self.window.connect('destroy', lambda *args: self.Gtk.main_quit())
        else:
            self.window.set_child(self.view)
            self.application.connect('activate', self._activate)
            self.window.connect('destroy', lambda *args: self.application.quit())

    def _build_settings(self):
        settings_object = self.view.get_settings()
        debug = os.environ.get('APPINSTALL_WEBVIEW_DEBUG') == '1'
        for name, value in (('enable_developer_extras', debug),
                            ('enable_write_console_messages_to_stdout', debug),
                            ('enable_back_forward_navigation_gestures', False),
                            ('enable_smooth_scrolling', True)):
            try:
                settings_object.set_property(name, value)
            except (AttributeError, TypeError):
                pass

    def _register_messages(self, content):
        """Open the page-to-shell channel.

        WebKit2 2.8 and newer register the channel name and deliver the
        messages through the script-message-received signal; older
        bindings take the callback directly.
        """
        for name in ('register_script_message_handler', 'register_message_handler'):
            register = getattr(content, name, None)
            if register is None:
                continue
            try:
                register('appinstall')
            except TypeError:
                try:
                    register('appinstall', self._handle_message)
                except TypeError:
                    continue
                return True
            content.connect('script-message-received::appinstall',
                            self._handle_message)
            return True
        return False

    def _handle_message(self, *args):
        # The binding calls back with the payload (and, on some versions,
        # the manager as well), so take the last argument.
        message = args[-1] if args else ''
        # WebKit hands the payload over as a JavascriptResult wrapping a
        # JSValue; the preview only ever sends short strings.
        if hasattr(message, 'get_js_value'):
            message = message.get_js_value()
        if hasattr(message, 'to_string'):
            message = message.to_string()
        self.messages.append(str(message))
        if os.environ.get('APPINSTALL_WEBVIEW_DEBUG') == '1':
            print('WebView message: ' + str(message), file=sys.stderr, flush=True)
        if self.on_message:
            self.on_message(str(message))

    def _load_changed(self, view, event):
        if os.environ.get('APPINSTALL_WEBVIEW_DEBUG') == '1':
            print('WebView load event: ' + str(event), file=sys.stderr, flush=True)

    def _title_changed(self, view, param):
        title = view.get_title()
        if title:
            self.window.set_title(title)

    def _activate(self, application):
        """GTK 4 activation: show the window, then load once the loop runs."""
        self.window.present()
        self.GLib.idle_add(self._load)

    def _load(self):
        if os.environ.get('APPINSTALL_WEBVIEW_DEBUG') == '1':
            print('WebView loading ' + str(self.url), file=sys.stderr, flush=True)
        self.view.load_uri(self.url)
        return False

    def run(self):
        if self.gtk_version.startswith('3'):
            self.window.show_all()
            self.GLib.idle_add(self._load)
            started = time.perf_counter()
            self.Gtk.main()
            if os.environ.get('APPINSTALL_WEBVIEW_DEBUG') == '1':
                print('WebView main loop ended after '
                      + str(round(time.perf_counter() - started, 2)) + 's',
                      file=sys.stderr, flush=True)
            return 0
        return self.application.run([sys.argv[0]])

    def evaluate(self, javascript):
        self.view.evaluate_javascript(javascript, -1, None, None, None, None, None)

    def close(self):
        if os.environ.get('APPINSTALL_WEBVIEW_DEBUG') == '1':
            print('WebView close requested', file=sys.stderr, flush=True)
        if getattr(self, '_closed', False):
            return
        self._closed = True

        def quit_loop():
            # Quit from another thread: a message handler can run inside a
            # nested loop, and only the outer loop must stop.
            time.sleep(0.05)
            try:
                if self.application is not None:
                    self.application.quit()
                else:
                    self.Gtk.main_quit()
            except Exception:
                pass

        threading.Thread(target=quit_loop, daemon=True).start()


class Benchmark:
    """Measures startup, search responsiveness and idle memory.

    The measurement runs inside the GTK main loop: the page reports its
    own search timings over the message channel, so the numbers are the
    browser's, not the shell's guesses.
    """

    QUERIES = ('a', 'app', 'code', 'x', 'flatpak', 'a')

    def __init__(self, window, state):
        self.window = window
        self.state = state
        self.startup_ms = None
        self.search_ms = []
        self.started = False
        self.finished = False
        self._index = 0

    def on_ready(self):
        if self.started:
            return
        self.started = True
        self.startup_ms = process_age_ms()
        # A warm-up query first: the first keystroke pays for the
        # JavaScript engine's start-up, not for the search.
        self._ask(self.QUERIES[0])

    def _ask(self, query):
        self.window.evaluate(
            'window.__appinstall && window.__appinstall.benchSearch('
            + json.dumps(query) + ')')

    def on_search(self, value):
        if self.started and not self.finished:
            self.search_ms.append(value)
        if self._index + 1 < len(self.QUERIES):
            self._index += 1
            self._ask(self.QUERIES[self._index])
            return
        # Let the WebKit helper processes settle before the memory reading.
        self.window.GLib.timeout_add(1000, self._finish)

    def _finish(self):
        self.finished = True
        memory = process_tree_memory(os.getpid())
        result = {
            'target': 'webview',
            'startup_ms': round(self.startup_ms or 0.0, 1),
            'search_ms': [round(value, 2) for value in self.search_ms[1:]],
            'rss_bytes': memory['rss_bytes'],
            'pss_bytes': memory['pss_bytes'],
            'apps': len(self.state.snapshot()['apps']),
        }
        print('BENCH ' + json.dumps(result), flush=True)
        self.window.close()
        return False


def process_age_ms():
    """How long this process has been running, in milliseconds.

    Read from /proc, so it includes the interpreter start-up and every
    import: the honest "time since the user launched the app".
    """
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
    """Memory of a process and its descendants.

    Returns the summed RSS and the summed PSS. The WebKit preview runs
    several helper processes that share the same libraries, so summed RSS
    counts those pages more than once; PSS splits them fairly.
    """
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
        description='WebView preview of the AppInstall My Applications screen')
    parser.add_argument('--port', type=int, default=0,
                        help='loopback port for the preview API (0 picks one)')
    parser.add_argument('--no-window', action='store_true',
                        help='serve the API without opening a window')
    parser.add_argument('--smoke', action='store_true',
                        help='open the window, wait for the first render, exit')
    parser.add_argument('--bench', action='store_true',
                        help='measure startup, search latency and idle memory')
    args = parser.parse_args(argv)

    state = PreviewState()
    loader = threading.Thread(target=state.load, name='inventory', daemon=True)
    loader.start()

    server = PreviewServer(state, port=args.port)
    thread = threading.Thread(target=server.serve_forever, name='preview-api',
                              daemon=True)
    thread.start()

    if args.no_window:
        print('Preview API on ' + server.url(), flush=True)
        try:
            while thread.is_alive():
                thread.join(0.5)
        except KeyboardInterrupt:
            pass
        server.shutdown()
        return 0

    try:
        Gtk, webkit, gtk_version = load_webkit()
        from gi.repository import GLib
    except (RuntimeError, ImportError) as error:
        print(str(error), file=sys.stderr)
        return 3

    rendered = {'count': None}
    watchdog = {'timer': None}
    benchmark = {'runner': None}

    def on_message(message):
        if message.startswith('bench:'):
            try:
                value = float(message.split(':', 1)[1])
            except (IndexError, ValueError):
                value = 0.0
            runner = benchmark['runner']
            if runner is not None:
                runner.on_search(value)
            return
        if not message.startswith('ready'):
            return
        _, _, count = message.partition(':')
        try:
            rendered['count'] = int(count)
        except ValueError:
            rendered['count'] = 0
        if args.bench:
            runner = benchmark['runner']
            if runner is not None:
                runner.on_ready()
            return
        if not args.smoke:
            return
        if watchdog['timer'] is not None:
            watchdog['timer'].cancel()
        window.close()

    window = WebPreviewWindow(Gtk, webkit, GLib, gtk_version, server.url(),
                              on_message)
    if args.bench:
        benchmark['runner'] = Benchmark(window, state)
        # The benchmark must never hang: a page that never paints ends
        # the run with a failure instead.
        timer = threading.Timer(90, window.close)
        timer.daemon = True
        timer.start()
    if args.smoke:
        def finish():
            if rendered['count'] is None:
                print('WebView smoke: the page never reported ready',
                      file=sys.stderr)
            window.close()
        timer = threading.Timer(60, finish)
        timer.daemon = True
        watchdog['timer'] = timer
        timer.start()

    status = window.run()
    server.shutdown()
    if args.bench:
        runner = benchmark['runner']
        if runner is None or not runner.finished:
            print('BENCH failed: the preview never finished the benchmark',
                  file=sys.stderr)
            return 6
        return 0
    if args.smoke:
        count = rendered['count']
        if count is None:
            return 4
        expected = os.environ.get('APPINSTALL_SMOKE_EXPECT_APPS')
        if expected is not None and expected.isdigit() and int(expected) != count:
            print('WebView smoke: rendered ' + str(count) + ' applications, '
                  'expected ' + expected, file=sys.stderr)
            return 5
        print('WebView smoke: the preview rendered ' + str(count) + ' applications',
              flush=True)
        return 0
    return status


if __name__ == '__main__':
    sys.exit(main())
