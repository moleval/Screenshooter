"""
Тесты resize RectangleItem через AnnotationResizeController.
"""

from types import SimpleNamespace

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QPixmap, QPen
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from screenshooter.controllers.annotation_resize_controller import (
    AnnotationResizeController,
)
from screenshooter.history import HistoryManager
from screenshooter.items import RectangleItem


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
        self.widget_manager = SimpleNamespace(
            update_floating_widgets_visibility=lambda: None
        )

    def _update_floating_widgets_visibility(self):
        pass


def event_for(view, scene_pos):
    return SimpleNamespace(
        button=lambda: Qt.LeftButton,
        pos=lambda: view.mapFromScene(scene_pos),
    )


def make_fixture(qapp):
    scene = QGraphicsScene()
    view = FakeView(scene, None)
    view.resize(400, 300)

    background = QGraphicsPixmapItem(QPixmap(200, 160))
    background.setPos(0, 0)
    scene.addItem(background)
    view.image_editor.background_item = background

    item = RectangleItem(QRectF(20, 20, 80, 60), QPen(Qt.red, 2))
    scene.addItem(item)
    item.setSelected(True)

    view.show()
    qapp.processEvents()
    return view, background, item


def test_rectangle_creates_eight_annotation_handles(qapp):
    view, _, item = make_fixture(qapp)
    controller = AnnotationResizeController(view)

    controller.sync_handles()

    assert controller.handles is not None
    assert set(controller.handles.handle_items) == {
        "tl", "tm", "tr", "lm", "rm", "bl", "bm", "br"
    }

    controller.remove_handles()
    view.close()


def test_rectangle_corner_resize_preserves_opposite_anchor_and_undo(qapp):
    view, _, item = make_fixture(qapp)
    controller = AnnotationResizeController(view)

    controller.sync_handles()

    old_rect = QRectF(item.rect())
    old_pos = QPointF(item.pos())
    anchor = item.mapToScene(old_rect.topLeft())

    press = event_for(view, item.mapToScene(old_rect.bottomRight()))
    assert controller.handle_mouse_press(press)

    move = event_for(view, QPointF(140, 110))
    assert controller.handle_mouse_move(move)

    scene_rect = item.mapRectToScene(item.rect()).normalized()
    assert scene_rect.topLeft() == anchor
    assert scene_rect.width() >= 5
    assert scene_rect.height() >= 5

    release = event_for(view, QPointF(140, 110))
    assert controller.handle_mouse_release(release)
    assert view.history.can_undo()

    view.history.undo()
    assert item.rect() == old_rect
    assert item.pos() == old_pos

    view.history.redo()
    assert item.mapRectToScene(item.rect()).normalized() == scene_rect

    controller.remove_handles()
    view.close()


def test_rectangle_resize_is_clamped_to_background(qapp):
    view, _, item = make_fixture(qapp)
    controller = AnnotationResizeController(view)

    controller.sync_handles()
    old_rect = QRectF(item.rect())

    press = event_for(view, item.mapToScene(old_rect.bottomRight()))
    assert controller.handle_mouse_press(press)

    move = event_for(view, QPointF(1000, 1000))
    assert controller.handle_mouse_move(move)
    controller.handle_mouse_release(move)

    scene_rect = item.mapRectToScene(item.rect()).normalized()
    bg_rect = view.image_editor.background_item.mapRectToScene(
        QRectF(view.image_editor.background_item.pixmap().rect())
    ).normalized()

    assert scene_rect.right() <= bg_rect.right()
    assert scene_rect.bottom() <= bg_rect.bottom()
    assert scene_rect.left() >= bg_rect.left()
    assert scene_rect.top() >= bg_rect.top()

    controller.remove_handles()
    view.close()


def test_rectangle_minimum_size_is_five_pixels(qapp):
    view, _, item = make_fixture(qapp)
    controller = AnnotationResizeController(view)

    controller.sync_handles()
    old_rect = QRectF(item.rect())

    press = event_for(view, item.mapToScene(old_rect.bottomRight()))
    assert controller.handle_mouse_press(press)

    move = event_for(view, QPointF(20.1, 20.1))
    assert controller.handle_mouse_move(move)
    controller.handle_mouse_release(move)

    assert item.rect().width() >= 5
    assert item.rect().height() >= 5

    controller.remove_handles()
    view.close()
