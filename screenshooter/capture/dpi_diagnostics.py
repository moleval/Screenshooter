"""
Модуль: capture/dpi_diagnostics.py
Описание: Диагностика соответствия физической геометрии мониторов
          фактическому размеру снимка Windows.
"""

import ctypes
import json
import platform

from PyQt5.QtGui import QGuiApplication

from screenshooter.dpi import configure_windows_dpi_awareness


def _get_windows_monitor_dpi(screen_name):
    """Возвращает DPI монитора напрямую через Windows API."""
    if platform.system() != "Windows":
        return None

    try:
        shcore = ctypes.windll.shcore
        user32 = ctypes.windll.user32
        enum_proc_type = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_void_p,
        )
        found_dpi = []

        def callback(monitor, _hdc, _rect, _data):
            info = ctypes.create_unicode_buffer(32)
            info.cb = 0
            return 1

        monitors = []
        monitor_enum = enum_proc_type(
            lambda monitor, hdc, rect, data: (
                monitors.append(monitor) or 1
            )
        )
        user32.EnumDisplayMonitors(None, None, monitor_enum, 0)

        for monitor in monitors:
            class MONITORINFOEXW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_uint32),
                    ("rcMonitor", ctypes.c_int32 * 4),
                    ("rcWork", ctypes.c_int32 * 4),
                    ("dwFlags", ctypes.c_uint32),
                    ("szDevice", ctypes.c_wchar * 32),
                ]

            monitor_info = MONITORINFOEXW()
            monitor_info.cbSize = ctypes.sizeof(monitor_info)
            if not user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
                continue
            if monitor_info.szDevice != screen_name:
                continue

            dpi_x = ctypes.c_uint()
            dpi_y = ctypes.c_uint()
            result = shcore.GetDpiForMonitor(
                monitor,
                0,
                ctypes.byref(dpi_x),
                ctypes.byref(dpi_y),
            )
            if result == 0:
                return [dpi_x.value, dpi_y.value]
    except (AttributeError, OSError):
        return None

    return None


def _get_process_dpi_awareness():
    """Возвращает режим DPI-awareness текущего процесса Windows."""
    if platform.system() != "Windows":
        return None

    try:
        shcore = ctypes.windll.shcore
        process = ctypes.windll.kernel32.GetCurrentProcess()
        awareness = ctypes.c_int()
        result = shcore.GetProcessDpiAwareness(
            process,
            ctypes.byref(awareness),
        )
        if result == 0:
            return awareness.value
    except (AttributeError, OSError):
        return None

    return None

from .virtual_screen import get_screen_physical_geometry, grab_screen_physical


def collect_dpi_diagnostics(screens=None, grabber=grab_screen_physical):
    """Собирает данные о DPI и фактическом размере снимка каждого экрана."""
    if screens is None:
        screens = QGuiApplication.screens()

    process_dpi_awareness = _get_process_dpi_awareness()
    result = []
    for screen in screens:
        logical = screen.geometry()
        physical = get_screen_physical_geometry(screen)
        pixmap = grabber(screen)

        dpr = float(screen.devicePixelRatio() or 1.0)
        expected_size = [
            round(logical.width() * dpr),
            round(logical.height() * dpr),
        ]
        captured_size = [pixmap.width(), pixmap.height()]

        result.append(
            {
                "name": screen.name(),
                "logical_geometry": [
                    logical.x(),
                    logical.y(),
                    logical.width(),
                    logical.height(),
                ],
                "device_pixel_ratio": dpr,
                "windows_monitor_dpi": _get_windows_monitor_dpi(screen.name()),
                "process_dpi_awareness": process_dpi_awareness,
                "expected_physical_size": expected_size,
                "physical_geometry": [
                    physical.x(),
                    physical.y(),
                    physical.width(),
                    physical.height(),
                ],
                "captured_size": captured_size,
                "captured_dpr": float(
                    pixmap.devicePixelRatio() or 1.0
                ),
                "logical_scale_matches_capture": (
                    not pixmap.isNull()
                    and captured_size == expected_size
                ),
                "physical_size_matches": (
                    not pixmap.isNull()
                    and pixmap.width() == physical.width()
                    and pixmap.height() == physical.height()
                ),
            }
        )

    return result


def main():
    """Запускает консольную диагностику физических размеров захвата."""
    if QGuiApplication.instance() is None:
        configure_windows_dpi_awareness()

    app = QGuiApplication.instance() or QGuiApplication([])
    print(
        json.dumps(
            collect_dpi_diagnostics(),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
