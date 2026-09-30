import ctypes
from unittest.mock import patch

from screenshooter.dpi import configure_windows_dpi_awareness


def test_dpi_configuration_is_noop_on_non_windows():
    with patch("screenshooter.dpi.platform.system", return_value="Linux"):
        assert configure_windows_dpi_awareness() is False


def test_dpi_configuration_uses_per_monitor_v2_on_windows():
    class FakeDpiFunction:
        def __init__(self):
            self.context = None

        def __call__(self, context):
            self.context = context
            return True

    class FakeDpiApi:
        def __init__(self):
            self.SetProcessDpiAwarenessContext = FakeDpiFunction()

    fake_user32 = FakeDpiApi()
    with patch("screenshooter.dpi.platform.system", return_value="Windows"), \
         patch("screenshooter.dpi.ctypes.windll.user32", fake_user32):
        assert configure_windows_dpi_awareness() is True
        assert fake_user32.context.value == ctypes.c_void_p(-4).value
