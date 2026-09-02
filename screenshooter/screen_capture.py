"""
Модуль: screen_capture.py
Описание: Захват экрана через Win32 API и Qt.
          Поддерживает захват монитора, активного окна и выделенной области.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog

from .capture.screen_overlay import ScreenCaptureOverlay
from .capture.region_overlay import RegionCaptureOverlay
from .capture.window_capture import capture_active_window


class ScreenCapture:
    """
    Управляет захватом экрана:
    - весь монитор
    - активное окно
    - выделенная область
    """

    def __init__(self):
        self._capture_in_progress = False

    def is_capturing(self):
        return self._capture_in_progress

    def capture_monitor(self):
        """Захватывает весь монитор через полноэкранный оверлей."""
        if self._capture_in_progress:
            return None
        self._capture_in_progress = True
        try:
            overlay = ScreenCaptureOverlay()
            overlay.activateWindow()
            overlay.raise_()
            QApplication.processEvents()
            if overlay.exec_() == QDialog.Accepted:
                return overlay.get_pixmap()
            return None
        finally:
            self._capture_in_progress = False

    def capture_screen(self):
        """Захватывает основной монитор без оверлея."""
        screen = QApplication.primaryScreen()
        return screen.grabWindow(0) if screen else None

    def capture_region(self):
        """Захватывает выделенную область."""
        if self._capture_in_progress:
            return None
        self._capture_in_progress = True
        try:
            overlay = RegionCaptureOverlay()
            overlay.activateWindow()
            overlay.raise_()
            QApplication.processEvents()
            return overlay.get_pixmap() if overlay.exec_() == QDialog.Accepted else None
        finally:
            self._capture_in_progress = False

    def capture_active_window(self, hwnd=None):
        """Захватывает клиентскую область указанного или активного окна."""
        if self._capture_in_progress:
            return None
        self._capture_in_progress = True
        try:
            return capture_active_window(hwnd)
        finally:
            self._capture_in_progress = False