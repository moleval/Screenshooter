"""
Тесты диспетчеризации событий для AnnotationResizeController.
"""

from types import SimpleNamespace

from screenshooter.controllers.annotation_resize_controller import (
    AnnotationResizeController,
)
from screenshooter.controllers.mouse_interaction_manager import (
    MouseInteractionManager,
)


class RecordingController:
    def __init__(self, name, calls, result=False):
        self.name = name
        self.calls = calls
        self.result = result

    def handle_mouse_press(self, event):
        self.calls.append(f"{self.name}.press")
        return self.result

    def handle_mouse_move(self, event):
        self.calls.append(f"{self.name}.move")
        return self.result

    def handle_mouse_release(self, event):
        self.calls.append(f"{self.name}.release")
        return self.result


class FakeBlurController(RecordingController):
    def __init__(self, calls):
        super().__init__("blur", calls)
        self.blur_mode = False
        self.blur_outside_mode = False

    def handle_blur_region_move_outside(self, event):
        self.calls.append("blur_outside.move")
        return False

    def handle_blur_region_release_outside(self, event):
        self.calls.append("blur_outside.release")
        return False


class FakeManipulationController(RecordingController):
    def __init__(self, calls):
        super().__init__("manipulation", calls)
        self._drag_items = []


def make_manager(calls):
    view = SimpleNamespace(
        current_tool=None,
        temp_item=None,
        _tool=None,
        start_point=None,
    )
    blur = FakeBlurController(calls)
    image_editor = SimpleNamespace(crop_mode=False)
    manipulation = FakeManipulationController(calls)
    annotation = RecordingController("annotation_resize", calls)
    manager = MouseInteractionManager(
        view,
        blur,
        image_editor,
        manipulation,
        annotation,
    )
    return manager


def test_press_dispatches_annotation_resize_before_manipulation():
    calls = []
    manager = make_manager(calls)

    assert manager.handle_press(object()) is False
    assert calls == [
        "annotation_resize.press",
        "manipulation.press",
    ]


def test_move_dispatches_annotation_resize_before_manipulation():
    calls = []
    manager = make_manager(calls)

    assert manager.handle_move(object()) is False
    assert calls == [
        "blur_outside.move",
        "annotation_resize.move",
        "manipulation.move",
    ]


def test_release_dispatches_annotation_resize_before_manipulation():
    calls = []
    manager = make_manager(calls)

    assert manager.handle_release(SimpleNamespace(button=lambda: 0)) is False
    assert calls == [
        "annotation_resize.release",
        "manipulation.release",
    ]


def test_annotation_resize_is_blocked_in_blur_mode():
    view = SimpleNamespace(
        blur_controller=SimpleNamespace(blur_mode=True),
        image_editor=SimpleNamespace(crop_mode=False),
    )
    controller = AnnotationResizeController(view)

    assert controller.handle_mouse_press(object()) is False
    assert controller.handle_mouse_move(object()) is False
    assert controller.handle_mouse_release(object()) is False


def test_annotation_resize_is_blocked_in_crop_mode():
    view = SimpleNamespace(
        blur_controller=SimpleNamespace(blur_mode=False),
        image_editor=SimpleNamespace(crop_mode=True),
    )
    controller = AnnotationResizeController(view)

    assert controller.handle_mouse_press(object()) is False
    assert controller.handle_mouse_move(object()) is False
    assert controller.handle_mouse_release(object()) is False
