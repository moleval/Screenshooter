from unittest.mock import Mock

from screenshooter.hotkey_manager import HotkeyManager


def test_monitor_capture_result_is_shown_fullscreen():
    target = Mock()

    HotkeyManager._show_monitor_capture_result_fullscreen(target)

    target.showFullScreen.assert_called_once_with()


def test_monitor_capture_result_fullscreen_handles_missing_target():
    HotkeyManager._show_monitor_capture_result_fullscreen(None)
