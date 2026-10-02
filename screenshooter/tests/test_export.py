"""
Регрессии экспорта: служебные crop/annotation маркеры не должны попадать
в итоговый QImage.
"""

from PyQt5.QtCore import QRectF, QPointF
from PyQt5.QtGui import QColor, QPixmap, QPen
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsScene
from types import SimpleNamespace

from screenshooter.export import Exporter
from screenshooter.items.shape_items import RectangleItem
from screenshooter.view import EditorView


class SpyScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.visible_items_during_render = []
        self.rendering_items_during_render = []

    def render(self, painter, target, source):
        self.visible_items_during_render = [
            item for item in self.items() if item.isVisible()
        ]
        self.rendering_items_during_render = [
            item for item in self.items()
            if getattr(item, "_rendering", False)
        ]
        self.selected_items_during_render = self.selectedItems()
        return super().render(painter, target, source)


def test_export_hides_annotation_and_crop_ui(qapp):
    scene = SpyScene()
    view = EditorView(scene)

    pixmap = QPixmap(100, 80)
    pixmap.fill(QColor("white"))
    view.set_background_from_pixmap(pixmap)

    annotation = RectangleItem(
        QRectF(20, 20, 30, 20), QPen(QColor("red"), 2)
    )
    scene.addItem(annotation)
    annotation.setSelected(True)
    view.annotation_resize_controller.sync_handles()
    assert view.annotation_resize_controller.handles is not None

    view.start_crop_mode()
    assert view.image_editor.overlay.crop_rect_item is not None
    assert view.image_editor.overlay.aspect_guide_items

    exporter = Exporter(view, scene)
    image = exporter.render_scene_to_image()

    assert image is not None
    assert view.annotation_resize_controller.handles is not None

    visible = scene.visible_items_during_render
    assert view.image_editor.overlay.crop_rect_item not in visible
    assert not any(
        item in visible
        for item in view.image_editor.overlay.aspect_guide_items
    )
    assert not any(
        item.zValue() == 2000
        for item in visible
    )
    assert scene.selected_items_during_render == []

    # После экспорта состояние UI и selection восстанавливаются.
    assert view.image_editor.overlay.crop_rect_item.isVisible()
    assert all(
        item.isVisible()
        for item in view.image_editor.overlay.aspect_guide_items
    )
    assert annotation.isSelected()


def test_export_keeps_blur_but_hides_blur_ui(qapp):
    scene = SpyScene()
    view = EditorView(scene)

    pixmap = QPixmap(120, 80)
    image = pixmap.toImage().convertToFormat(pixmap.toImage().format())
    for x in range(120):
        color = QColor("black") if x < 60 else QColor("white")
        for y in range(80):
            image.setPixelColor(x, y, color)
    pixmap = QPixmap.fromImage(image)
    view.set_background_from_pixmap(pixmap)

    view.blur_controller.apply_blur(QRectF(45, 20, 30, 40))
    blur_item = view.blur_controller.blur_region_items[0]
    assert not blur_item.blurred_pixmap.isNull()
    blur_item.setSelected(True)
    blur_item.set_mode("active")
    assert blur_item.handles is not None

    settings = SimpleNamespace(
        save_directory="",
        enhancer_enabled=False,
        enhancer_scale=1.0,
        enhancer_text=True,
        enhancer_lines=True,
        enhancer_ui=True,
        enhancer_geometry=True,
        enhancer_color_mode="auto",
    )
    exporter = Exporter(view, scene, settings)
    exported = exporter.render_scene_to_image()

    assert exported is not None
    assert not exported.isNull()
    assert blur_item in scene.visible_items_during_render
    assert blur_item in scene.rendering_items_during_render
    assert not any(item.zValue() == 2000 for item in scene.visible_items_during_render)
    assert not blur_item._rendering
    assert exported.pixelColor(59, 40) != QColor("black")
    assert exported.pixelColor(60, 40) != QColor("white")
    assert blur_item.isSelected()
    assert blur_item.handles is not None


def test_export_applies_enhancer_to_rendered_scene(qapp):
    scene = SpyScene()
    view = EditorView(scene)

    pixmap = QPixmap(40, 30)
    pixmap.fill(QColor("white"))
    view.set_background_from_pixmap(pixmap)

    settings = SimpleNamespace(
        save_directory="",
        enhancer_enabled=True,
        enhancer_scale=1.0,
        enhancer_text=True,
        enhancer_lines=True,
        enhancer_ui=True,
        enhancer_geometry=True,
        enhancer_color_mode="invert",
    )

    exporter = Exporter(view, scene, settings)
    exported = exporter.render_scene_to_image()

    assert exported is not None
    assert exported.size() == pixmap.size()
    assert exported.pixelColor(0, 0).red() == 0
    assert exported.pixelColor(0, 0).green() == 0
    assert exported.pixelColor(0, 0).blue() == 0


def test_export_skips_enhancer_when_disabled(qapp):
    scene = SpyScene()
    view = EditorView(scene)

    pixmap = QPixmap(40, 30)
    pixmap.fill(QColor("white"))
    view.set_background_from_pixmap(pixmap)

    settings = SimpleNamespace(
        save_directory="",
        enhancer_enabled=False,
        enhancer_scale=1.0,
        enhancer_text=True,
        enhancer_lines=True,
        enhancer_ui=True,
        enhancer_geometry=True,
        enhancer_color_mode="invert",
    )

    exporter = Exporter(view, scene, settings)
    exported = exporter.render_scene_to_image()

    assert exported is not None
    assert exported.size() == pixmap.size()
    assert exported.pixelColor(0, 0).red() == 255
    assert exported.pixelColor(0, 0).green() == 255
    assert exported.pixelColor(0, 0).blue() == 255
