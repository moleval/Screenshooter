"""
Тесты resize CurvedArrowItem через AnnotationResizeController.
"""

from types import SimpleNamespace

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QPixmap, QPen
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from screenshooter.controllers.annotation_resize_controller import AnnotationResizeController
from screenshooter.history import HistoryManager
from screenshooter.items import CurvedArrowItem


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
        modifiers=lambda: Qt.NoModifier,
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


def scene_geometry(item):
    return (
        item.mapToScene(item._start),
        item.mapToScene(item._end),
        item.mapToScene(item._ctrl),
    )


def test_curved_arrow_has_three_handles(qapp):
    view, _ = make_fixture(qapp)
    item = CurvedArrowItem(
        QPointF(30, 40),
        QPointF(130, 40),
        QPointF(80, 100),
        QPen(Qt.red, 2),
    )
    view.scene().addItem(item)
    controller = select_item(view, item)

    assert set(controller.handles.handle_items) == {"start", "end", "ctrl"}

    controller.remove_handles()
    view.close()


def test_curved_arrow_ctrl_handle_moves_endpoints_and_supports_undo_redo(qapp):
    view, _ = make_fixture(qapp)
    item = CurvedArrowItem(
        QPointF(30, 40),
        QPointF(130, 40),
        QPointF(80, 100),
        QPen(Qt.red, 2),
    )
    view.scene().addItem(item)
    controller = select_item(view, item)

    old_start, old_end, old_ctrl = scene_geometry(item)
    target = QPointF(70, 120)

    assert controller.handle_mouse_press(event_for(view, old_ctrl))
    assert controller.handle_mouse_move(event_for(view, target))
    controller.handle_mouse_release(event_for(view, target))

    new_start, new_end, new_ctrl = scene_geometry(item)
    assert new_start == old_start
    assert new_end == old_end
    assert new_ctrl == target
    assert view.history.can_undo()

    view.history.undo()
    undo_start, undo_end, undo_ctrl = scene_geometry(item)
    assert undo_start == old_start
    assert undo_end == old_end
    assert undo_ctrl == old_ctrl

    view.history.redo()
    redo_start, redo_end, redo_ctrl = scene_geometry(item)
    assert redo_start == old_start
    assert redo_end == old_end
    assert redo_ctrl == target

    controller.remove_handles()
    view.close()


def test_curved_arrow_end_handle_keeps_start_and_ctrl_fixed(qapp):
    view, _ = make_fixture(qapp)
    item = CurvedArrowItem(
        QPointF(30, 40),
        QPointF(130, 40),
        QPointF(80, 100),
        QPen(Qt.red, 2),
    )
    view.scene().addItem(item)
    controller = select_item(view, item)

    old_start, old_end, old_ctrl = scene_geometry(item)
    target = QPointF(150, 120)

    assert controller.handle_mouse_press(event_for(view, old_end))
    assert controller.handle_mouse_move(event_for(view, target))
    controller.handle_mouse_release(event_for(view, target))

    new_start, new_end, new_ctrl = scene_geometry(item)
    assert new_start == old_start
    assert new_end == target
    assert new_ctrl == old_ctrl

    controller.remove_handles()
    view.close()


def test_curved_arrow_resize_clamps_all_handles_to_background(qapp):
    view, _ = make_fixture(qapp)
    item = CurvedArrowItem(
        QPointF(30, 40),
        QPointF(130, 40),
        QPointF(80, 100),
        QPen(Qt.red, 2),
    )
    view.scene().addItem(item)
    controller = select_item(view, item)

    assert controller.handle_mouse_press(event_for(view, item._ctrl))
    controller.handle_mouse_move(event_for(view, QPointF(500, 500)))
    controller.handle_mouse_release(event_for(view, QPointF(500, 500)))

    _, _, ctrl = scene_geometry(item)
    assert 0 <= ctrl.x() <= 200
    assert 0 <= ctrl.y() <= 160

    controller.remove_handles()
    view.close()


def test_curved_arrow_resize_is_blocked_in_blur_and_crop_modes(qapp):
    view, _ = make_fixture(qapp)
    item = CurvedArrowItem(
        QPointF(30, 40),
        QPointF(130, 40),
        QPointF(80, 100),
        QPen(Qt.red, 2),
    )
    view.scene().addItem(item)
    controller = select_item(view, item)
    ctrl = scene_geometry(item)[2]

    view.blur_controller.blur_mode = True
    assert not controller.handle_mouse_press(event_for(view, ctrl))
    view.blur_controller.blur_mode = False

    view.image_editor.crop_mode = True
    assert not controller.handle_mouse_press(event_for(view, ctrl))

    controller.remove_handles()
    view.close()
