"""
Модуль: screen_capture.py
Описание: Захват экрана через Win32 API и Qt.
          Поддерживает захват монитора, активного окна и выделенной области.
"""

from PyQt5.QtCore import Qt, QTimer
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

    def __init__(self, app):
        self.app = app
        self._capture_in_progress = False
        self._window_state_before_capture = None

    def is_capturing(self):
        return self._capture_in_progress

    def capture_screen(self):
        """Захватывает весь экран через Qt."""
        screen = QApplication.primaryScreen()
        if screen:
            self.app.screenshot_pixmap = screen.grabWindow(0)
            self.app.display_screenshot()

    def capture_monitor(self):
        """Захватывает монитор через полноэкранный оверлей."""
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        try:
            self._window_state_before_capture = self.app.windowState()
            self.app.hide()
            QApplication.processEvents()
            overlay = ScreenCaptureOverlay()
            overlay.activateWindow()
            overlay.raise_()
            QApplication.processEvents()
            res = overlay.exec_()
            self._restore_main_window(force_maximized=True)
            if res == QDialog.Accepted:
                pm = overlay.get_pixmap()
                if pm is not None:
                    self.app.screenshot_pixmap = pm
                    self.app.display_screenshot()
        except Exception as e:
            self._restore_main_window(force_maximized=True)
            print(f"Ошибка захвата монитора: {e}")
        finally:
            self._capture_in_progress = False

    def capture_region(self):
        """Захватывает выделенную область."""
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        try:
            self._window_state_before_capture = self.app.windowState()
            self.app.hide()
            QApplication.processEvents()
            QTimer.singleShot(30, self._start_region_capture)
        except Exception as e:
            self._capture_in_progress = False
            self._restore_main_window()
            print(f"Ошибка запуска захвата области: {e}")

    def _start_region_capture(self):
        """Внутренний метод запуска захвата области."""
        try:
            overlay = RegionCaptureOverlay()
            overlay.activateWindow()
            overlay.raise_()
            QApplication.processEvents()
            res = overlay.exec_()
            self._restore_main_window()
            if res == QDialog.Accepted:
                pm = overlay.get_pixmap()
                if pm is not None:
                    self.app.screenshot_pixmap = pm
                    self.app.display_screenshot()
        except Exception as e:
            self._restore_main_window()
            print(f"Ошибка захвата области: {e}")
        finally:
            self._capture_in_progress = False

    def capture_window(self):
        """Захватывает активное окно."""
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        try:
            self._window_state_before_capture = self.app.windowState()
            self.app.hide()
            QApplication.processEvents()
            pixmap = capture_active_window()
            QTimer.singleShot(0, self._restore_main_window)
            if pixmap is not None:
                self.app.screenshot_pixmap = pixmap
                self.app.display_screenshot()
            else:
                self.app.view.show_status_message("Не удалось захватить активное окно.", 15000)
        except Exception as e:
            QTimer.singleShot(0, self._restore_main_window)
            print(f"Ошибка захвата активного окна: {e}")
            self.app.view.show_status_message("Не удалось захватить активное окно.", 15000)
        finally:
            self._capture_in_progress = False

    def _restore_main_window(self, force_maximized=False):
        """Восстанавливает главное окно после захвата."""
        if force_maximized:
            self.app.showMaximized()
        else:
            if self._window_state_before_capture and (self._window_state_before_capture & Qt.WindowMaximized):
                self.app.showMaximized()
            else:
                self.app.showNormal()
        self.app.activateWindow()
        self.app.raise_()
        QApplication.processEvents()
        self.app.view.setFocus()