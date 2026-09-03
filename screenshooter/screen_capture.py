"""Координация захвата экрана для одного окна редактора."""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QDialog
import win32gui

from .capture.screen_overlay import ScreenCaptureOverlay
from .capture.region_overlay import RegionCaptureOverlay
from .capture.window_capture import capture_active_window


class ScreenCapture:
    def __init__(self, app):
        self.app = app
        self._capture_in_progress = False
        self._window_state_before_capture = None

    def is_capturing(self):
        return self._capture_in_progress

    def capture_screen(self, screen=None):
        """Захватывает указанный монитор или основной монитор."""
        screen = screen or QApplication.primaryScreen()
        if screen:
            self.app.screenshot_pixmap = screen.grabWindow(0)
            self.app.display_screenshot()

    def capture_monitor(self):
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
            if overlay.exec_() == QDialog.Accepted:
                pm = overlay.get_pixmap()
                if pm is not None:
                    self.app.screenshot_pixmap = pm
                    self.app.display_screenshot()
            self._restore_main_window(force_maximized=True)
        except Exception as e:
            self._restore_main_window(force_maximized=True)
            print(f"Ошибка захвата монитора: {e}")
        finally:
            self._capture_in_progress = False

    def capture_region(self):
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
        try:
            overlay = RegionCaptureOverlay()
            overlay.activateWindow()
            overlay.raise_()
            QApplication.processEvents()
            if overlay.exec_() == QDialog.Accepted:
                pm = overlay.get_pixmap()
                if pm is not None:
                    self.app.screenshot_pixmap = pm
                    self.app.display_screenshot()
            self._restore_main_window()
        except Exception as e:
            self._restore_main_window()
            print(f"Ошибка захвата области: {e}")
        finally:
            self._capture_in_progress = False

    def capture_window(self, hwnd=None):
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        try:
            self._window_state_before_capture = self.app.windowState()
            self.app.hide()
            QApplication.processEvents()
            if hwnd is None:
                window_manager = getattr(self.app, "_window_manager", None)
                app_hwnds = (
                    {int(window.winId()) for window in window_manager.windows}
                    if window_manager is not None else set()
                )
                candidate = win32gui.GetForegroundWindow()
                if candidate and candidate not in app_hwnds:
                    hwnd = candidate
            pixmap = capture_active_window(hwnd)
            self._restore_main_window()
            if pixmap is not None:
                self.app.screenshot_pixmap = pixmap
                self.app.display_screenshot()
            else:
                self.app.view.show_status_message("Не удалось захватить активное окно.", 15000)
        except Exception as e:
            self._restore_main_window()
            print(f"Ошибка захвата активного окна: {e}")
            self.app.view.show_status_message("Не удалось захватить активное окно.", 15000)
        finally:
            self._capture_in_progress = False

    def _restore_main_window(self, force_maximized=False):
        if force_maximized:
            self.app.showMaximized()
        elif self._window_state_before_capture and (self._window_state_before_capture & Qt.WindowMaximized):
            self.app.showMaximized()
        else:
            self.app.showNormal()
        self.app.activateWindow()
        self.app.raise_()
        QApplication.processEvents()
        self.app.view.setFocus()
