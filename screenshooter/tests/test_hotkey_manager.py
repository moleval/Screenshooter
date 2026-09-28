from unittest.mock import Mock

from screenshooter.hotkey_manager import HotkeyManager


def test_monitor_capture_result_is_shown_maximized():
    target = Mock()

    HotkeyManager._show_monitor_capture_result_maximized(target)

    target.showMaximized.assert_called_once_with()


def test_monitor_capture_result_maximized_handles_missing_target():
    HotkeyManager._show_monitor_capture_result_maximized(None)


def test_window_state_maximized_flag_uses_integer_qt_flags():
    from PyQt5.QtCore import Qt

    state = Qt.WindowMaximized
    assert bool(int(state) & int(Qt.WindowMaximized))
