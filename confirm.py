#!/usr/bin/env python3
"""Optional Qt confirmation, using local metadata without executing packages.

Exit codes: 0 = install requested, 1 = cancelled by the user,
2 = unexpected failure, 3 = PySide6 unavailable (caller falls back)."""
import json
import os
from pathlib import Path
import sys
import traceback
from urllib.parse import urlparse, quote

import package_meta as meta


def enriched_metadata(file, ref):
    """Fetch display metadata only for known Flathub references; local data remains usable."""
    appid = ref['appid']
    from urllib.request import urlopen
    cached = None
    try:
        cache = Path(os.environ.get('XDG_CACHE_HOME', Path.home()/'.cache'))/'appinstall'
        cache.mkdir(parents=True, exist_ok=True)
        record = cache/(appid+'.json')
        if record.exists():
            cached = json.loads(record.read_text())
        else:
            with urlopen('https://flathub.org/api/v2/appstream/'+quote(appid), timeout=3) as response:
                cached = json.loads(response.read(1024*1024))
            record.write_text(json.dumps(cached))
    except Exception:
        return ref
    if not isinstance(cached, dict):
        return ref
    ref = dict(ref)
    if cached.get('name'):
        ref['name'] = cached['name']
    if cached.get('summary'):
        ref['description'] = cached['summary']
    iconurl = cached.get('icon', '')
    if isinstance(iconurl, str) and iconurl.startswith('https://') and urlparse(iconurl).hostname == 'dl.flathub.org':
        cached_icon = Path(os.environ.get('XDG_CACHE_HOME', Path.home()/'.cache'))/'appinstall'/(appid+'.png')
        if not cached_icon.exists():
            try:
                with urlopen(iconurl, timeout=3) as response:
                    imagebytes = response.read(2*1024*1024)
                cached_icon.write_bytes(imagebytes)
            except Exception:
                return ref
        ref['icon'] = str(cached_icon)
    return ref


def main():
    file = Path(sys.argv[1])
    kind, details = sys.argv[2:4]
    probe = '--probe' in sys.argv[4:]

    local = meta.display_metadata(file, kind, meta.metadata_roots())
    ref = local
    if kind == 'flatpakref' and local['appid']:
        ref = enriched_metadata(file, local)
    if kind in ('deb', 'rpm'):
        native_info = json.loads(details)
        ref = dict(ref,
                   name=native_info['name']+' '+native_info.get('version', ''),
                   description=native_info.get('description', ''))
    if probe:
        size = ''
        try: size = file.stat().st_size
        except OSError: pass
        print(json.dumps(dict(ref, file=str(file), kind=kind, size=size)))
        return

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                   QPushButton, QPlainTextEdit, QFrame, QGridLayout)
    import ui_style

    name = ref['name']
    description = ref['description'] or {
        'appimage': 'Add this application to your application menu. Your downloaded file will be kept.',
        'flatpakref': 'Install this application and its required runtime.',
        'flatpak': 'Install this application from a local Flatpak bundle.',
        'flatpakrepo': 'Add this software repository for your account.',
        'deb': 'Install this native Debian package on this distribution.',
        'rpm': 'Install this native RPM package on this distribution.'}.get(kind, '')
    icon = ref['icon']
    roots = meta.metadata_roots()

    app = QApplication(sys.argv[:1])
    QIcon.setThemeSearchPaths(QIcon.themeSearchPaths() + [str(r/'icons') for r in roots])

    window = QDialog()
    window.setWindowTitle('AppInstall')
    window.setMinimumWidth(520)
    window.setMaximumWidth(720)
    window.setSizeGripEnabled(True)

    layout = QVBoxLayout(window)
    layout.setContentsMargins(26, 24, 26, 20)
    layout.setSpacing(14)

    header = QHBoxLayout()
    header.setSpacing(16)
    picture = QLabel()
    image = QIcon(icon) if icon and Path(icon).is_file() else QIcon.fromTheme(icon or ref['appid'])
    if image.isNull():
        image = QIcon.fromTheme('package-x-generic')
    picture.setPixmap(image.pixmap(88, 88))
    picture.setFixedSize(92, 92)
    picture.setAlignment(Qt.AlignCenter)
    header.addWidget(picture, 0, Qt.AlignTop)
    text = QVBoxLayout()
    text.setSpacing(4)
    title = QLabel(name)
    title.setTextFormat(Qt.PlainText)
    title.setWordWrap(True)
    title.setStyleSheet('font-size: 20px; font-weight: 700;')
    text.addWidget(title)
    subtitle = QLabel({'flatpakref': 'Flatpak application', 'flatpak': 'Flatpak bundle',
                       'appimage': 'AppImage application', 'flatpakrepo': 'Software repository',
                       'deb': 'Debian package', 'rpm': 'RPM package'}.get(kind, kind))
    subtitle.setTextFormat(Qt.PlainText)
    subtitle.setStyleSheet('color: palette(mid);')
    text.addWidget(subtitle)
    try: size_text = meta.human_size(file.stat().st_size)
    except OSError: size_text = ''
    facts = QGridLayout()
    facts.setHorizontalSpacing(16)
    facts.setVerticalSpacing(3)
    facts.setContentsMargins(0, 4, 0, 0)
    rows = [('Format', kind), ('Size', size_text or '—'),
            ('Destination', 'System-wide — administrator required' if kind in ('deb', 'rpm') else 'Install for your account')]
    for row, (label, value) in enumerate(rows):
        key = QLabel(label)
        key.setStyleSheet('color: palette(mid);')
        facts.addWidget(key, row, 0)
        entry = QLabel(value)
        entry.setTextFormat(Qt.PlainText)
        entry.setWordWrap(True)
        facts.addWidget(entry, row, 1)
    facts.setColumnStretch(1, 1)
    text.addLayout(facts)
    header.addLayout(text, 1)
    layout.addLayout(header)

    body = QLabel(description.strip())
    body.setTextFormat(Qt.PlainText)
    body.setWordWrap(True)
    layout.addWidget(body)

    notice = QLabel('Only install applications from sources you trust. DEB/RPM packages run '
                    'their package scripts inside their matching container; containers are '
                    'not security sandboxes.' if kind in ('deb', 'rpm') else
                    'Only install applications from sources you trust.')
    notice.setWordWrap(True)
    notice.setStyleSheet('color: palette(mid);')
    layout.addWidget(notice)

    line = QFrame(); line.setFrameShape(QFrame.HLine)
    layout.addWidget(line)

    toggle = QPushButton('Show details')
    toggle.setFlat(True)
    toggle.setCursor(Qt.PointingHandCursor)
    layout.addWidget(toggle, 0, Qt.AlignLeft)
    extra = QPlainTextEdit()
    extra.setReadOnly(True)
    extra.setPlainText(str(file)+'\n'+details)
    extra.setFont(QApplication.font('QPlainTextEdit'))
    extra.setMaximumHeight(140)
    extra.hide()
    layout.addWidget(extra)

    def expand():
        extra.setVisible(not extra.isVisible())
        toggle.setText('Hide details' if extra.isVisible() else 'Show details')
        window.adjustSize()
    toggle.clicked.connect(expand)

    buttons = QHBoxLayout()
    buttons.setSpacing(10)
    diagnostics = QPushButton('Application Diagnostics')
    def show_diagnostics():
        import subprocess
        subprocess.Popen([sys.executable, str(Path(__file__).with_name('diagnostics_ui.py'))],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    diagnostics.clicked.connect(show_diagnostics)
    buttons.addWidget(diagnostics)
    buttons.addStretch(1)
    cancel = QPushButton('&Cancel')
    cancel.clicked.connect(window.reject)
    buttons.addWidget(cancel)
    install = QPushButton('Add repo&sitory' if kind == 'flatpakrepo' else '&Install')
    install.setObjectName('primary')
    install.setDefault(True)
    install.clicked.connect(window.accept)
    buttons.addWidget(install)
    layout.addLayout(buttons)
    window.setStyleSheet(window.styleSheet() + ui_style.primary_button_stylesheet(install))

    window.adjustSize()
    sys.exit(0 if window.exec() == QDialog.Accepted else 1)


def entry():
    try:
        main()
    except ImportError as error:
        print('PySide6 is required for the package details window: '+str(error), file=sys.stderr)
        sys.exit(3)
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc()
        sys.exit(2)


if __name__ == '__main__':
    entry()
