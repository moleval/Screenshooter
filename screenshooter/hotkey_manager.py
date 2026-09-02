"""Application-wide global screenshot hotkeys."""

import keyboard
import win32gui
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
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
            ("hook", keyboard.hook_key(
                "print screen", self._on_print, suppress=True)),
        ]

    def _on_print(self, event):
        if event.event_type == keyboard.KEY_DOWN and not keyboard.is_pressed("alt") and not keyboard.is_pressed("ctrl"):
            self._monitor_requested.emit()
        return True

    def _on_alt(self):
        hwnd = win32gui.GetForegroundWindow()
        app_hwnds = {int(w.winId()) for w in self.window_manager.windows}
        if hwnd and hwnd not in app_hwnds:
            self._last_external_hwnd = hwnd
        self._window_requested.emit(self._last_external_hwnd)

    def _on_ctrl(self):
        self._region_requested.emit()

    def _begin(self):
        if self._capturing:
            return False
        self._capturing = True
        self._hidden_windows = []
        for window in self.window_manager.windows:
            if window.isVisible():
                self._hidden_windows.append(window)
                window.hide()
        return True

    def _finish(self):
        self._capturing = False
        for window in self._hidden_windows:
            window.show()
        self._hidden_windows = []
        active = self.window_manager.active_window
        if active:
            active.raise_()
            active.activateWindow()

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

    @pyqtSlot()
    def _capture_monitor(self):
        if not self._begin():
            return
        try:
            target = self._target()
            pixmap = self._capture_pixmap("monitor")
            if pixmap is not None:
                target = target or self.window_manager.create_editor_window()
                self._deliver(target, pixmap)
        finally:
            self._finish()

    @pyqtSlot(object)
    def _capture_window(self, hwnd):
        if not self._begin():
            return
        try:
            target = self._target()
            pixmap = self._capture_pixmap("active_window", hwnd)
            if pixmap is not None:
                target = target or self.window_manager.create_editor_window()
                self._deliver(target, pixmap)
        finally:
            self._finish()

    @pyqtSlot()
    def _capture_region(self):
        if not self._begin():
            return
        try:
            target = self._target()
            pixmap = self._capture_pixmap("region")
            if pixmap is not None:
                target = target or self.window_manager.create_editor_window()
                self._deliver(target, pixmap)
        finally:
            self._finish()

    def cleanup(self):
        for hook_type, hook in self._hooks:
            if hook_type == "hotkey":
                keyboard.remove_hotkey(hook)
            else:
                keyboard.unhook_key(hook)
        self._hooks.clear()
