"""
Smoke-тесты для ImageEditController: обрезка и поворот подложки,
работа с вставленными изображениями.
"""

import pytest
from PyQt5.QtCore import QRectF, QPointF
from PyQt5.QtGui import QPixmap, QColor, QPen
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsEllipseItem

from screenshooter.items.pasted_image_item import PastedImageItem
from screenshooter.items.blur_region_item import BlurRegionItem
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


def test_trim_keeps_blur_in_scene_coordinates_and_background_geometry(setup_editor):
    view = setup_editor
    bg = view.background_item

    image = bg.pixmap().toImage()
    image.fill(QColor("white"))
    for y in range(20, 80):
        for x in range(20, 100):
            image.setPixelColor(x, y, QColor("gray"))
    bg.setPixmap(QPixmap.fromImage(image))

    view.blur_controller._add_blur_region_internal(QRectF(85, 40, 20, 20))
    assert len(view.blur_controller.blur_region_items) == 1

    assert view.trim_white_fields() is True

    # После trim подложка начинается в старых scene-координатах (20, 20).
    # Blur остаётся в scene-координатах и обрезается только пересечением
    # с новой границей: (85, 40, 15, 20).
    bg_rect = bg.sceneBoundingRect().normalized()
    blur = view.blur_controller.blur_region_items[0]
    blur_rect = blur.sceneBoundingRect().normalized()
    assert bg_rect == QRectF(20, 20, 80, 60)
    assert blur.rect() == QRectF(85, 40, 15, 20)

    old_bg_rect = QRectF(bg_rect)
    old_blur_rect = QRectF(blur_rect)

    # Перемещение обрезанного blur не должно менять геометрию подложки
    # или внезапно создавать новое белое поле.
    moved = old_blur_rect.translated(10, 0)
    view.blur_controller._update_blur_region_rect(0, moved)

    assert bg.sceneBoundingRect().normalized() == old_bg_rect
    assert view.blur_controller.blur_region_items[0].sceneBoundingRect().normalized() == moved
    assert bg.pixmap().size().width() == 80
    assert bg.pixmap().size().height() == 60
    assert not bg.pixmap().isNull()


def test_trim_removes_pasted_image_handles_with_removed_image(setup_editor):
    view = setup_editor
    scene = view.scene()

    image = QPixmap(30, 30)
    image.fill(QColor("blue"))
    pasted = view.add_pasted_image(image, scene_pos=QPointF(85, 35))

    assert pasted in view.pasted_images
    assert pasted.handles is not None
    assert [
        item for item in scene.items()
        if isinstance(item, QGraphicsEllipseItem) and item.zValue() == 2000
    ]

    # Обрезаем правое белое поле так, чтобы вставленная картинка была удалена.
    bg = view.background_item
    bg_image = bg.pixmap().toImage()
    bg_image.fill(QColor("white"))
    for y in range(20, 60):
        for x in range(20, 80):
            bg_image.setPixelColor(x, y, QColor("gray"))
    bg.setPixmap(QPixmap.fromImage(bg_image))

    assert view.trim_white_fields() is True
    assert pasted.scene() is None
    assert pasted not in view.pasted_images
    assert pasted.handles is None
    assert not [
        item for item in scene.items()
        if isinstance(item, QGraphicsEllipseItem) and item.zValue() == 2000
    ]

    # Последующая операция, которая расширяет подложку по реальному
    # содержимому, не должна учитывать ручки удалённой картинки.
    old_size = bg.pixmap().size()
    view.expand_background_to_content(margin=0, threshold=1)
    assert bg.pixmap().size() == old_size


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

def test_trim_white_fields_keeps_annotation_moved_outside_background(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)

    pm = QPixmap(120, 100)
    pm.fill(QColor("white"))
    image = pm.toImage()
    for y in range(20, 80):
        for x in range(20, 100):
            image.setPixelColor(x, y, QColor("gray"))
    view.set_background_from_pixmap(QPixmap.fromImage(image))

    annotation = RectangleItem(
        QRectF(105, 40, 10, 10), QPen(QColor("red"), 2)
    )
    scene.addItem(annotation)
    annotation.setSelected(True)
    view.annotation_resize_controller.sync_handles()

    assert view.trim_white_fields() is True
    # Белая рамка определяется по содержимому подложки, а не по аннотации.
    assert view.background_item.pixmap().width() == 80
    assert annotation.scene() is None
    # Ручки удалённой аннотации не должны остаться отдельными QGraphicsItem.
    assert not [
        item for item in scene.items()
        if isinstance(item, QGraphicsEllipseItem) and item.zValue() == 2000
    ]

    view.undo()
    assert view.background_item.pixmap().size() == pm.size()
    assert annotation.scene() is scene
