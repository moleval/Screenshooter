"""
Модуль: capture/window_capture.py
Описание: Захват активного окна (Alt+PrintScreen) через win32gui.
Определяет клиентскую область окна и вырезает её из виртуального
скриншота.
"""
import os

import win32gui
import win32api
import win32con
import win32process
from PyQt5.QtCore import QRect
from .virtual_screen import grab_physical_rect


def is_autocad_window(hwnd):
    """Надёжно определяет окно AutoCAD по процессу или заголовку."""
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False

    # PROCESS_QUERY_LIMITED_INFORMATION работает и при разном уровне
    # привилегий процесса приложения и AutoCAD.
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            pid,
        )
        try:
            executable = win32process.QueryFullProcessImageName(
                process_handle,
                0,
            )
        finally:
            win32api.CloseHandle(process_handle)
        executable_name = os.path.basename(executable).lower()
        if executable_name in {"acad.exe", "acadlt.exe"}:
            return True
    except Exception:
        pass

    # Совместимость со старыми/ограниченными окружениями.
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
            False,
            pid,
        )
        try:
            executable = win32process.GetModuleFileNameEx(process_handle, 0)
        finally:
            win32api.CloseHandle(process_handle)
        executable_name = os.path.basename(executable).lower()
        if executable_name in {"acad.exe", "acadlt.exe"}:
            return True
    except Exception:
        pass

    # Последний fallback — заголовок окна.
    try:
        title = win32gui.GetWindowText(hwnd).strip().lower()
    except Exception:
        title = ""
    return "autocad" in title or ("autodesk" in title and "cad" in title)


def capture_active_window(hwnd=None):
    """Захватывает клиентскую область окна.

    :param hwnd: Если передан, захватывает это окно.
                 Если не передан, берёт GetForegroundWindow().
                 Если окно принадлежит текущему процессу — возвращает None.
    """
    if hwnd is None or not win32gui.IsWindow(hwnd):
        hwnd = win32gui.GetForegroundWindow()

    if not hwnd:
        return None

    # Защита: не захватываем собственное окно
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid == os.getpid():
            return None
    except Exception:
        pass

    # Проверяем, что окно видимо
    if not win32gui.IsWindowVisible(hwnd):
        return None

    client_rect = win32gui.GetClientRect(hwnd)
    left_top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
    right_bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))

    x = left_top[0]
    y = left_top[1]
    width = right_bottom[0] - left_top[0]
    height = right_bottom[1] - left_top[1]

    if width <= 0 or height <= 0:
        return None

    return grab_physical_rect(QRect(x, y, width, height))