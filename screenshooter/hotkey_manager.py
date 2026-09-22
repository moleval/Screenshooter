"""
Модуль: hotkey_manager.py

Мультиоконный режим с корректным восстановлением foreground после захвата.
"""

import os
import threading

import keyboard
import win32api
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

    HIDE_SETTLE_DELAY_MS = 200

    # Только для отладки. True — печатает события Alt/PrintScreen
    # и состояние модификаторов. Обычная работа — False.
    DEBUG = False

    def __init__(self, window_manager, parent=None):
        super().__init__(parent)

        self.window_manager = window_manager

        self._capturing = False
        self._hidden_windows = []
        self._last_external_hwnd = None
        self._request_pending = False

        self._printscreen_down = False
        self._alt_down = False

        self._key_state_lock = threading.Lock()

        self._hooks = []
        self._hotkeys = []

        self._monitor_requested.connect(self._capture_monitor)
        self._window_requested.connect(self._capture_window)
        self._region_requested.connect(self._capture_region)

        self._register()

    # ==============================================================
    # Регистрация / очистка
    # ==============================================================

    def _register(self):
        # Hook нужен для защиты от повторной обработки PrintScreen
        # и для отслеживания состояния Alt.
        h = keyboard.hook(self._keyboard_event)
        self._hooks.append(("keyboard", h))

        # Прямая регистрация Alt+PrintScreen.
        # На Windows PrintScreen в комбинации с Alt приходит
        # как scan code 0x54 (SysRq), и имя в hook — 'sys req'.
        # Поэтому hook-only детекция ненадёжна, используем add_hotkey.
        try:
            hk = keyboard.add_hotkey(
                "alt+print screen",
                self._on_alt_printscreen_hotkey,
                suppress=False,
                trigger_on_release=False,
            )
            self._hotkeys.append(("alt+print screen", hk))
            if self.DEBUG:
                print("[HOTKEY] registered: alt+print screen")
        except Exception as error:
            print(f"[HOTKEY] failed to register alt+print screen: {error}")

    def _on_alt_printscreen_hotkey(self):
        if self.DEBUG:
            print("[HOTKEY] alt+print screen FIRED")

        if self._request_pending:
            return

        self._request_pending = True
        self._prepare_window_capture()

    def cleanup(self):
        for _, hk in self._hotkeys:
            try:
                keyboard.remove_hotkey(hk)
            except Exception:
                pass
        self._hotkeys = []

        for htype, hook in self._hooks:
            if htype == "keyboard":
                try:
                    keyboard.unhook(hook)
                except Exception:
                    pass
        self._hooks = []

        with self._key_state_lock:
            self._printscreen_down = False
            self._alt_down = False

        self._request_pending = False

    # ==============================================================
    # Keyboard hook
    # ==============================================================

    def _keyboard_event(self, event):
        key = str(event.name).lower().strip()

        # --- Alt ---
        if key in ("alt", "left alt", "right alt", "alt gr"):
            if self.DEBUG:
                print(f"[HOOK] {event.name} "
                      f"{'DOWN' if event.event_type == keyboard.KEY_DOWN else 'UP'}")
            with self._key_state_lock:
                if event.event_type == keyboard.KEY_DOWN:
                    self._alt_down = True
                elif event.event_type == keyboard.KEY_UP:
                    self._alt_down = False
            return

        # --- PrintScreen / SysRq ---
        if key not in ("print screen", "printscreen", "prtsc", "prtscr", "sys req"):
            return

        if self.DEBUG:
            print(f"[HOOK] {event.name} "
                  f"{'DOWN' if event.event_type == keyboard.KEY_DOWN else 'UP'}")

        if event.event_type == keyboard.KEY_DOWN:
            # 'sys req' приходит, когда PrintScreen нажат вместе с Alt.
            # Обрабатываем только чистый PrintScreen здесь;
            # Alt+PrintScreen обрабатывается через add_hotkey.
            if key == "sys req":
                return
            self._handle_printscreen_down()

        elif event.event_type == keyboard.KEY_UP:
            with self._key_state_lock:
                self._printscreen_down = False

    @staticmethod
    def _is_vk_down(vk):
        try:
            return bool(win32api.GetAsyncKeyState(vk) & 0x8000)
        except Exception:
            return False

    def _get_modifier_state(self):
        ctrl_down = (
            self._is_vk_down(win32con.VK_LCONTROL)
            or self._is_vk_down(win32con.VK_RCONTROL)
        )

        alt_winapi = (
            self._is_vk_down(win32con.VK_MENU)
            or self._is_vk_down(win32con.VK_LMENU)
            or self._is_vk_down(win32con.VK_RMENU)
        )

        with self._key_state_lock:
            alt_hook = self._alt_down

        try:
            alt_keyboard = (
                keyboard.is_pressed("alt")
                or keyboard.is_pressed("alt gr")
            )
        except Exception:
            alt_keyboard = False

        alt_down = alt_winapi or alt_hook or alt_keyboard

        return ctrl_down, alt_down

    def _handle_printscreen_down(self):
        with self._key_state_lock:
            if self._printscreen_down:
                return
            self._printscreen_down = True

        if self._request_pending:
            return

        ctrl_down, alt_down = self._get_modifier_state()

        self._request_pending = True

        if ctrl_down:
            self._region_requested.emit()
            return

        if alt_down:
            self._prepare_window_capture()
            return

        self._monitor_requested.emit()

    # ==============================================================
    # Проверка принадлежности окна текущему процессу
    # ==============================================================

    @staticmethod
    def _is_app_window(hwnd):
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
        found = {"hwnd": None}
        current_pid = os.getpid()

        def _enum(hwnd, lparam):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid == current_pid:
                    return True
                text = win32gui.GetWindowText(hwnd)
                if text and not text.isspace():
                    found["hwnd"] = hwnd
                    return False
            except Exception:
                return True
            return True

        try:
            win32gui.EnumWindows(_enum, None)
        except Exception:
            pass

        return found["hwnd"]

    # ==============================================================
    # Alt + PrintScreen
    # ==============================================================

    def _prepare_window_capture(self):
        self._last_external_hwnd = None

        try:
            hwnd = win32gui.GetForegroundWindow()
        except Exception:
            hwnd = None

        if hwnd and not self._is_app_window(hwnd):
            self._last_external_hwnd = hwnd
        else:
            fallback = self._find_top_external_window()
            if fallback:
                self._last_external_hwnd = fallback

        if self.DEBUG:
            if self._last_external_hwnd:
                print(f"[WINDOW] external hwnd=0x{self._last_external_hwnd:X}")
            else:
                print("[WINDOW] external hwnd=None")

        self._window_requested.emit(self._last_external_hwnd)

    # ==============================================================
    # Скрытие / восстановление
    # ==============================================================

    def _begin(self):
        if self._capturing:
            return False

        self._capturing = True
        self._hidden_windows = []

        for window in self.window_manager.windows:
            if window.isVisible():
                self._hidden_windows.append(
                    (window, window.isMinimized())
                )
                window.hide()

        QApplication.processEvents()
        QApplication.flush()

        try:
            desktop_hwnd = win32gui.GetDesktopWindow()
            win32gui.RedrawWindow(
                desktop_hwnd,
                None,
                None,
                win32con.RDW_INVALIDATE
                | win32con.RDW_UPDATENOW
                | win32con.RDW_ALLCHILDREN,
            )
        except Exception:
            pass

        return True

    def _finish(self, target=None):
        self._capturing = False

        for window, was_minimized in self._hidden_windows:
            if not was_minimized:
                window.show()

        self._hidden_windows = []

        window = target or self.window_manager.active_window
        if not window:
            return

        if window.isMinimized():
            if window.windowState() & Qt.WindowMaximized:
                window.showMaximized()
            else:
                window.showNormal()
        elif not window.isVisible():
            window.show()

        QApplication.processEvents()

        # Принудительно возвращаем foreground.
        self._force_foreground(window)

    def _force_foreground(self, window):
        """
        Возвращает окно на передний план, обходя foreground lock Windows.

        Проблема: перед захватом мы вызывали SetForegroundWindow(external_hwnd)
        и скрывали свои окна. Windows теперь считает, что foreground занят
        внешним приложением, и блокирует наш SetForegroundWindow.

        Решение:
          1. Попытка прямого SetForegroundWindow.
          2. Если не сработало — AttachThreadInput к текущему foreground
             потоку, чтобы получить право переключения.
        """
        try:
            hwnd_self = int(window.winId())
        except Exception:
            return

        if not hwnd_self:
            return

        try:
            foreground = win32gui.GetForegroundWindow()
        except Exception:
            foreground = None

        if foreground == hwnd_self:
            return

        # Попытка 1: прямое переключение
        try:
            win32gui.ShowWindow(hwnd_self, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd_self)
            if self.DEBUG:
                print("[FOREGROUND] direct SetForegroundWindow OK")
            return
        except Exception as error:
            if self.DEBUG:
                print(f"[FOREGROUND] direct failed: {error}")

        # Попытка 2: через AttachThreadInput
        try:
            if foreground:
                fg_thread = win32process.GetWindowThreadProcessId(foreground)[0]
                cur_thread = win32api.GetCurrentThreadId()

                if fg_thread and fg_thread != cur_thread:
                    win32process.AttachThreadInput(fg_thread, cur_thread, True)
                    try:
                        win32gui.ShowWindow(hwnd_self, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd_self)
                        win32gui.BringWindowToTop(hwnd_self)
                        if self.DEBUG:
                            print("[FOREGROUND] AttachThreadInput OK")
                    finally:
                        win32process.AttachThreadInput(fg_thread, cur_thread, False)
                    return
        except Exception as error:
            if self.DEBUG:
                print(f"[FOREGROUND] AttachThreadInput failed: {error}")

        # Попытка 3: Qt-уровень
        try:
            window.raise_()
            window.activateWindow()
            if self.DEBUG:
                print("[FOREGROUND] Qt raise/activate fallback")
        except Exception:
            pass

    # ==============================================================
    # Захват
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

        return (
            overlay.get_pixmap()
            if overlay.exec_() == QDialog.Accepted
            else None
        )

    @staticmethod
    def _deliver(target, pixmap):
        if target.is_empty():
            target.view.set_background_from_pixmap(pixmap)
        else:
            target.view.add_pasted_image(pixmap)

    def _target(self):
        # Каждый новый скриншот должен попадать в отдельное окно.
        # Не переиспользуем окна с уже сохранённым скриншотом.
        return None

    # ==============================================================
    # Захват выбранного монитора
    # ==============================================================

    def capture_specific_screen(self, screen):
        if not self._begin():
            return
        QTimer.singleShot(
            self.HIDE_SETTLE_DELAY_MS,
            lambda: self._capture_specific_screen(screen),
        )

    def _capture_specific_screen(self, screen):
        target = None
        try:
            target = self._target()
            pixmap = screen.grabWindow(0)
            if not pixmap.isNull():
                target = (
                    target
                    or self.window_manager.create_editor_window(reusable=False)
                )
                self._deliver(target, pixmap)
        except Exception as error:
            print(f"Ошибка захвата выбранного экрана: {error}")
        finally:
            self._finish(target)

    # ==============================================================
    # Захват монитора
    # ==============================================================

    @pyqtSlot()
    def _capture_monitor(self):
        if not self._begin():
            self._request_pending = False
            return
        QTimer.singleShot(self.HIDE_SETTLE_DELAY_MS, self._do_capture_monitor)

    def _do_capture_monitor(self):
        target = None
        try:
            target = self._target()
            pixmap = self._capture_pixmap("monitor")
            if pixmap is not None:
                target = (
                    target
                    or self.window_manager.create_editor_window(reusable=False)
                )
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
        QTimer.singleShot(
            self.HIDE_SETTLE_DELAY_MS,
            lambda: self._do_capture_window(hwnd),
        )

    def _do_capture_window(self, hwnd):
        target = None
        try:
            if self._is_app_window(hwnd):
                hwnd = None

            if hwnd is None:
                QApplication.processEvents()
                foreground_hwnd = win32gui.GetForegroundWindow()
                if foreground_hwnd and not self._is_app_window(foreground_hwnd):
                    hwnd = foreground_hwnd

            if self._is_app_window(hwnd):
                hwnd = self._find_top_external_window()

            if hwnd:
                try:
                    win32gui.SetForegroundWindow(hwnd)
                    QApplication.processEvents()
                except Exception:
                    pass

            target = self._target()
            pixmap = self._capture_pixmap("active_window", hwnd)

            if pixmap is not None:
                target = (
                    target
                    or self.window_manager.create_editor_window(reusable=False)
                )
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
        QTimer.singleShot(self.HIDE_SETTLE_DELAY_MS, self._do_capture_region)

    def _do_capture_region(self):
        target = None
        try:
            target = self._target()
            pixmap = self._capture_pixmap("region")
            if pixmap is not None:
                target = (
                    target
                    or self.window_manager.create_editor_window(reusable=False)
                )
                self._deliver(target, pixmap)
        except Exception as error:
            print(f"Ошибка захвата области: {error}")
        finally:
            self._finish(target)
            self._request_pending = False