"""Shared visual theme for AppInstall dialogs. Follows the system palette."""
import os

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


def manager_stylesheet(widget):
    """Manager-only visual system, with dark/light colors from the system theme.

    The other dialogs keep their existing native palette. Named selectors avoid
    unexpectedly restyling confirmation and diagnostics windows.
    """
    dark = widget.palette().color(QPalette.ColorRole.Window).lightness() < 125
    if dark:
        bg, surface, elevated = '#15191e', '#1e252c', '#242d36'
        border, muted, text = '#35404b', '#aab6c2', '#f5f8fb'
        subtle, accent_bg, accent_text = '#182c3d', '#204960', '#91dbff'
        success, attention = '#76dab5', '#ffb86b'
    else:
        bg, surface, elevated = '#f4f7fa', '#ffffff', '#f0f4f8'
        border, muted, text = '#dce5ed', '#647487', '#172636'
        subtle, accent_bg, accent_text = '#ecf5fc', '#dceffe', '#156494'
        success, attention = '#167f5f', '#ab5815'
    return f"""
    QWidget#managerRoot {{
        background-color: {bg};
        color: {text};
    }}
    QLabel#brandMark {{
        color: {accent_text};
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 1px;
    }}
    QLabel#overline, QLabel#sectionCaption {{
        color: {muted};
        font-size: 11px;
        font-weight: 600;
    }}
    QLabel#heroTitle {{
        color: {text};
        font-size: 27px;
        font-weight: 750;
    }}
    QLabel#heroSubtitle {{
        color: {muted};
        font-size: 13px;
    }}
    QFrame#heroPanel {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: 16px;
    }}
    QFrame#metricCard {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: 13px;
    }}
    QLabel#metricValue {{
        color: {text};
        font-size: 25px;
        font-weight: 750;
    }}
    QLabel#metricValueReady {{ color: {success}; font-size: 25px; font-weight: 750; }}
    QLabel#metricValueAttention {{ color: {attention}; font-size: 25px; font-weight: 750; }}
    QLabel#metricTitle {{
        color: {muted};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#sectionTitle {{
        color: {text};
        font-size: 17px;
        font-weight: 750;
    }}
    QLineEdit#managerSearch {{
        background-color: {surface};
        color: {text};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 10px 13px;
        selection-background-color: {accent_bg};
        min-height: 18px;
    }}
    QLineEdit#managerSearch:focus {{ border-color: {accent_text}; }}
    QPushButton#refreshButton {{
        background-color: {surface};
        color: {text};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 10px 16px;
        font-weight: 600;
    }}
    QPushButton#refreshButton:hover {{ background-color: {elevated}; border-color: {accent_text}; }}
    QPushButton#filterChip {{
        background-color: {surface};
        color: {muted};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 8px 15px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton#filterChip:hover {{ color: {text}; border-color: {accent_text}; }}
    QPushButton#filterChip:checked {{
        background-color: {accent_bg};
        border-color: {accent_text};
        color: {accent_text};
    }}
    QListWidget#appList {{
        background: transparent;
        border: none;
        outline: none;
    }}
    QListWidget#appList::item {{
        background: transparent;
        border: none;
        padding: 0;
        margin: 0;
    }}
    QFrame#appCard {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: 14px;
    }}
    QFrame#appCard:hover {{ border-color: {accent_text}; background-color: {elevated}; }}
    QLabel#appName {{ color: {text}; font-size: 16px; font-weight: 700; }}
    QLabel#appMeta {{ color: {muted}; font-size: 12px; }}
    QLabel#appStatus {{
        color: {success};
        font-size: 12px;
        font-weight: 650;
    }}
    QLabel#appStatus[attention="true"] {{ color: {attention}; }}
    QLabel#appWarning {{ color: {attention}; font-size: 11px; }}
    QLabel#managerFooter, QLabel#managerEmpty {{
        color: {muted};
        font-size: 12px;
    }}
    QLabel#managerEmpty {{
        background-color: {surface};
        border: 1px dashed {border};
        border-radius: 14px;
        padding: 36px;
        font-size: 14px;
    }}
    QFrame#appCard QPushButton#primary {{
        min-width: 64px;
        padding: 10px 17px;
    }}
    QFrame#appCard QPushButton#ghost {{
        min-width: 54px;
        padding: 9px 14px;
    }}
    """
