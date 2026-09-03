"""Registry and lifecycle management for editor windows."""

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication


class WindowManager(QObject):
    window_activated = pyqtSignal(object)

    # Константы раскладки
    MARGIN = 10
    GAP = 10

    # Прогрессивный шаг лесенки для 5+ окон
    CASCADE_BASE_STEP = 80        # шаг для 5 окон
    CASCADE_STEP_DECREMENT = 10   # уменьшение на каждое дополнительное окно
    CASCADE_MIN_STEP = 25         # минимальный шаг

    # Минимальный размер окна (для каскада)
    MIN_WINDOW_W = 650
    MIN_WINDOW_H = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self._windows = []
        self._active_window = None
        self._next_window_number = 1
        self.tray_manager = None

    @staticmethod
    def build_window_title(window_number):
        return f"Скриншотер {window_number}"

    # ==============================================================
    # Показать / скрыть все окна (вызывается из трея)
    # ==============================================================

    def toggle_all_windows(self):
        windows = list(self.windows)
        if not windows:
            return

        all_visible = all(
            window.isVisible() and not window.isMinimized()
            for window in windows
        )

        if all_visible:
            # Скрываем все окна, сохраняя геометрию каждого
            for window in windows:
                window._saved_geometry = window.geometry()
                window.hide()
            return

        N = len(windows)

        if N == 1:
            # Одно окно: восстанавливаем сохранённую геометрию БЕЗ раскладки
            window = windows[0]
            self.restore_normal_constraints(window)
            if hasattr(window, 'set_preview_mode'):
                window.set_preview_mode(False)
            if window.isMinimized():
                window.showNormal()
            else:
                window.show()
            self._restore_saved_geometry(window)
            window.raise_()
            window.activateWindow()
        else:
            # Несколько окон: показываем без raise_() — порядок установит layout
            for window in windows:
                self._enable_preview_constraints(window)
                if window.isMinimized():
                    window.showNormal()
                else:
                    window.show()
            self.layout_all_windows()

        if self.tray_manager is not None:
            self.tray_manager.update_windows_menu()

    # ==============================================================
    # Разворот одного окна из предпросмотра
    # ==============================================================

    def expand_window(self, window, fullscreen=False):
        """Разворачивает одно окно из предпросмотра в полный режим.

        :param fullscreen: True — развернуть на весь экран (ДЩЛКМ по заголовку),
                           False — переместить в центр (ДЩЛКМ по полю).
        Остальные окна скрываются."""
        if window not in self._windows:
            return

        # Восстанавливаем нормальные ограничения
        self.restore_normal_constraints(window)

        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()

        if fullscreen:
            # ДЩЛКМ по заголовку: развернуть на весь экран
            window.setGeometry(rect)
        else:
            # ДЩЛКМ по полю: переместить в центр, минимальный рабочий размер
            from .ui.layout_metrics import WINDOW_INITIAL_WIDTH, WINDOW_MIN_HEIGHT
            w = min(WINDOW_INITIAL_WIDTH, rect.width() - 2 * self.MARGIN)
            h = min(WINDOW_MIN_HEIGHT, rect.height() - 2 * self.MARGIN)
            x = rect.left() + (rect.width() - w) // 2
            y = rect.top() + (rect.height() - h) // 2
            window.setGeometry(x, y, w, h)

        # Показываем тулбары ПОСЛЕ установки геометрии
        if hasattr(window, 'set_preview_mode'):
            window.set_preview_mode(False)

        window.show()
        window.raise_()
        window.activateWindow()

        # Остальные видимые окна скрываем
        for other in self._windows:
            if other is not window and other.isVisible():
                other._saved_geometry = other.geometry()
                other.hide()

        if self.tray_manager is not None:
            self.tray_manager.update_windows_menu()

    # ==============================================================
    # Ограничения (минимальный размер)
    # ==============================================================

    @staticmethod
    def _enable_preview_constraints(window):
        """Временно снимает минимальные ограничения окна."""
        if not hasattr(window, "_normal_minimum_size"):
            window._normal_minimum_size = window.minimumSize()
        window.setMinimumSize(0, 0)

    @staticmethod
    def restore_normal_constraints(window):
        """Восстанавливает нормальные минимальные ограничения окна."""
        minimum_size = getattr(window, "_normal_minimum_size", None)
        if minimum_size is not None:
            window.setMinimumSize(minimum_size)
            del window._normal_minimum_size

    # ==============================================================
    # Раскладка окон
    # ==============================================================

    def layout_all_windows(self):
        """Раскладывает окна по схеме в зависимости от количества."""
        windows = sorted(
            self.windows,
            key=lambda w: getattr(w, "_window_number", 0) or 0
        )
        if not windows:
            return

        N = len(windows)
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()

        # Определяем режим: 5+ окон = предпросмотр (скрываем тулбары)
        preview_mode = N >= 5
        for window in windows:
            if hasattr(window, 'set_preview_mode'):
                window.set_preview_mode(preview_mode)
            if not preview_mode:
                self.restore_normal_constraints(window)

        # Получаем позиции и размеры по схеме
        if N == 1:
            positions = self._layout_single(rect)
        elif N == 2:
            positions = self._layout_two(rect)
        elif N == 3:
            positions = self._layout_three(rect)
        elif N == 4:
            positions = self._layout_four(rect)
        else:
            positions = self._layout_grid(rect, N)

        # Применяем геометрию
        for window, (x, y, w, h) in zip(windows, positions):
            frame_width, frame_height, frame_left, frame_top = self._frame_metrics(window)
            content_width = max(1, w - max(0, frame_width))
            content_height = max(1, h - max(0, frame_height))
            window.setGeometry(
                x - frame_left,
                y - frame_top,
                content_width,
                content_height,
            )
            window._saved_geometry = window.geometry()

            # Вписываем содержимое в новый размер
            if hasattr(window, 'view') and window.view.background_item:
                window.view.fitInView(window.view.background_item, Qt.KeepAspectRatio)

        # Устанавливаем z-порядок: первое окно внизу, последнее наверху
        for window in windows:
            window.raise_()

    # ==============================================================
    # Схемы раскладки
    # ==============================================================

    def _layout_single(self, rect):
        """1 окно: по центру, минимальный рабочий размер."""
        from .ui.layout_metrics import WINDOW_INITIAL_WIDTH, WINDOW_MIN_HEIGHT

        outer_width = WINDOW_INITIAL_WIDTH
        outer_height = WINDOW_MIN_HEIGHT

        outer_width = min(outer_width, rect.width() - 2 * self.MARGIN)
        outer_height = min(outer_height, rect.height() - 2 * self.MARGIN)

        x = rect.left() + (rect.width() - outer_width) // 2
        y = rect.top() + (rect.height() - outer_height) // 2
        return [(x, y, outer_width, outer_height)]

    def _layout_two(self, rect):
        """2 окна:
        Окно 1 — левый верхний угол окна = левый верхний угол монитора.
        Окно 2 — левый верхний угол окна = середина левого края экрана."""
        from .ui.layout_metrics import WINDOW_INITIAL_WIDTH, WINDOW_MIN_HEIGHT

        w = min(WINDOW_INITIAL_WIDTH, rect.width() - self.MARGIN)
        h = min(WINDOW_MIN_HEIGHT, rect.height() - self.MARGIN)

        return [
            # Окно 1: левый верхний угол монитора
            (rect.left(), rect.top(), w, h),
            # Окно 2: середина левого края
            (rect.left(), rect.top() + rect.height() // 2, w, h),
        ]

    def _layout_three(self, rect):
        """3 окна:
        Окно 1 — левый верхний угол = левый верхний угол монитора.
        Окно 2 — левый верхний угол = середина левого края экрана.
        Окно 3 — ПРАВЫЙ верхний угол = середина правого края."""
        from .ui.layout_metrics import WINDOW_INITIAL_WIDTH, WINDOW_MIN_HEIGHT

        w = min(WINDOW_INITIAL_WIDTH, rect.width() - self.MARGIN)
        h = min(WINDOW_MIN_HEIGHT, rect.height() - self.MARGIN)

        # Центр правой части экрана = 3/4 ширины
        right_center_x = rect.left() + rect.width() * 3 // 4

        return [
            # Окно 1: левый верхний угол монитора
            (rect.left(), rect.top(), w, h),
            # Окно 2: середина левого края
            (rect.left(), rect.top() + rect.height() // 2, w, h),
            # Окно 3: ПРАВЫЙ верхний угол = середина правого края
            (rect.right() - w, rect.top() + rect.height() // 2, w, h),
        ]

    def _layout_four(self, rect):
        """4 окна:
        Окно 1 — левый верхний угол = левый верхний угол монитора.
        Окно 2 — ПРАВЫЙ верхний угол = ПРАВЫЙ ВЕРХНИЙ УГОЛ экрана.
        Окно 3 — левый верхний угол = середина левого края экрана.
        Окно 4 — ПРАВЫЙ верхний угол = середина правого края."""
        from .ui.layout_metrics import WINDOW_INITIAL_WIDTH, WINDOW_MIN_HEIGHT

        w = min(WINDOW_INITIAL_WIDTH, rect.width() - self.MARGIN)
        h = min(WINDOW_MIN_HEIGHT, rect.height() - self.MARGIN)

        # Центр правой части экрана = 3/4 ширины
        right_center_x = rect.left() + rect.width() * 3 // 4

        return [
            # Окно 1: левый верхний угол монитора
            (rect.left(), rect.top(), w, h),
            # Окно 2: ПРАВЫЙ верхний угол = правый верхний угол экрана
            (rect.right() - w, rect.top(), w, h),
            # Окно 3: середина левого края
            (rect.left(), rect.top() + rect.height() // 2, w, h),
            # Окно 4: середина правого края
            (rect.right() - w, rect.top() + rect.height() // 2, w, h),
        ]

    def _layout_grid(self, rect, N):
        """5+ окон: лесенка с прогрессивным шагом."""
        from .ui.layout_metrics import WINDOW_INITIAL_WIDTH, WINDOW_MIN_HEIGHT

        w = min(WINDOW_INITIAL_WIDTH, rect.width() - self.MARGIN)
        h = min(WINDOW_MIN_HEIGHT, rect.height() - self.MARGIN)

        # Прогрессивный шаг: меньше окон — больше отступы
        step = max(
            self.CASCADE_MIN_STEP,
            self.CASCADE_BASE_STEP - (N - 5) * self.CASCADE_STEP_DECREMENT
        )

        positions = []
        for i in range(N):
            x = rect.left() + i * step
            y = rect.top() + i * step

            # Ограничиваем, чтобы окно не выходило за экран
            x = min(x, rect.right() - w)
            y = min(y, rect.bottom() - h)
            x = max(x, rect.left())
            y = max(y, rect.top())

            positions.append((x, y, w, h))

        return positions

    # ==============================================================
    # Вспомогательные
    # ==============================================================

    @staticmethod
    def _frame_metrics(window):
        """Возвращает размеры рамки окна."""
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

    def _restore_saved_geometry(self, window):
        """Восстанавливает сохранённую геометрию окна."""
        saved_geometry = getattr(window, "_saved_geometry", None)
        if saved_geometry is not None:
            window.setGeometry(saved_geometry)
            return
        window.resize(window.sizeHint().width(), window.sizeHint().height())

    # ==============================================================
    # Свойства
    # ==============================================================

    @property
    def windows(self):
        return tuple(self._windows)

    @property
    def active_window(self):
        return self._active_window

    # ==============================================================
    # Управление окнами
    # ==============================================================

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
            return
        if self.tray_manager is not None:
            self.tray_manager.update_windows_menu()

        # Пересчитываем раскладку для оставшихся видимых окон
        visible_windows = [w for w in self._windows if w.isVisible()]
        if visible_windows:
            self.layout_all_windows()

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
    """Фильтр событий для каждого окна приложения."""

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
            elif event.type() == QEvent.MouseButtonDblClick:
                # ДЩЛКМ по полю: переместить в центр
                visible = [w for w in self.manager.windows if w.isVisible()]
                if len(visible) >= 5:
                    self.manager.expand_window(self.window, fullscreen=False)
                    return True
        return False