"""
Модуль: hotkey_manager.py
"""

import os

import keyboard
import win32con
import win32gui
import win32process
from PyQt5.QtCore import QObject, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QDialog

from .capture.screen_overlay import ScreenCaptureOverlay
from .capture.region_overlay import RegionCaptureOverlay
from .capture.window_capture import capture_active_window


class HotkeyManager(QObject):
    _monitor_requested = pyqtSignal()
    _window_requested = pyqtSignal(object)
    _region_requested = pyqtSignal()

    # Задержка (мс) после скрытия окон перед захватом.
    # Даёт системе время переключить фокус и перерисовать экран.
    HIDE_SETTLE_DELAY_MS = 200

    def __init__(self, window_manager, parent=None):
        super().__init__(parent)
        self.window_manager = window_manager
        self._capturing = False
        self._hidden_windows = []
        self._last_external_hwnd = None
        self._request_pending = False
        self._monitor_requested.connect(self._capture_monitor)
        self._window_requested.connect(self._capture_window)
        self._region_requested.connect(self._capture_region)
        self._register()

    # ==============================================================
    # Регистрация / очистка хуков
    # ==============================================================

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

    def cleanup(self):
        for hook_type, hook in self._hooks:
            if hook_type == "hotkey":
                keyboard.remove_hotkey(hook)
        self._hooks.clear()

    # ==============================================================
    # Проверка принадлежности окна текущему процессу
    # ==============================================================

    @staticmethod
    def _is_app_window(hwnd):
        """Возвращает True, если окно принадлежит текущему процессу."""
        if not hwnd:
            return False
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return pid == os.getpid()
        except Exception:
            return False

    # ==============================================================
    # Поиск внешнего окна
    # ==============================================================

    def _find_top_external_window(self):
        """Ищет первое видимое окно с заголовком, не принадлежащее
        текущему процессу.

        EnumWindows перечисляет top-level окна сверху вниз,
        поэтому первое подходящее — верхнее внешнее окно.
        """
        found = {"hwnd": None}
        current_pid = os.getpid()

        def _enum(hwnd, lparam):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                # Фильтрация по PID — отбрасываем окна своего процесса
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid == current_pid:
                    return True
                text = win32gui.GetWindowText(hwnd)
                if text and not text.isspace():
                    found["hwnd"] = hwnd
                    return False  # останавливаем перебор
            except Exception:
                return True
            return True

        try:
            win32gui.EnumWindows(_enum, None)
        except Exception:
            pass
        return found["hwnd"]

    # ==============================================================
    # Обработчики горячих клавиш
    # ==============================================================

    def _on_print(self):
        if self._request_pending:
            return
        self._request_pending = True
        self._monitor_requested.emit()

    def _on_alt(self):
        if self._request_pending:
            return
        self._request_pending = True

        hwnd = win32gui.GetForegroundWindow()

        # Если foreground принадлежит НЕ нашему процессу — используем его
        if hwnd and not self._is_app_window(hwnd):
            self._last_external_hwnd = hwnd
        else:
            # Foreground — наше приложение или пусто.
            # Ищем внешнее окно через перебор.
            fallback = self._find_top_external_window()
            if fallback:
                self._last_external_hwnd = fallback

        self._window_requested.emit(self._last_external_hwnd)

    def _on_ctrl(self):
        if self._request_pending:
            return
        self._request_pending = True
        self._region_requested.emit()

    # ==============================================================
    # Скрытие / восстановление окон приложения
    # ==============================================================

    def _begin(self):
        """Скрывает все видимые окна приложения перед захватом."""
        if self._capturing:
            return False
        self._capturing = True
        self._hidden_windows = []
        for window in self.window_manager.windows:
            if window.isVisible():
                self._hidden_windows.append((window, window.isMinimized()))
                window.hide()

        # Обрабатываем события очереди и сбрасываем буфер отрисовки
        QApplication.processEvents()
        QApplication.flush()

        # Принудительная перерисовка рабочего стола,
        # чтобы убрать «призраки» скрытых окон
        try:
            desktop_hwnd = win32gui.GetDesktopWindow()
            win32gui.RedrawWindow(
                desktop_hwnd, None, None,
                win32con.RDW_INVALIDATE
                | win32con.RDW_UPDATENOW
                | win32con.RDW_ALLCHILDREN,
            )
        except Exception:
            pass

        return True

    def _finish(self, target=None):
        """Восстанавливает окна приложения после захвата."""
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

    # ==============================================================
    # Захват изображения
    # ==============================================================

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

    # ==============================================================
    # Захват выбранного монитора (кнопки «Окно 1», «Окно 2» и т.д.)
    # ==============================================================

    def capture_specific_screen(self, screen):
        if not self._begin():
            return
        QTimer.singleShot(self.HIDE_SETTLE_DELAY_MS,
                          lambda: self._capture_specific_screen(screen))

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

    # ==============================================================
    # Захват монитора (по горячим клавишам)
    # ==============================================================

    @pyqtSlot()
    def _capture_monitor(self):
        if not self._begin():
            self._request_pending = False
            return
        QTimer.singleShot(self.HIDE_SETTLE_DELAY_MS,
                          self._do_capture_monitor)

    def _do_capture_monitor(self):
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

    # ==============================================================
    # Захват окна
    # ==============================================================

    @pyqtSlot(object)
    def _capture_window(self, hwnd):
        if not self._begin():
            self._request_pending = False
            return
        QTimer.singleShot(self.HIDE_SETTLE_DELAY_MS,
                          lambda: self._do_capture_window(hwnd))

    def _do_capture_window(self, hwnd):
        target = None
        try:
            # Защита 1: если переданный hwnd принадлежит нашему процессу — отбрасываем
            if self._is_app_window(hwnd):
                hwnd = None

            # Защита 2: если hwnd не определён — пробуем текущий foreground
            if hwnd is None:
                QApplication.processEvents()
                foreground_hwnd = win32gui.GetForegroundWindow()
                if foreground_hwnd and not self._is_app_window(foreground_hwnd):
                    hwnd = foreground_hwnd

            # Защита 3: если всё ещё наше окно — ищем внешнее через перебор
            if self._is_app_window(hwnd):
                hwnd = self._find_top_external_window()

            # Принудительно переключаем фокус на целевое окно
            if hwnd:
                try:
                    win32gui.SetForegroundWindow(hwnd)
                    QApplication.processEvents()
                except Exception:
                    pass

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

    # ==============================================================
    # Захват области
    # ==============================================================

    @pyqtSlot()
    def _capture_region(self):
        if not self._begin():
            self._request_pending = False
            return
        QTimer.singleShot(self.HIDE_SETTLE_DELAY_MS,
                          self._do_capture_region)

    def _do_capture_region(self):
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