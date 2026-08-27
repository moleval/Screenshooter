"""
Модуль: controllers/pasted_image_controller.py
Описание: Контроллер вставленных изображений.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QPointF

from ..items.pasted_image_item import PastedImageItem
from ..history import AddPastedImageCommand, RemovePastedImageCommand


class PastedImageController:
    """
    Управляет вставленными изображениями:
    добавление, удаление, маркеры, рендеринг.
    """

    def __init__(self, view):
        self.view = view
        self.pasted_images = []

    def add_image(self, pixmap):
        """Добавляет вставленное изображение на сцену."""
        view = self.view
        item = PastedImageItem(pixmap, view)
        self.pasted_images.append(item)
        view.scene().addItem(item)
        center = view.mapToScene(view.viewport().rect().center())
        item.setPos(center - QPointF(pixmap.width() / 2, pixmap.height() / 2))
        viewport_rect = view.viewport().rect()
        max_w = viewport_rect.width() * 0.8
        max_h = viewport_rect.height() * 0.8
        if pixmap.width() > max_w or pixmap.height() > max_h:
            scale = min(max_w / pixmap.width(), max_h / pixmap.height())
            item.set_image_scale(scale)
        view.history.push(AddPastedImageCommand(view.scene(), item, view))
        view.scene().clearSelection()
        item.setSelected(True)
        item.show_handles()
        return item

    def remove_image(self, item):
        """Удаляет вставленное изображение."""
        if item in self.pasted_images:
            self.view.history.push(
                RemovePastedImageCommand(self.view.scene(), item, self.view))

    def clear_all(self):
        """Удаляет все вставленные изображения."""
        for item in self.pasted_images[:]:
            item.hide_handles()
            self.view.scene().removeItem(item)
        self.pasted_images.clear()

    def update_handles(self):
        """Показывает/скрывает маркеры в зависимости от выделения."""
        try:
            selected_ids = {id(it) for it in self.view.scene().selectedItems()
                            if isinstance(it, PastedImageItem)}
            for item in self.pasted_images:
                if sip.isdeleted(item):
                    continue
                if id(item) in selected_ids:
                    item.show_handles()
                else:
                    item.hide_handles()
        except RuntimeError:
            pass

    def hide_handles_for_render(self):
        """Скрывает маркеры перед рендерингом."""
        for item in self.pasted_images:
            item.hide_handles()

    def show_handles_after_render(self):
        """Показывает маркеры после рендеринга."""
        for item in self.pasted_images:
            if item.isSelected():
                item.show_handles()