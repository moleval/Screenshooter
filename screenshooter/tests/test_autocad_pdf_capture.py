"""Тесты экспериментального PDF-захвата AutoCAD."""
from PyQt5.QtCore import QRect

from screenshooter.capture.autocad_pdf_capture import (
    _is_supported_2d_view,
    screen_rect_to_autocad_window,
)


class FakeUtility:
    @staticmethod
    def TranslateCoordinates(point, source, target, displacement):
        assert source == 1
        assert target == 0
        return point


class FakeDocument:
    Utility = FakeUtility()

    def __init__(self, values):
        self.values = values

    def GetVariable(self, name):
        return self.values[name]


def test_pdf_capture_accepts_plain_2d_top_view():
    assert _is_supported_2d_view({
        "view_dir": (0.0, 0.0, 1.0),
        "view_twist": 0.0,
    })


def test_pdf_capture_rejects_twisted_view():
    assert not _is_supported_2d_view({
        "view_dir": (0.0, 0.0, 1.0),
        "view_twist": 0.1,
    })


def test_screen_rect_maps_to_autocad_window():
    document = FakeDocument({
        "VIEWCTR": (100.0, 200.0, 0.0),
        "VIEWSIZE": 100.0,
        "SCREENSIZE": (1000.0, 500.0, 0.0),
        "VIEWDIR": (0.0, 0.0, 1.0),
        "VIEWTWIST": 0.0,
    })

    # Fake window: client origin is (0, 0), 1000x500.
    import screenshooter.capture.autocad_pdf_capture as module

    original_get_client_rect = module.win32gui.GetClientRect
    original_client_to_screen = module.win32gui.ClientToScreen
    try:
        module.win32gui.GetClientRect = lambda hwnd: (0, 0, 1000, 500)
        module.win32gui.ClientToScreen = lambda hwnd, point: point

        lower_left, upper_right = screen_rect_to_autocad_window(
            document,
            123,
            QRect(250, 125, 500, 250),
        )
    finally:
        module.win32gui.GetClientRect = original_get_client_rect
        module.win32gui.ClientToScreen = original_client_to_screen

    assert lower_left == (50.0, 175.0, 0.0)
    assert upper_right == (150.0, 225.0, 0.0)
