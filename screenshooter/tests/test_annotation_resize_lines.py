"""
Тесты resize линий и прямых стрелок через AnnotationResizeController.
"""

from types import SimpleNamespace

import pytest
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QPixmap, QPen
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from screenshooter.controllers.annotation_resize_controller import AnnotationResizeController
from screenshooter.history import HistoryManager
from screenshooter.items import LineItem, WavyLineItem, ArrowItem, DimensionItem


class FakeBlur:
    blur_mode = False


class FakeImageEditor:
    crop_mode = False

    def __init__(self, background_item):
        self.background_item = background_item


class FakeView(QGraphicsView):
    def __init__(self, scene, background_item):
        super().__init__(scene)
        self.blur_controller = FakeBlur()
        self.image_editor = FakeImageEditor(background_item)
        self.history = HistoryManager()
        self._interaction_dragging = False

    def _update_floating_widgets_visibility(self):
        pass


def event_for(view, scene_pos):
    return SimpleNamespace(
        button=lambda: Qt.LeftButton,
        pos=lambda: view.mapFromScene(scene_pos),
    )


def make_fixture(qapp):
    scene = QGraphicsScene()
    background = QGraphicsPixmapItem(QPixmap(200, 160))
    scene.addItem(background)
    view = FakeView(scene, background)
    view.resize(400, 300)
    view.show()
    qapp.processEvents()
    return view, background


def select_item(view, item):
    view.scene().clearSelection()
    item.setSelected(True)
    controller = AnnotationResizeController(view)
    controller.sync_handles()
    return controller


def scene_endpoints(item):
    if isinstance(item, LineItem):
        line = item.line()
        return item.mapToScene(line.p1()), item.mapToScene(line.p2())
    if isinstance(item, WavyLineItem):
        return item.mapToScene(QPointF(item._x1, item._y1)), item.mapToScene(QPointF(item._x2, item._y2))
    return item.mapToScene(item._start), item.mapToScene(item._end)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: LineItem(30, 40, 100, 40, QPen(Qt.red, 2)),
        lambda: WavyLineItem(30, 40, 100, 40, QPen(Qt.red, 2)),
        lambda: ArrowItem(QPointF(30, 40), QPointF(100, 40), QPen(Qt.red, 2)),
        lambda: DimensionItem(QPointF(30, 40), QPointF(100, 40), QPen(Qt.red, 2)),
    ],
)
def test_line_like_annotations_have_only_start_and_end_handles(qapp, factory):
    view, _ = make_fixture(qapp)
    item = factory()
    view.scene().addItem(item)
    controller = select_item(view, item)

    assert set(controller.handles.handle_items) == {"start", "end"}

    controller.remove_handles()
    view.close()


@pytest.mark.parametrize(
    "factory",
    [
        lambda: LineItem(30, 40, 100, 40, QPen(Qt.red, 2)),
        lambda: WavyLineItem(30, 40, 100, 40, QPen(Qt.red, 2)),
        lambda: ArrowItem(QPointF(30, 40), QPointF(100, 40), QPen(Qt.red, 2)),
        lambda: DimensionItem(QPointF(30, 40), QPointF(100, 40), QPen(Qt.red, 2)),
    ],
)
def test_end_handle_moves_with_fixed_start_and_supports_undo_redo(qapp, factory):
    view, _ = make_fixture(qapp)
    item = factory()
    view.scene().addItem(item)
    controller = select_item(view, item)

    old_start, old_end = scene_endpoints(item)
    target = QPointF(140, 100)

    assert controller.handle_mouse_press(event_for(view, old_end))
    assert controller.handle_mouse_move(event_for(view, target))
    controller.handle_mouse_release(event_for(view, target))

    new_start, new_end = scene_endpoints(item)
    assert new_start == old_start
    assert new_end == target
    assert view.history.can_undo()

    view.history.undo()
    undo_start, undo_end = scene_endpoints(item)
    assert undo_start == old_start
    assert undo_end == old_end

    view.history.redo()
    redo_start, redo_end = scene_endpoints(item)
    assert redo_start == old_start
    assert redo_end == target

    controller.remove_handles()
    view.close()


def test_line_resize_enforces_minimum_length(qapp):
    view, _ = make_fixture(qapp)
    item = LineItem(30, 40, 100, 40, QPen(Qt.red, 2))
    view.scene().addItem(item)
    controller = select_item(view, item)

    start, end = scene_endpoints(item)
    assert controller.handle_mouse_press(event_for(view, end))
    assert controller.handle_mouse_move(event_for(view, QPointF(32, 40)))
    controller.handle_mouse_release(event_for(view, QPointF(32, 40)))

    new_start, new_end = scene_endpoints(item)
    distance = ((new_end.x() - new_start.x()) ** 2 + (new_end.y() - new_start.y()) ** 2) ** 0.5
    assert distance >= 8

    controller.remove_handles()
    view.close()


def test_line_resize_clamps_moving_endpoint_to_background(qapp):
    view, _ = make_fixture(qapp)
    item = LineItem(30, 40, 100, 40, QPen(Qt.red, 2))
    view.scene().addItem(item)
    controller = select_item(view, item)

    old_start, _ = scene_endpoints(item)
    assert controller.handle_mouse_press(event_for(view, scene_endpoints(item)[1]))
    assert controller.handle_mouse_move(event_for(view, QPointF(500, 500)))
    controller.handle_mouse_release(event_for(view, QPointF(500, 500)))

    new_start, new_end = scene_endpoints(item)
    assert new_start == old_start
    assert 0 <= new_end.x() <= 200
    assert 0 <= new_end.y() <= 160

    controller.remove_handles()
    view.close()


def test_line_handle_does_not_capture_regular_body_click(qapp):
    view, _ = make_fixture(qapp)
    item = LineItem(30, 40, 100, 40, QPen(Qt.red, 2))
    view.scene().addItem(item)
    controller = select_item(view, item)

    assert not controller.handle_mouse_press(event_for(view, QPointF(65, 40)))
    assert controller._handle_id is None

    controller.remove_handles()
    view.close()


def test_line_resize_is_blocked_in_blur_and_crop_modes(qapp):
    view, _ = make_fixture(qapp)
    item = LineItem(30, 40, 100, 40, QPen(Qt.red, 2))
    view.scene().addItem(item)
    controller = select_item(view, item)
    endpoint = scene_endpoints(item)[1]

    view.blur_controller.blur_mode = True
    assert not controller.handle_mouse_press(event_for(view, endpoint))
    view.blur_controller.blur_mode = False

    view.image_editor.crop_mode = True
    assert not controller.handle_mouse_press(event_for(view, endpoint))

    controller.remove_handles()
    view.close()
