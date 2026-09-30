"""
Регрессии DPI-safe захвата в физических пикселях.
"""

from PyQt5.QtCore import QRect
from PyQt5.QtGui import QPixmap

from screenshooter.capture.virtual_screen import (
    _logical_rect_to_physical,
    grab_screen_physical,
)


def test_logical_rect_is_converted_to_physical_pixels(qapp):
    class FakeScreen:
        def geometry(self):
            return QRect(100, 50, 1000, 800)

        def devicePixelRatio(self):
            return 1.5

    result = _logical_rect_to_physical(FakeScreen(), QRect(200, 100, 100, 80))

    assert result == QRect(150, 75, 150, 120)


def test_grab_screen_physical_removes_qt_dpr(qapp):
    source = QPixmap(300, 200)
    source.setDevicePixelRatio(1.5)

    class FakeScreen:
        def grabWindow(self, *_args):
            return source

    result = grab_screen_physical(FakeScreen())

    assert result.size() == source.size()
    assert result.devicePixelRatio() == 1.0
