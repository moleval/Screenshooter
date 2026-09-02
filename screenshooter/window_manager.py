"""Registry and lifecycle management for editor windows."""

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication


class WindowManager(QObject):
    window_activated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._windows = []
        self._active_window = None
        self._next_window_number = 1

    @property
    def windows(self):
        return tuple(self._windows)

    @property
    def active_window(self):
        return self._active_window

    def add_window(self, window, reusable=True):
        if window not in self._windows:
            self._windows.append(window)
            window._auto_reuse_enabled = reusable
            window_number = self._next_window_number
            self._next_window_number += 1
            window._window_number = window_number
            window.setWindowTitle(f"Скриншотер с редактором — Окно {window_number}")
            event_filter = _WindowEventFilter(self, window)
            window.installEventFilter(event_filter)
            window._window_manager_event_filter = event_filter
        self.set_active_window(window)

    def remove_window(self, window):
        if window in self._windows:
            self._windows.remove(window)
        if self._active_window is window:
            self._active_window = self._windows[-1] if self._windows else None
        if not self._windows:
            QApplication.quit()

    def set_active_window(self, window):
        if window in self._windows:
            self._active_window = window
            self._windows.remove(window)
            self._windows.append(window)
            self.window_activated.emit(window)

    @staticmethod
    def mark_window_reusable(window):
        """Возвращает окно в автоматический цикл после очистки сцены."""
        window._auto_reuse_enabled = True

    def find_target_window_for_reuse(self):
        eligible = [w for w in reversed(self._windows)
                    if getattr(w, "_auto_reuse_enabled", True)]
        empty = [w for w in eligible if w.is_empty()]
        if empty:
            return empty[0]
        available = [w for w in eligible
                     if w.has_no_pasted_images()]
        return available[0] if available else None

    def create_editor_window(self, reusable=True):
        from .app import ScreenshotApp
        window = ScreenshotApp()
        window._window_manager = self
        self.add_window(window, reusable=reusable)
        window.show()
        return window


class _WindowEventFilter(QObject):
    def __init__(self, manager, window):
        super().__init__(window)
        self.manager = manager
        self.window = window

    def eventFilter(self, watched, event):
        from PyQt5.QtCore import QEvent
        if watched is self.window:
            if event.type() == QEvent.WindowActivate:
                self.manager.set_active_window(self.window)
            elif event.type() == QEvent.Close:
                self.manager.remove_window(self.window)
        return False
