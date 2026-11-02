"""Shared visual theme for AppInstall dialogs. Follows the system palette."""
from PySide6.QtGui import QColor, QPalette


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
