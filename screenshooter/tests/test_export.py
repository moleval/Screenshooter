"""
Регрессии экспорта: служебные crop/annotation маркеры не должны попадать
в итоговый QImage.
"""

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QColor, QPixmap, QPen
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsScene

from screenshooter.export import Exporter
from screenshooter.items.shape_items import RectangleItem
from screenshooter.view import EditorView


class SpyScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.visible_items_during_render = []

    def render(self, painter, target, source):
        self.visible_items_during_render = [
            item for item in self.items() if item.isVisible()
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
