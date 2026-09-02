"""Registry and lifecycle management for editor windows."""

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication


class WindowManager(QObject):
    window_activated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._windows = []
        self._active_window = None

    @property
    def windows(self):
        return tuple(self._windows)

    @property
    def active_window(self):
        return self._active_window

    def add_window(self, window):
        if window not in self._windows:
            self._windows.append(window)
            window.installEventFilter(_WindowEventFilter(self, window))
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
            self.window_activated.emit(window)

    def find_target_window_for_reuse(self):
        empty = [w for w in reversed(self._windows) if w.is_empty()]
        if empty:
            return empty[0]
        available = [w for w in reversed(self._windows)
                     if w.has_no_pasted_images()]
        return available[0] if available else None

    def create_editor_window(self):
        from .app import ScreenshotApp
        window = ScreenshotApp()
        self.add_window(window)
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
