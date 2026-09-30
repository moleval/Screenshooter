from unittest.mock import patch

from screenshooter.dpi import configure_windows_dpi_awareness


def test_dpi_configuration_is_noop_on_non_windows():
    with patch("screenshooter.dpi.platform.system", return_value="Linux"):
        assert configure_windows_dpi_awareness() is False


def test_dpi_configuration_uses_per_monitor_v2_on_windows():
    class FakeUser32:
        def SetProcessDpiAwarenessContext(self, context):
            assert context.value == -4
            return True

    with patch("screenshooter.dpi.platform.system", return_value="Windows"), \
         patch("screenshooter.dpi.ctypes.windll.user32", FakeUser32()):
        assert configure_windows_dpi_awareness() is True
