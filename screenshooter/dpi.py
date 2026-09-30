"""
Модуль: dpi.py
Описание: Настройка DPI-awareness процесса Windows до создания QApplication.
"""

import ctypes
import platform


def configure_windows_dpi_awareness():
    """Включает режим Per-Monitor DPI Awareness на Windows."""
    if platform.system() != "Windows":
        return False

    try:
        user32 = ctypes.windll.user32
    except AttributeError:
        return False

    # Windows 10 1703+: наиболее точный режим для Qt и нескольких мониторов.
    try:
        set_context = user32.SetProcessDpiAwarenessContext
        set_context.argtypes = [ctypes.c_void_p]
        set_context.restype = ctypes.c_bool
        per_monitor_v2 = ctypes.c_void_p(-4)
        if set_context(per_monitor_v2):
            return True
    except (AttributeError, OSError):
        pass

    # Запасной вариант для более старых версий Windows.
    try:
        shcore = ctypes.windll.shcore
        result = shcore.SetProcessDpiAwareness(2)
        return result == 0
    except (AttributeError, OSError):
        return False
