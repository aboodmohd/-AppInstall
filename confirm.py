#!/usr/bin/env python3
"""Optional Qt confirmation, using local metadata without executing packages."""
import configparser
import os
from pathlib import Path
import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QFrame

file = Path(sys.argv[1])
kind, details = sys.argv[2:4]
def values(path, section):
    p = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        p.read(path)
        return dict(p[section])
    except (OSError, KeyError, configparser.Error):
        return {}

ref = values(file, 'Flatpak Ref') if kind == 'flatpakref' else {}
appid = ref.get('name', '')
name = appid.rsplit('.', 1)[-1] if appid else file.stem
description = ref.get('comment', ref.get('description', ''))
if kind in ('deb', 'rpm'):
    import json
    native = json.loads(details)
    name = native['name'] + ' ' + native['version']
    description = native['description']
icon = ref.get('icon', '')
roots = [Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share')), Path.home()/'.local/share/flatpak/exports/share', Path('/var/lib/flatpak/exports/share'), Path('/usr/share')]
for root in roots:
    if not appid:
        break
    meta = values(root/'applications'/f'{appid}.desktop', 'Desktop Entry')
    if meta:
        name = meta.get('name', name)
        description = meta.get('comment', description)
        icon = meta.get('icon', icon)
        break
# Fetch display metadata only for known Flathub references; offline/local metadata remains usable.
if kind == 'flatpakref' and appid:
    from urllib.parse import urlparse, quote
    from urllib.request import urlopen
    import json
    import re
    if urlparse(ref.get('url', '')).hostname in ('dl.flathub.org', 'flathub.org') and re.fullmatch(r'[A-Za-z0-9_.-]+', appid):
        try:
            cache = Path(os.environ.get('XDG_CACHE_HOME', Path.home()/'.cache'))/'appinstall'
            cache.mkdir(parents=True, exist_ok=True)
            record = cache/(appid+'.json')
            if record.exists():
                metadata = json.loads(record.read_text())
            else:
                with urlopen('https://flathub.org/api/v2/appstream/'+quote(appid), timeout=3) as response:
                    metadata = json.loads(response.read(1024*1024))
                record.write_text(json.dumps(metadata))
            name = metadata.get('name') or name
            description = metadata.get('summary') or description
            iconurl = metadata.get('icon', '')
            if urlparse(iconurl).hostname == 'dl.flathub.org' and iconurl.startswith('https://'):
                cached_icon = cache/(appid+'.png')
                if not cached_icon.exists():
                    with urlopen(iconurl, timeout=3) as response:
                        imagebytes = response.read(2*1024*1024)
                    cached_icon.write_bytes(imagebytes)
                icon = str(cached_icon)
        except Exception:
            pass
if not description:
    description = {'appimage':'Add this application to your application menu. Your downloaded file will be kept.', 'flatpakref':'Install this application and its required runtime.', 'flatpak':'Install this application from a local Flatpak bundle.', 'flatpakrepo':'Add this software repository for your user account.'}.get(kind, '')
app = QApplication(sys.argv)
QIcon.setThemeSearchPaths(QIcon.themeSearchPaths() + [str(r/'icons') for r in roots])
window = QDialog()
window.setWindowTitle('AppInstall')
window.setMinimumWidth(480)
window.setMaximumWidth(600)
layout = QVBoxLayout(window)
layout.setContentsMargins(28,28,28,24)
layout.setSpacing(18)
header = QHBoxLayout()
picture = QLabel()
image = QIcon(icon) if icon and Path(icon).is_file() else QIcon.fromTheme(icon or appid)
if image.isNull():
    image = QIcon.fromTheme('package-x-generic')
picture.setPixmap(image.pixmap(72,72))
picture.setFixedSize(80,80)
header.addWidget(picture)
text = QVBoxLayout()
title = QLabel(name)
title.setTextFormat(Qt.PlainText)
font = title.font(); font.setPointSize(20); font.setBold(True); title.setFont(font)
text.addWidget(title)
subtitle = QLabel({'flatpakref':'Flatpak application', 'flatpak':'Flatpak bundle', 'appimage':'AppImage application', 'flatpakrepo':'Software repository'}.get(kind, kind))
text.addWidget(subtitle)
header.addLayout(text, 1)
layout.addLayout(header)
body = QLabel(description)
body.setTextFormat(Qt.PlainText)
body.setWordWrap(True)
layout.addWidget(body)
line = QFrame(); line.setFrameShape(QFrame.HLine); layout.addWidget(line)
location = QLabel('System-wide — administrator required' if kind in ('deb','rpm') else 'Install for your account')
layout.addWidget(location)
trust = QLabel('Only install applications from sources you trust.')
trust.setWordWrap(True); layout.addWidget(trust)
toggle = QPushButton('Show details')
toggle.setFlat(True)
layout.addWidget(toggle, alignment=Qt.AlignLeft)
extra = QTextEdit(); extra.setReadOnly(True); extra.setPlainText(str(file)+'\n'+details); extra.setMaximumHeight(130); extra.hide()
layout.addWidget(extra)
def expand():
    extra.setVisible(not extra.isVisible())
    toggle.setText('Hide details' if extra.isVisible() else 'Show details')
    window.adjustSize()
toggle.clicked.connect(expand)
buttons = QHBoxLayout(); buttons.addStretch()
cancel = QPushButton('Cancel'); cancel.clicked.connect(window.reject); buttons.addWidget(cancel)
install = QPushButton('Add repository' if kind == 'flatpakrepo' else 'Install'); install.setDefault(True); install.clicked.connect(window.accept); buttons.addWidget(install)
layout.addLayout(buttons)
diagnostics = QPushButton('Application Diagnostics')
def show_diagnostics():
    import subprocess
    subprocess.Popen([sys.executable, str(Path(__file__).with_name('diagnostics_ui.py'))])
diagnostics.clicked.connect(show_diagnostics)
layout.addWidget(diagnostics)
sys.exit(0 if window.exec() == QDialog.Accepted else 1)
