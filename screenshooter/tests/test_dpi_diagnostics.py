"""
Тесты диагностики DPI-safe захвата.
"""

from PyQt5.QtCore import QRect
from PyQt5.QtGui import QPixmap

from screenshooter.capture.dpi_diagnostics import collect_dpi_diagnostics


def test_dpi_diagnostics_reports_physical_capture_size(qapp):
    class FakeScreen:
        def name(self):
            return "DISPLAY1"

        def geometry(self):
            return QRect(0, 0, 1280, 720)

        def devicePixelRatio(self):
            return 1.5

    source = QPixmap(1920, 1080)
    source.setDevicePixelRatio(1.0)

    result = collect_dpi_diagnostics(
        screens=[FakeScreen()],
        grabber=lambda _screen: source,
    )

    assert result[0]["device_pixel_ratio"] == 1.5
    assert result[0]["captured_size"] == [1920, 1080]
    assert result[0]["captured_dpr"] == 1.0
