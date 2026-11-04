"""Shared installation result windows: success, failure and focused reviews."""
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QPlainTextEdit, QFrame)
import ui_style


def icon_for(_name='', icon_name=''):
    image = QIcon.fromTheme(icon_name)
    if image.isNull():
        image = QIcon.fromTheme('package-x-generic')
    return image


class SuccessDialog(QDialog):
    def __init__(self, name, description='', open_action=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('AppInstall — Installation Complete')
        self.setMinimumWidth(420)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(14)
        header = QHBoxLayout()
        header.setSpacing(16)
        picture = QLabel()
        picture.setPixmap(icon_for(name, icon_name=name.casefold().replace(' ', '-')).pixmap(80, 80))
        picture.setFixedSize(84, 84)
        picture.setAlignment(Qt.AlignCenter)
        header.addWidget(picture, 0, Qt.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(4)
        banner = QLabel('Installation Complete')
        banner.setTextFormat(Qt.PlainText)
        banner.setStyleSheet('font-size: 19px; font-weight: 700;')
        text.addWidget(banner)
        who = QLabel(name)
        who.setTextFormat(Qt.PlainText)
        who.setWordWrap(True)
        font = who.font(); font.setPointSizeF(font.pointSizeF()*1.05); who.setFont(font)
        text.addWidget(who)
        if description:
            note = QLabel(description)
            note.setWordWrap(True)
            note.setStyleSheet('color: palette(mid);')
            text.addWidget(note)
        header.addLayout(text, 1)
        layout.addLayout(header)
        line = QFrame(); line.setFrameShape(QFrame.HLine); layout.addWidget(line)
        buttons = QHBoxLayout(); buttons.setSpacing(10)
        buttons.addStretch(1)
        done = QPushButton('&Done')
        done.setObjectName('ghost')
        if open_action:
            open_button = QPushButton('&Open Application')
            open_button.setObjectName('primary')
            open_button.setDefault(True)
            open_button.clicked.connect(lambda: (self.accept(), open_action()))
            buttons.addWidget(open_button)
        done.clicked.connect(self.accept)
        buttons.addWidget(done)
        layout.addLayout(buttons)
        self.setStyleSheet(ui_style.primary_button_stylesheet(self) + ui_style.ghost_button_stylesheet(self))


class FailureDialog(QDialog):
    """Install/repair failure review. Retry is only enabled when the caller proved it safe."""
    def __init__(self, name, category, explanation='', technical='', logs='', retry=None, parent=None, headline=None):
        super().__init__(parent)
        self.setWindowTitle('AppInstall — Could not finish')
        self.resize(560, 460)
        self.setModal(True)
        self.details = (name+'\n'+category+'\n'+explanation+'\n'+technical).strip()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(12)
        title = QLabel(headline if headline is not None else name+' could not be installed')
        title.setObjectName('failure-headline')
        title.setTextFormat(Qt.PlainText)
        title.setWordWrap(True)
        title.setStyleSheet('font-size: 18px; font-weight: 700;')
        layout.addWidget(title)
        kind = QLabel('Problem type: '+category)
        kind.setTextFormat(Qt.PlainText)
        kind.setObjectName('failure-category')
        kind.setStyleSheet('color: palette(window-text);')
        layout.addWidget(kind)
        body = QPlainTextEdit()
        body.setReadOnly(True)
        body.setPlainText((explanation+'\n\n'+technical).strip())
        body.setMaximumHeight(150)
        layout.addWidget(body)
        buttons = QHBoxLayout(); buttons.setSpacing(10)
        if logs:
            view = QPushButton('View &Logs')
            def show_logs():
                window = QDialog(self)
                window.setWindowTitle('AppInstall — Logs')
                window.resize(700, 480)
                text = QPlainTextEdit(); text.setReadOnly(True); text.setPlainText(logs)
                rows = QVBoxLayout(window)
                rows.addWidget(text)
                close = QPushButton('Close'); close.clicked.connect(window.accept); rows.addWidget(close)
                window.show()
            view.clicked.connect(show_logs)
            buttons.addWidget(view)
        copy = QPushButton('&Copy Details')
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.details))
        buttons.addWidget(copy)
        if retry is not None:
            again = QPushButton('&Retry')
            again.clicked.connect(lambda: (self.accept(), retry()))
            buttons.addWidget(again)
        buttons.addStretch(1)
        close = QPushButton('&Close')
        close.setObjectName('ghost')
        close.setDefault(True)
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.setStyleSheet(ui_style.primary_button_stylesheet(self) + ui_style.ghost_button_stylesheet(self))


def show_success_blocking(name, description='', open_action=None):
    window = SuccessDialog(name, description, open_action)
    window.exec()
