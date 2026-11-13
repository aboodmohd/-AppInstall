"""Shared visual theme for AppInstall dialogs. Follows the system palette."""
import os

from qt_compat import QtGui
import settings
QColor = QtGui.QColor
QPalette = QtGui.QPalette

# Captured on the first apply_theme call so 'auto' can restore the exact
# palette and style the application started with.
_native = None


def accent(widget):
    color = widget.palette().color(QPalette.ColorRole.Highlight)
    if not color.isValid() or color.alpha() == 0:
        return QColor('#2980b9')
    return color


def primary_button_stylesheet(widget):
    """Rounded, accent-filled style for the main action; derived from the system palette."""
    color = accent(widget)
    red, green, blue = color.red(), color.green(), color.blue()
    luminance = 0.299*red + 0.587*green + 0.114*blue
    text = '#14181d' if luminance > 150 else '#ffffff'
    hover = QColor(max(red-18 if red > 18 else red, 0), max(green-18 if green > 18 else green, 0), max(blue-18 if blue > 18 else blue, 0)).name()
    pressed = QColor(min(red+18, 255), min(green+18, 255), min(blue+18, 255)).name()
    return f"""
    QPushButton#primary {{
        background-color: {color.name()};
        color: {text};
        border: none;
        border-radius: 8px;
        padding: 9px 24px;
        font-size: 14px;
        font-weight: 600;
    }}
    QPushButton#primary:hover {{ background-color: {hover}; }}
    QPushButton#primary:pressed {{ background-color: {pressed}; }}
    QPushButton#primary:disabled {{ background-color: palette(mid); color: palette(disabled-text); }}
    """


def _dark_palette():
    palette = QPalette()
    window = QColor(49, 54, 59)
    surface = QColor(42, 46, 50)
    text = QColor(239, 240, 241)
    disabled = QColor(120, 124, 130)
    for role, color in ((QPalette.ColorRole.Window, window),
                        (QPalette.ColorRole.WindowText, text),
                        (QPalette.ColorRole.Base, surface),
                        (QPalette.ColorRole.AlternateBase, window),
                        (QPalette.ColorRole.ToolTipBase, text),
                        (QPalette.ColorRole.ToolTipText, text),
                        (QPalette.ColorRole.Text, text),
                        (QPalette.ColorRole.Button, surface),
                        (QPalette.ColorRole.ButtonText, text),
                        (QPalette.ColorRole.BrightText, QColor(255, 96, 96)),
                        (QPalette.ColorRole.Link, QColor(61, 174, 233)),
                        (QPalette.ColorRole.Highlight, QColor(61, 174, 233)),
                        (QPalette.ColorRole.HighlightedText, QColor(20, 24, 29))):
        palette.setColor(QPalette.ColorGroup.Active, role, color)
        palette.setColor(QPalette.ColorGroup.Inactive, role, color)
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText, QPalette.ColorRole.Text):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return palette


def _light_palette():
    palette = QPalette()
    window = QColor(245, 246, 248)
    surface = QColor(255, 255, 255)
    text = QColor(28, 32, 36)
    disabled = QColor(130, 134, 140)
    for role, color in ((QPalette.ColorRole.Window, window),
                        (QPalette.ColorRole.WindowText, text),
                        (QPalette.ColorRole.Base, surface),
                        (QPalette.ColorRole.AlternateBase, window),
                        (QPalette.ColorRole.ToolTipBase, text),
                        (QPalette.ColorRole.ToolTipText, text),
                        (QPalette.ColorRole.Text, text),
                        (QPalette.ColorRole.Button, surface),
                        (QPalette.ColorRole.ButtonText, text),
                        (QPalette.ColorRole.BrightText, QColor(178, 32, 32)),
                        (QPalette.ColorRole.Link, QColor(41, 128, 185)),
                        (QPalette.ColorRole.Highlight, QColor(41, 128, 185)),
                        (QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))):
        palette.setColor(QPalette.ColorGroup.Active, role, color)
        palette.setColor(QPalette.ColorGroup.Inactive, role, color)
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText, QPalette.ColorRole.Text):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return palette


def apply_theme(app, theme):
    """Apply 'auto', 'light' or 'dark' to a running QApplication.

    'auto' restores the palette and style captured on the first call; 'light'
    and 'dark' force Fusion with an explicit palette so the appearance is
    deterministic on any system theme.
    """
    global _native
    if theme not in ('light', 'dark'):
        theme = 'auto'
    if _native is None:
        _native = (app.style().objectName(), QPalette(app.palette()))
    if theme == 'auto':
        app.setStyle(_native[0])
        app.setPalette(QPalette(_native[1]))
    else:
        app.setStyle('Fusion')
        app.setPalette(_dark_palette() if theme == 'dark' else _light_palette())


def maybe_dark(app):
    """APPINSTALL_UI_DARK=1 forces dark (test/CI override); otherwise the
    saved theme setting applies, falling back to native detection."""
    if os.environ.get('APPINSTALL_UI_DARK') == '1':
        apply_theme(app, 'dark')
        return
    try:
        theme = settings.read().get('theme', 'auto')
    except Exception:
        theme = 'auto'
    apply_theme(app, theme)


def ghost_button_stylesheet(widget):
    """Subtle secondary-action style; uses the system palette for contrast."""
    return """
    QPushButton#ghost, QPlainTextEdit, QPushButton[flat="false"] {
        border-radius: 8px;
        padding: 9px 20px;
    }
    QPushButton#ghost {
        background: palette(button);
        border: 1px solid palette(mid);
    }
    QPushButton#ghost:hover { border-color: palette(highlight); }
    QPlainTextEdit#hidden-logs { font-family: monospace; }
    """


def choose_package(parent):
    """Use Qt's file picker even when no desktop portal is running."""
    from qt_compat import QtWidgets

    dialog = QtWidgets.QFileDialog
    directory = os.path.join(os.path.expanduser('~'), 'Downloads')
    path, _ = dialog.getOpenFileName(
        parent, 'Install Application', directory,
        'Applications (*.AppImage *.appimage *.flatpak *.flatpakref *.flatpakrepo *.deb *.rpm)',
        options=dialog.Option.DontUseNativeDialog,
    )
    return path


def open_package(parent):
    """Route a selected package through the normal CLI review."""
    from pathlib import Path
    import subprocess
    from qt_compat import QtWidgets

    path = choose_package(parent)
    if not path:
        return
    command = Path(__file__).with_name('appinstall')
    if not command.is_file():
        command = Path.home() / '.local/bin/appinstall'
    try:
        subprocess.Popen([str(command), '--', path])
    except OSError as error:
        QtWidgets.QMessageBox.warning(parent, 'AppInstall', str(error))
