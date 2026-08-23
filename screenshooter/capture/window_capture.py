"""Захват активного окна (Ctrl+PrintScreen)."""

import win32gui
import win32con
from PyQt5.QtCore import QRect
from .virtual_screen import grab_virtual_screen, get_virtual_screen_geometry


def capture_active_window():
    """Захватывает клиентскую область активного окна."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
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
    full = grab_virtual_screen()
    if full.isNull():
        return None
    total_rect = get_virtual_screen_geometry()
    offset = total_rect.topLeft()
    local_rect = QRect(x - offset.x(), y - offset.y(), width, height)
    return full.copy(local_rect)