"""
Регрессионные тесты атомарного Undo/Redo для resize всех типов аннотаций.
"""

from types import SimpleNamespace

import pytest

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPixmap, QPen
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from screenshooter.controllers.annotation_resize_controller import AnnotationResizeController
from screenshooter.history import HistoryManager
from screenshooter.items import (
    ArrowItem,
    CloudItem,
    CurvedArrowItem,
    DimensionItem,
    EllipseItem,
    FilledRectItem,
    LineItem,
    RectangleItem,
    TextItem,
    WavyLineItem,
)


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

    def _text_editing_finished(self, item):
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
    return view


def rect_item_state(item):
    return tuple(
        item.mapToScene(point)
        for point in (
            item.rect().topLeft(),
            item.rect().bottomRight(),
        )
    )


def line_item_state(item):
    if isinstance(item, LineItem):
        line = item.line()
        start, end = line.p1(), line.p2()
    elif isinstance(item, WavyLineItem):
        start = QPointF(item._x1, item._y1)
        end = QPointF(item._x2, item._y2)
    elif isinstance(item, (ArrowItem, DimensionItem)):
        start = QPointF(item._start)
        end = QPointF(item._end)
    else:
        raise TypeError(type(item).__name__)
    return item.mapToScene(start), item.mapToScene(end)


def curved_item_state(item):
    return tuple(
        item.mapToScene(point)
        for point in (item._start, item._end, item._ctrl)
    )


def text_item_state(item):
    return item.scale(), QPointF(item.pos())


def make_item(view, kind):
    pen = QPen(Qt.red, 2)
    rect = QRectF(40, 40, 80, 60)

    factories = {
        "rectangle": lambda: RectangleItem(rect, QPen(pen)),
        "filled": lambda: FilledRectItem(rect, QColor("red")),
        "cloud": lambda: CloudItem(rect, QPen(pen)),
        "ellipse": lambda: EllipseItem(rect, QPen(pen)),
        "line": lambda: LineItem(40, 50, 120, 50, QPen(pen)),
        "wavy": lambda: WavyLineItem(40, 50, 120, 50, QPen(pen)),
        "arrow": lambda: ArrowItem(QPointF(40, 50), QPointF(120, 50), QPen(pen)),
        "dimension": lambda: DimensionItem(QPointF(40, 50), QPointF(120, 50), QPen(pen)),
        "curved": lambda: CurvedArrowItem(
            QPointF(40, 50), QPointF(140, 50), QPointF(90, 100), QPen(pen)
        ),
    }

    if kind == "text":
        item = TextItem(view)
        item.setPlainText("Resize me")
        item.setPos(60, 70)
        return item

    return factories[kind]()


def item_state(item, kind):
    if kind in {"rectangle", "filled", "cloud", "ellipse"}:
        return rect_item_state(item)
    if kind in {"line", "wavy", "arrow", "dimension"}:
        return line_item_state(item)
    if kind == "curved":
        return curved_item_state(item)
    return text_item_state(item)


def press_and_resize(view, controller, item, kind):
    controller.sync_handles()

    if kind in {"rectangle", "filled", "cloud", "ellipse"}:
        handle = item.mapToScene(item.rect().bottomRight())
        target = handle + QPointF(20, 15)
    elif kind in {"line", "wavy", "arrow", "dimension"}:
        if kind == "line":
            endpoint = item.line().p2()
        elif kind == "wavy":
            endpoint = QPointF(item._x2, item._y2)
        else:
            endpoint = QPointF(item._end)
        handle = item.mapToScene(endpoint)
        target = handle + QPointF(20, 15)
    elif kind == "curved":
        handle = item.mapToScene(item._ctrl)
        target = handle + QPointF(15, 20)
    else:
        handle = item.mapToScene(item.rect().topLeft())
        anchor = item.mapToScene(item.rect().bottomRight())
        target = anchor + (handle - anchor) * 1.3

    assert controller.handle_mouse_press(event_for(view, handle))
    first_target = handle + (target - handle) * 0.5
    assert controller.handle_mouse_move(event_for(view, first_target))
    assert controller.handle_mouse_move(event_for(view, target))
    assert controller.handle_mouse_release(event_for(view, target))


@pytest.mark.parametrize(
    "kind",
    [
        "rectangle",
        "filled",
        "cloud",
        "ellipse",
        "line",
        "wavy",
        "arrow",
        "dimension",
        "curved",
        "text",
    ],
)
def test_resize_annotation_is_one_atomic_history_entry_for_every_type(qapp, kind):
    view = make_fixture(qapp)
    item = make_item(view, kind)
    view.scene().addItem(item)
    item.setSelected(True)

    controller = AnnotationResizeController(view)
    old_state = item_state(item, kind)

    press_and_resize(view, controller, item, kind)

    new_state = item_state(item, kind)
    assert new_state != old_state
    assert view.history.stack.count() == 1

    view.history.undo()
    assert item_state(item, kind) == old_state

    view.history.redo()
    assert item_state(item, kind) == new_state

    controller.remove_handles()
    view.close()
