"""
Тесты resize аннотаций через AnnotationResizeController.
"""

from types import SimpleNamespace

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QPixmap, QPen, QColor
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from screenshooter.controllers.annotation_resize_controller import AnnotationResizeController
from screenshooter.history import HistoryManager, ChangeBrushCommand
from screenshooter.items import CloudItem, EllipseItem, FilledRectItem, RectangleItem


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
    view = FakeView(scene, None)
    view.resize(400, 300)

    background = QGraphicsPixmapItem(QPixmap(200, 160))
    scene.addItem(background)
    view.image_editor.background_item = background

    view.show()
    qapp.processEvents()
    return view, background


def select_item(view, item):
    view.scene().clearSelection()
    item.setSelected(True)
    controller = AnnotationResizeController(view)
    controller.sync_handles()
    return controller


def test_rectangle_still_has_eight_handles_and_anchor_resize(qapp):
    view, _ = make_fixture(qapp)
    item = RectangleItem(QRectF(20, 20, 80, 60), QPen(Qt.red, 2))
    view.scene().addItem(item)
    controller = select_item(view, item)

    assert set(controller.handles.handle_items) == {
        "tl", "tm", "tr", "lm", "rm", "bl", "bm", "br"
    }

    old = QRectF(item.rect())
    anchor = item.mapToScene(old.topLeft())
    assert controller.handle_mouse_press(event_for(view, item.mapToScene(old.bottomRight())))
    assert controller.handle_mouse_move(event_for(view, QPointF(140, 110)))

    assert item.mapRectToScene(item.rect()).normalized().topLeft() == anchor
    assert item.rect().width() >= 5
    assert item.rect().height() >= 5

    controller.handle_mouse_release(event_for(view, QPointF(140, 110)))
    assert view.history.can_undo()
    controller.remove_handles()
    view.close()


def test_filled_rect_has_eight_handles_and_resizes(qapp):
    view, _ = make_fixture(qapp)
    item = FilledRectItem(QRectF(20, 20, 80, 60), QColor(255, 0, 0))
    view.scene().addItem(item)
    controller = select_item(view, item)

    assert set(controller.handles.handle_items) == {
        "tl", "tm", "tr", "lm", "rm", "bl", "bm", "br"
    }

    old = QRectF(item.rect())
    assert controller.handle_mouse_press(event_for(view, item.mapToScene(QPointF(old.right(), old.bottom()))))
    assert controller.handle_mouse_move(event_for(view, QPointF(130, 100)))
    controller.handle_mouse_release(event_for(view, QPointF(130, 100)))

    assert item.rect().width() > old.width()
    assert item.rect().height() > old.height()
    assert view.history.can_undo()

    view.history.undo()
    assert item.rect() == old
    view.history.redo()
    assert item.rect().width() > old.width()

    controller.remove_handles()
    view.close()


def test_cloud_has_eight_handles_and_rebuilds_path(qapp):
    view, _ = make_fixture(qapp)
    item = CloudItem(QRectF(20, 20, 80, 60), QPen(Qt.red, 2))
    view.scene().addItem(item)
    controller = select_item(view, item)

    assert set(controller.handles.handle_items) == {
        "tl", "tm", "tr", "lm", "rm", "bl", "bm", "br"
    }

    old = QRectF(item.rect())
    old_path = item.path()
    assert controller.handle_mouse_press(event_for(view, item.mapToScene(old.right(), old.bottom())))
    assert controller.handle_mouse_move(event_for(view, QPointF(140, 110)))
    controller.handle_mouse_release(event_for(view, QPointF(140, 110)))

    assert item.rect().width() > old.width()
    assert item.rect().height() > old.height()
    assert item.path() != old_path

    controller.remove_handles()
    view.close()


def test_ellipse_has_eight_handles(qapp):
    view, _ = make_fixture(qapp)
    item = EllipseItem(QRectF(40, 30, 80, 60), QPen(Qt.red, 2))
    view.scene().addItem(item)
    controller = select_item(view, item)

    assert set(controller.handles.handle_items) == {
        "tl", "tm", "tr", "lm", "rm", "bl", "bm", "br"
    }

    old = QRectF(item.rect())
    anchor = item.mapToScene(old.topLeft())

    assert controller.handle_mouse_press(event_for(view, item.mapToScene(old.bottomRight())))
    assert controller.handle_mouse_move(event_for(view, QPointF(150, 110)))
    controller.handle_mouse_release(event_for(view, QPointF(150, 110)))

    new_rect = item.mapRectToScene(item.rect()).normalized()
    assert new_rect.topLeft() == anchor
    assert new_rect.width() > old.width()
    assert new_rect.height() > old.height()
    assert view.history.can_undo()

    view.history.undo()
    assert item.rect() == old
    view.history.redo()
    assert item.rect() != old

    controller.remove_handles()
    view.close()


def test_filled_rect_brush_change_has_undo_redo(qapp):
    view, _ = make_fixture(qapp)
    item = FilledRectItem(QRectF(20, 20, 80, 60), QColor(255, 0, 0))
    view.scene().addItem(item)

    old_brush = item.brush()
    new_brush = QColor(0, 255, 0, 80)
    view.history.push(ChangeBrushCommand(item, old_brush, new_brush))

    assert item.brush().color() == new_brush
    view.history.undo()
    assert item.brush() == old_brush
    view.history.redo()
    assert item.brush().color() == new_brush

    view.close()
