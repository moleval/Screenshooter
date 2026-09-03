"""Application-wide global screenshot hotkeys."""

import keyboard
import win32gui
from PyQt5.QtCore import QObject, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QDialog
from .capture.screen_overlay import ScreenCaptureOverlay
from .capture.region_overlay import RegionCaptureOverlay
from .capture.window_capture import capture_active_window


class HotkeyManager(QObject):
    _monitor_requested = pyqtSignal()
    _window_requested = pyqtSignal(object)
    _region_requested = pyqtSignal()

    def __init__(self, window_manager, parent=None):
        super().__init__(parent)
        self.window_manager = window_manager
        self._capturing = False
        self._hooks = []
        self._hidden_windows = []
        self._last_external_hwnd = None
        self._request_pending = False
        self._monitor_requested.connect(self._capture_monitor)
        self._window_requested.connect(self._capture_window)
        self._region_requested.connect(self._capture_region)
        self._register()

    def _register(self):
        self._hooks = [
            ("hotkey", keyboard.add_hotkey(
                "alt+print screen", self._on_alt,
                suppress=True, trigger_on_release=False)),
            ("hotkey", keyboard.add_hotkey(
                "ctrl+print screen", self._on_ctrl,
                suppress=True, trigger_on_release=False)),
            ("hotkey", keyboard.add_hotkey(
                "print screen", self._on_print,
                suppress=True, trigger_on_release=False)),
        ]

    def _on_print(self):
        if self._request_pending:
            return
        self._request_pending = True
        self._monitor_requested.emit()

    def _find_top_external_window(self, exclude_hwnds):
        """Find top-most visible window that is not in exclude_hwnds.

        EnumWindows enumerates top-level windows from top to bottom, so
        the first visible non-app window with a non-empty title is a good
        candidate for an external target.
        """
        found = {"hwnd": None}

        def _enum(hwnd, lparam):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                if hwnd in exclude_hwnds:
                    return True
                text = win32gui.GetWindowText(hwnd)
                if text and not text.isspace():
                    found["hwnd"] = hwnd
                    return False
            except Exception:
                # ignore windows we can't query
                return True
            return True

        try:
            win32gui.EnumWindows(_enum, None)
        except Exception:
            pass
        return found["hwnd"]

    def _on_alt(self):
        if self._request_pending:
            return
        self._request_pending = True
        hwnd = win32gui.GetForegroundWindow()
        app_hwnds = {int(w.winId()) for w in self.window_manager.windows}
        # Prefer the current foreground if it's external, otherwise try to
        # find the top-most external window. This avoids capturing the app
        # itself when the app holds focus.
        if hwnd and hwnd not in app_hwnds:
            self._last_external_hwnd = hwnd
        else:
            fallback = self._find_top_external_window(app_hwnds)
            if fallback:
                self._last_external_hwnd = fallback
        self._window_requested.emit(self._last_external_hwnd)

    def _on_ctrl(self):
        if self._request_pending:
            return
        self._request_pending = True
        self._region_requested.emit()

    def _begin(self):
        if self._capturing:
            return False
        self._capturing = True
        self._hidden_windows = []
        for window in self.window_manager.windows:
            if window.isVisible():
                self._hidden_windows.append((window, window.isMinimized()))
                window.hide()
        QApplication.processEvents()
        return True

    def _finish(self, target=None):
        self._capturing = False
        for window, was_minimized in self._hidden_windows:
            if not was_minimized:
                window.show()
        self._hidden_windows = []
        window = target or self.window_manager.active_window
        if window:
            if window.isMinimized():
                if window.windowState() & Qt.WindowMaximized:
                    window.showMaximized()
                else:
                    window.showNormal()
            elif not window.isVisible():
                window.show()
            window.raise_()
            window.activateWindow()

    def _capture_pixmap(self, capture_type, hwnd=None):
        if capture_type == "active_window":
            return capture_active_window(hwnd)
        if capture_type == "monitor":
            overlay = ScreenCaptureOverlay()
        else:
            overlay = RegionCaptureOverlay()
        overlay.activateWindow()
        overlay.raise_()
        QApplication.processEvents()
        return overlay.get_pixmap() if overlay.exec_() == QDialog.Accepted else None

    @staticmethod
    def _deliver(target, pixmap):
        if target.is_empty():
            target.view.set_background_from_pixmap(pixmap)
        else:
            target.view.add_pasted_image(pixmap)

    def _target(self):
        return self.window_manager.find_target_window_for_reuse()

    def capture_specific_screen(self, screen):
        """Захватывает выбранный монитор по общей логике распределения окон."""
        if not self._begin():
            return
        QTimer.singleShot(50, lambda: self._capture_specific_screen(screen))

    def _capture_specific_screen(self, screen):
        target = None
        try:
            target = self._target()
            pixmap = screen.grabWindow(0)
            if not pixmap.isNull():
                target = target or self.window_manager.create_editor_window(reusable=False)
                self._deliver(target, pixmap)
        except Exception as error:
            print(f"Ошибка захвата выбранного экрана: {error}")
        finally:
            self._finish(target)

    @pyqtSlot()
    def _capture_monitor(self):
        if not self._begin():
            self._request_pending = False
            return
        target = None
        try:
            target = self._target()
            pixmap = self._capture_pixmap("monitor")
            if pixmap is not None:
                target = target or self.window_manager.create_editor_window(reusable=False)
                self._deliver(target, pixmap)
        except Exception as error:
            print(f"Ошибка захвата экрана: {error}")
        finally:
            self._finish(target)
            self._request_pending = False

    @pyqtSlot(object)
    def _capture_window(self, hwnd):
        if not self._begin():
            self._request_pending = False
            return
        target = None
        try:
            app_hwnds = {int(window.winId()) for window in self.window_manager.windows}
            if hwnd in app_hwnds:
                hwnd = None
            if hwnd is None:
                QApplication.processEvents()
                foreground_hwnd = win32gui.GetForegroundWindow()
                if foreground_hwnd and foreground_hwnd not in app_hwnds:
                    hwnd = foreground_hwnd
            if hwnd in app_hwnds:
                hwnd = None
            target = self._target()
            pixmap = self._capture_pixmap("active_window", hwnd)
            if pixmap is not None:
                target = target or self.window_manager.create_editor_window(reusable=False)
                self._deliver(target, pixmap)
        except Exception as error:
            print(f"Ошибка захвата окна: {error}")
        finally:
            self._finish(target)
            self._request_pending = False

    @pyqtSlot()
    def _capture_region(self):
        if not self._begin():
            self._request_pending = False
            return
        target = None
        try:
            target = self._target()
            pixmap = self._capture_pixmap("region")
            if pixmap is not None:
                target = target or self.window_manager.create_editor_window(reusable=False)
                self._deliver(target, pixmap)
        except Exception as error:
            print(f"Ошибка захвата области: {error}")
        finally:
            self._finish(target)
            self._request_pending = False

    def cleanup(self):
        for hook_type, hook in self._hooks:
            if hook_type == "hotkey":
                keyboard.remove_hotkey(hook)
        self._hooks.clear()
