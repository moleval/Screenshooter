"""
Модуль: history/composite_commands.py
Описание: Составные команды для групповых операций.
          Массовое удаление выбранных элементов, вставка из буфера обмена.
"""

from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QUndoCommand


class RemoveSelectedItemsCommand(QUndoCommand):
    """
    Команда группового удаления выбранных элементов.
    Удаляет одновременно обычные аннотации, вставленные изображения и зоны размытия.
    Откат возвращает всё сразу.
    """
    def __init__(self, scene, items, pasted_items, blur_indices, view):
        super().__init__("Удалить объекты")
        self.scene = scene
        self.items = items
        self.pasted_items = pasted_items
        self.blur_indices = sorted(blur_indices)
        self.view = view
        self.removed_items = []
        self.removed_pasted = []
        self.removed_blur_rects = []
        self.removed_blur_was_active = []
        self.active_text_removed = None

    def redo(self):
        # Удаляем обычные элементы
        for item in self.items:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
                self.removed_items.append(item)

        # Удаляем вставленные изображения
        for item in self.pasted_items:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
            if item in self.view.pasted_images:
                self.view.pasted_images.remove(item)
            item.hide_handles()
            self.removed_pasted.append(item)

        # Удаляем зоны размытия
        for idx in reversed(self.blur_indices):
            self.removed_blur_rects.append(QRectF(self.view.blur_controller.blur_regions[idx]))
            self.removed_blur_was_active.append(self.view.blur_controller.active_blur_index == idx)
            self.view.blur_controller._remove_blur_region_at(idx)

        if self.view.active_text_item in self.items + self.pasted_items:
            self.active_text_removed = self.view.active_text_item
            self.view.active_text_item = None

    def undo(self):
        # Возвращаем обычные элементы
        for item in self.removed_items:
            if item.scene() is not self.scene:
                self.scene.addItem(item)
            item.setVisible(True)

        # Возвращаем вставленные изображения
        for item in self.removed_pasted:
            if item.scene() is not self.scene:
                self.scene.addItem(item)
            if item not in self.view.pasted_images:
                self.view.pasted_images.append(item)
            item.setVisible(True)
            item.show_handles()
            item.update_handles()

        # Возвращаем зоны размытия
        for rect, was_active, idx in zip(reversed(self.removed_blur_rects),
                                          reversed(self.removed_blur_was_active),
                                          self.blur_indices):
            self.view.blur_controller._insert_blur_region_at(idx, rect)
            if was_active:
                self.view.blur_controller._set_active_blur(idx)

        if self.active_text_removed is not None:
            self.view.active_text_item = self.active_text_removed
            self.active_text_removed = None


class PasteItemsCommand(QUndoCommand):
    """Команда вставки элементов из внутреннего буфера обмена."""

    def __init__(self, scene, items):
        super().__init__("Вставить элементы")
        self.scene = scene
        self.items = items

    def redo(self):
        for item in self.items:
            if item.scene() is not self.scene:
                self.scene.addItem(item)
            item.setVisible(True)

    def undo(self):
        for item in self.items:
            item.setVisible(False)
            if item.scene() is self.scene:
                self.scene.removeItem(item)