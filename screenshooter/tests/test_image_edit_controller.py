"""
Smoke-тесты для ImageEditController: обрезка и поворот подложки,
работа с вставленными изображениями.
"""

import pytest
from PyQt5.QtCore import QRectF, QPointF
from PyQt5.QtGui import QPixmap, QColor, QPen
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsEllipseItem

from screenshooter.items.pasted_image_item import PastedImageItem
from screenshooter.items.shape_items import RectangleItem
from screenshooter.view import EditorView


@pytest.fixture
def setup_editor(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)

    pm = QPixmap(100, 80)
    pm.fill(QColor("gray"))
    view.set_background_from_pixmap(pm)

    return view


def test_start_and_cancel_crop_mode(setup_editor):
    view = setup_editor
    assert view.crop_mode is False

    view.start_crop_mode()
    assert view.crop_mode is True

    view.cancel_crop_mode()
    assert view.crop_mode is False


def test_rotate_background(setup_editor):
    view = setup_editor
    original_width = view.background_item.pixmap().width()
    original_height = view.background_item.pixmap().height()

    view.rotate_image(90)

    assert view.background_item.pixmap().width() == original_height
    assert view.background_item.pixmap().height() == original_width


def test_crop_pasted_image_keeps_scale(setup_editor):
    view = setup_editor

    pm = QPixmap(50, 50)
    pm.fill(QColor("blue"))
    item = view.add_pasted_image(pm)

    item.setSelected(True)
    view.start_crop_mode()
    assert view.crop_mode is True

    target = item
    target_rect = target.mapRectToScene(target.boundingRect())
    view.image_editor.crop_rect = target_rect
    view.apply_crop()

    assert view.image_editor.crop_mode is False
    assert target.scene() is not None
def test_crop_removes_partially_cut_annotation(setup_editor):
    view = setup_editor
    controller = view.image_editor

    inside = RectangleItem(QRectF(30, 30, 10, 10), QPen(QColor("red"), 2))
    partial = RectangleItem(QRectF(10, 30, 20, 10), QPen(QColor("red"), 2))
    outside = RectangleItem(QRectF(85, 30, 10, 10), QPen(QColor("red"), 2))

    view.scene().addItem(inside)
    view.scene().addItem(partial)
    view.scene().addItem(outside)

    crop = QRectF(20, 20, 60, 40)
    items_to_remove, items_to_shift, _, _ = controller._collect_items_for_crop(crop)

    assert partial in items_to_remove
    assert outside in items_to_remove
    assert inside in items_to_shift
    assert partial not in items_to_shift
    assert outside not in items_to_shift


def test_rotate_undo_does_not_restore_annotation_handles_as_scene_items(setup_editor):
    view = setup_editor
    item = RectangleItem(QRectF(20, 20, 30, 20), QPen(QColor("red"), 2))
    view.scene().addItem(item)
    item.setSelected(True)

    controller = view.annotation_resize_controller
    controller.sync_handles()
    assert controller.handles is not None
    assert len(controller.handles.handle_items) == 8

    view.rotate_image(90)

    # После поворота служебные ручки не должны оставаться в сцене.
    assert not [
        scene_item for scene_item in view.scene().items()
        if isinstance(scene_item, QGraphicsEllipseItem)
        and scene_item.zValue() == 2000
    ]

    view.undo()

    assert item.scene() is view.scene()
    item.setSelected(True)
    controller.sync_handles()
    assert controller.handles is not None
    expected = controller._handle_points(
        item.mapRectToScene(item.rect()).normalized(), item)
    assert controller.handles.positions == expected

    old_positions = dict(controller.handles.positions)
    item.setPos(item.pos() + QPointF(10, 5))
    controller.sync_handles()

    assert controller.handles.positions != old_positions
    assert controller.handles.positions == controller._handle_points(
        item.mapRectToScene(item.rect()).normalized(), item)
