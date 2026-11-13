"""Shared visual theme for AppInstall dialogs. Follows the system palette."""
import os

from qt_compat import QtGui
QColor = QtGui.QColor
QPalette = QtGui.QPalette


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


def maybe_dark(app):
    """Force Fusion + dark palette when APPINSTALL_UI_DARK=1; native detection otherwise."""
    if os.environ.get('APPINSTALL_UI_DARK') != '1':
        return
    app.setStyle('Fusion')
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
    app.setPalette(palette)


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
