"""
Модуль: capture/dpi_diagnostics.py
Описание: Диагностика соответствия физической геометрии мониторов
          фактическому размеру снимка Windows.
"""

import json

from PyQt5.QtGui import QGuiApplication

from .virtual_screen import get_screen_physical_geometry, grab_screen_physical


def collect_dpi_diagnostics(screens=None, grabber=grab_screen_physical):
    """Собирает данные о DPI и фактическом размере снимка каждого экрана."""
    if screens is None:
        screens = QGuiApplication.screens()

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
