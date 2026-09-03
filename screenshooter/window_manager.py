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
        self.tray_manager = None

    @staticmethod
    def build_window_title(window_number):
        return f"Скриншотер {window_number}"

    def toggle_all_windows(self):
        windows = list(self.windows)
        if not windows:
            return

        all_visible = all(window.isVisible() and not window.isMinimized() for window in windows)
        if all_visible:
            for window in windows:
                window.hide()
            return

        for window in windows:
            self._enable_preview_constraints(window)
            if window.isMinimized():
                window.showNormal()
            else:
                window.show()
            self._restore_saved_geometry(window)
            window.raise_()
        self.layout_all_windows(preview=True)

    @staticmethod
    def _enable_preview_constraints(window):
        if not hasattr(window, "_normal_minimum_size"):
            window._normal_minimum_size = window.minimumSize()
        window.setMinimumSize(0, 0)

    @staticmethod
    def restore_normal_constraints(window):
        minimum_size = getattr(window, "_normal_minimum_size", None)
        if minimum_size is not None:
            window.setMinimumSize(minimum_size)
            del window._normal_minimum_size

    def layout_all_windows(self, preview=False):
        windows = sorted(self.windows, key=lambda w: getattr(w, "_window_number", 0) or 0)
        if not windows:
            return

        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        left = rect.left()
        top = rect.top()
        screen_width = rect.width()
        screen_height = rect.height()
        count = len(windows)
        gap = max(8, min(16, min(screen_width, screen_height) // 120))
        aspect = 1030 / 750

        if count == 1:
            outer_width = min(screen_width, int(screen_height * aspect)) * 3 // 5
            outer_height = int(outer_width / aspect)
            positions = [(
                left + (screen_width - outer_width) // 2,
                top + (screen_height - outer_height) // 2,
            )]
        elif count == 2:
            outer_width = min(screen_width // 2, int((screen_height - gap) * aspect / 2))
            outer_height = int(outer_width / aspect)
            positions = [
                (left, top),
                (left, top + outer_height + gap),
            ]
        elif count == 3:
            outer_width = min((screen_width - gap) // 2,
                              int((screen_height - gap) * aspect / 2))
            outer_height = int(outer_width / aspect)
            positions = [
                (left, top),
                (left, top + outer_height + gap),
                (left + outer_width + gap, top + outer_height + gap),
            ]
        elif count == 4:
            outer_width = min((screen_width - gap) // 2,
                              int((screen_height - gap) * aspect / 2))
            outer_height = int(outer_width / aspect)
            positions = [
                (left, top),
                (left + outer_width + gap, top),
                (left + outer_width + gap, top + outer_height + gap),
                (left, top + outer_height + gap),
            ]
        else:
            rows = (count + 1) // 2
            outer_width = min((screen_width - gap) // 2,
                              int((screen_height - gap * (rows - 1))
                                  * aspect / rows))
            outer_height = int(outer_width / aspect)
            positions = []
            for index in range(count):
                row = index // 2
                x = left if index % 2 == 0 else left + outer_width + gap
                positions.append((x, top + row * (outer_height + gap)))

        if preview:
            outer_width = max(1, int(outer_width * 0.72))
            outer_height = max(1, int(outer_height * 0.72))
            if count == 1:
                positions = [(
                    left + (screen_width - outer_width) // 2,
                    top + (screen_height - outer_height) // 2,
                )]
            elif count == 2:
                positions = [
                    (left, top),
                    (left, top + outer_height + gap),
                ]
            elif count == 3:
                positions = [
                    (left, top),
                    (left, top + outer_height + gap),
                    (left + outer_width + gap, top + outer_height + gap),
                ]
            elif count == 4:
                positions = [
                    (left, top),
                    (left + outer_width + gap, top),
                    (left + outer_width + gap, top + outer_height + gap),
                    (left, top + outer_height + gap),
                ]
            else:
                positions = []
                for index in range(count):
                    row = index // 2
                    x = left if index % 2 == 0 else left + outer_width + gap
                    positions.append((x, top + row * (outer_height + gap)))

        def frame_metrics(window):
            try:
                frame = window.frameGeometry()
                content = window.geometry()
                return (
                    frame.width() - content.width(),
                    frame.height() - content.height(),
                    frame.left() - content.left(),
                    frame.top() - content.top(),
                )
            except (AttributeError, RuntimeError):
                return 0, 0, 0, 0

        for window, (outer_x, outer_y) in zip(windows, positions):
            frame_width, frame_height, frame_left, frame_top = frame_metrics(window)
            content_width = max(1, outer_width - max(0, frame_width))
            content_height = max(1, outer_height - max(0, frame_height))
            window.setGeometry(
                outer_x - frame_left,
                outer_y - frame_top,
                content_width,
                content_height,
            )
            window._saved_geometry = window.geometry()

    def _restore_saved_geometry(self, window):
        saved_geometry = getattr(window, "_saved_geometry", None)
        if saved_geometry is not None:
            window.setGeometry(saved_geometry)
            return
        window.resize(window.sizeHint().width(), window.sizeHint().height())

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
            window.setWindowTitle(self.build_window_title(window_number))
            event_filter = _WindowEventFilter(self, window)
            window.installEventFilter(event_filter)
            window._window_manager_event_filter = event_filter
            if self.tray_manager is not None:
                window.tray_manager = self.tray_manager
        self.set_active_window(window)
        if self.tray_manager is not None:
            self.tray_manager.update_windows_menu()

    def remove_window(self, window):
        if window in self._windows:
            self._windows.remove(window)
        if self._active_window is window:
            self._active_window = self._windows[-1] if self._windows else None
        if not self._windows:
            QApplication.quit()
        if self.tray_manager is not None:
            self.tray_manager.update_windows_menu()

    def set_active_window(self, window):
        if window in self._windows:
            self._active_window = window
            self._windows.remove(window)
            self._windows.append(window)
            self.window_activated.emit(window)
            if self.tray_manager is not None:
                self.tray_manager.update_windows_menu()

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

    def create_editor_window(self, reusable=True, show=True):
        from .app import ScreenshotApp
        window = ScreenshotApp()
        window._window_manager = self
        if hasattr(self, "hotkey_manager"):
            window._hotkey_manager = self.hotkey_manager
        self.add_window(window, reusable=reusable)
        if show:
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
