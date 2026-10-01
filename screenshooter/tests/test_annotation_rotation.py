"""
Тесты поворота обычных аннотаций через AnnotationResizeController.
"""

import math

import pytest
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPen
from PyQt5.QtWidgets import QApplication, QGraphicsScene

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
from screenshooter.view import EditorView


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def make_event(view, scene_pos):
    return type(
        "Event",
        (),
        {
            "button": lambda self: Qt.LeftButton,
            "pos": lambda self: view.mapFromScene(scene_pos),
            "modifiers": lambda self: Qt.NoModifier,
        },
    )()


def make_items(view):
    pen = QPen(Qt.red, 2)
    return [
        ("rectangle", RectangleItem(QRectF(40, 40, 80, 60), QPen(pen))),
        ("ellipse", EllipseItem(QRectF(40, 40, 80, 60), QPen(pen))),
        ("filled", FilledRectItem(QRectF(40, 40, 80, 60), QColor(255, 0, 0))),
        ("cloud", CloudItem(QRectF(40, 40, 80, 60), QPen(pen))),
        ("line", LineItem(40, 40, 120, 90, QPen(pen))),
        ("wavy", WavyLineItem(40, 40, 120, 90, QPen(pen))),
        (
            "arrow",
            ArrowItem(QPointF(40, 40), QPointF(120, 90), QPen(pen)),
        ),
        (
            "curved",
            CurvedArrowItem(
                QPointF(40, 40),
                QPointF(120, 90),
                QPointF(90, 120),
                QPen(pen),
            ),
        ),
        (
            "dimension",
            DimensionItem(QPointF(40, 40), QPointF(120, 90), QPen(pen)),
        ),
    ]


@pytest.mark.parametrize(
    "name, expected_handles",
    [
        ("rectangle", 9),
        ("ellipse", 9),
        ("filled", 9),
        ("cloud", 9),
        ("line", 3),
        ("wavy", 3),
        ("arrow", 3),
        ("curved", 4),
        ("dimension", 3),
    ],
)
def test_annotation_has_rotation_handle_with_existing_handles(
    qapp, name, expected_handles
):
    view = EditorView(QGraphicsScene())
    items = dict(make_items(view))
    item = items[name]
    view.scene().addItem(item)
    item.setSelected(True)

    controller = view.annotation_resize_controller
    controller.sync_handles()

    assert "rotate" in controller.handles.handle_items
    assert len(controller.handles.handle_items) == expected_handles
    assert controller.handles.positions["rotate"] != item.mapToScene(
        item.boundingRect().center()
    )

    view.close()


def test_text_has_rotation_handle(qapp):
    view = EditorView(QGraphicsScene())
    item = TextItem(view)
    item.setPlainText("Rotation")
    item.setPos(100, 100)
    view.scene().addItem(item)
    item.setSelected(True)

    controller = view.annotation_resize_controller
    controller.sync_handles()

    assert set(controller.handles.handle_items) == {
        "tl", "tr", "bl", "br", "rotate"
    }

    view.close()


def test_rectangle_rotation_keeps_center_and_supports_undo_redo(qapp):
    view = EditorView(QGraphicsScene())
    item = RectangleItem(QRectF(40, 40, 80, 60), QPen(Qt.red, 2))
    view.scene().addItem(item)
    item.setSelected(True)

    controller = view.annotation_resize_controller
    controller.sync_handles()

    handle = controller.handles.positions["rotate"]
    center_before = item.mapToScene(item.boundingRect().center())

    assert controller.handle_mouse_press(make_event(view, handle))
    assert controller.handle_mouse_release(make_event(view, handle))

    center_after = item.mapToScene(item.boundingRect().center())

    assert math.isclose(center_before.x(), center_after.x(), abs_tol=1e-6)
    assert math.isclose(center_before.y(), center_after.y(), abs_tol=1e-6)
    assert item.rotation() == 90.0

    view.history.undo()
    assert math.isclose(item.rotation(), 0.0, abs_tol=1e-9)

    view.history.redo()
    assert math.isclose(item.rotation(), 90.0, abs_tol=1e-9)

    view.close()
