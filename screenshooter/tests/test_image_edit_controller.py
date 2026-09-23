"""
Smoke-тесты для ImageEditController: обрезка и поворот подложки,
работа с вставленными изображениями.
"""

import pytest
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QPixmap, QColor, QPen
from PyQt5.QtWidgets import QGraphicsScene

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
