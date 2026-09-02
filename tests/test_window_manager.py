from PyQt5.QtWidgets import QApplication, QWidget

from screenshooter.window_manager import WindowManager


class FakeWindow(QWidget):
    def __init__(self, empty, no_pasted_images):
        super().__init__()
        self._empty = empty
        self._no_pasted_images = no_pasted_images

    def is_empty(self):
        return self._empty

    def has_no_pasted_images(self):
        return self._no_pasted_images


def test_reuse_prefers_last_active_empty_window(qapp):
    manager = WindowManager(qapp)
    first = FakeWindow(empty=True, no_pasted_images=False)
    second = FakeWindow(empty=True, no_pasted_images=False)
    manager.add_window(first)
    manager.add_window(second)

    manager.set_active_window(first)

    assert manager.find_target_window_for_reuse() is first


def test_reuse_falls_back_to_last_active_background_without_pasted_images(qapp):
    manager = WindowManager(qapp)
    with_pasted = FakeWindow(empty=False, no_pasted_images=False)
    available = FakeWindow(empty=False, no_pasted_images=True)
    manager.add_window(with_pasted)
    manager.add_window(available)

    assert manager.find_target_window_for_reuse() is available


def test_reuse_returns_none_when_no_window_is_eligible(qapp):
    manager = WindowManager(qapp)
    manager.add_window(FakeWindow(empty=False, no_pasted_images=False))

    assert manager.find_target_window_for_reuse() is None


def test_removing_last_window_quits_application(qapp, monkeypatch):
    manager = WindowManager(qapp)
    window = FakeWindow(empty=True, no_pasted_images=False)
    manager.add_window(window)
    quit_called = []
    monkeypatch.setattr(QApplication, "quit", lambda: quit_called.append(True))

    manager.remove_window(window)

    assert quit_called == [True]
