"""
Тесты resize TextItem через AnnotationResizeController.
"""

from types import SimpleNamespace

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from screenshooter.constants import MIN_SCALE
from screenshooter.controllers.annotation_resize_controller import AnnotationResizeController
from screenshooter.history import HistoryManager
from screenshooter.items import TextItem


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
    background = QGraphicsPixmapItem(QPixmap(300, 220))
    scene.addItem(background)
    view = FakeView(scene, background)
    view.resize(500, 400)
    view.show()
    qapp.processEvents()
    return view, background


def make_text(view):
    item = TextItem(view)
    item.setPlainText("Resize me")
    item.setPos(60, 70)
    item.setSelected(True)
    view.scene().addItem(item)
    return item


def test_text_has_four_corner_handles_and_editable_hides_them(qapp):
    view, _ = make_fixture(qapp)
    item = make_text(view)
    controller = AnnotationResizeController(view)
    controller.sync_handles()

    assert set(controller.handles.handle_items) == {"tl", "tr", "bl", "br"}

    item.setEditable(True)
    controller.sync_handles()
    assert controller.handles is None

    item.setEditable(False)
    controller.sync_handles()
    assert set(controller.handles.handle_items) == {"tl", "tr", "bl", "br"}

    controller.remove_handles()
    view.close()


def test_text_handle_points_follow_rotation(qapp):
    view, _ = make_fixture(qapp)
    item = make_text(view)
    item.setRotation(45)
    controller = AnnotationResizeController(view)
    controller.sync_handles()

    expected = {
        key: item.mapToScene(point)
        for key, point in {
            "tl": item.rect().topLeft(),
            "tr": item.rect().topRight(),
            "bl": item.rect().bottomLeft(),
            "br": item.rect().bottomRight(),
        }.items()
    }

    for key, point in expected.items():
        actual = controller.handles.handle_items[key].pos()
        assert actual == point

    controller.remove_handles()
    view.close()


def test_text_resize_is_proportional_and_keeps_opposite_corner_fixed(qapp):
    view, _ = make_fixture(qapp)
    item = make_text(view)
    item.setRotation(45)
    controller = AnnotationResizeController(view)
    controller.sync_handles()

    old_scale = item.scale()
    anchor = item.mapToScene(item.rect().bottomRight())
    moving = item.mapToScene(item.rect().topLeft())
    vector = moving - anchor
    target = anchor + vector * 1.5

    assert controller.handle_mouse_press(event_for(view, moving))
    assert controller.handle_mouse_move(event_for(view, target))
    controller.handle_mouse_release(event_for(view, target))

    assert item.scale() == old_scale * 1.5
    assert item.mapToScene(item.rect().bottomRight()) == anchor
    assert view.history.can_undo()

    view.history.undo()
    assert item.scale() == old_scale
    assert item.mapToScene(item.rect().bottomRight()) == anchor

    view.history.redo()
    assert item.scale() == old_scale * 1.5

    controller.remove_handles()
    view.close()


def test_text_resize_respects_minimum_scale(qapp):
    view, _ = make_fixture(qapp)
    item = make_text(view)
    controller = AnnotationResizeController(view)
    controller.sync_handles()

    moving = item.mapToScene(item.rect().topLeft())
    anchor = item.mapToScene(item.rect().bottomRight())

    assert controller.handle_mouse_press(event_for(view, moving))
    assert controller.handle_mouse_move(event_for(view, anchor))
    controller.handle_mouse_release(event_for(view, anchor))

    assert item.scale() >= MIN_SCALE

    controller.remove_handles()
    view.close()
