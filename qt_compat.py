"""Use the distribution's Qt 6 Python bindings."""
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Signal, Slot
except ModuleNotFoundError as error:
    if error.name != "PySide6":
        raise
    from PyQt6 import QtCore, QtGui, QtWidgets
    from PyQt6.QtCore import pyqtSignal as Signal, pyqtSlot as Slot
