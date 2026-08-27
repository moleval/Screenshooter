"""
Модуль: history/image_commands.py
Описание: Команды для вставленных изображений.
          Добавление, удаление, изменение размера, обрезка, поворот.
"""

from PyQt5.QtWidgets import QUndoCommand


class AddPastedImageCommand(QUndoCommand):
    """Команда добавления вставленного изображения."""

    def __init__(self, scene, item, view):
        super().__init__("Вставить изображение")
        self.scene = scene
        self.item = item
        self.view = view

    def redo(self):
        if self.item.scene() is not self.scene:
            self.scene.addItem(self.item)
        if self.item not in self.view.pasted_images:
            self.view.pasted_images.append(self.item)
        self.item.setVisible(True)
        self.item.update_handles()

    def undo(self):
        if self.item.scene() is self.scene:
            self.scene.removeItem(self.item)
        if self.item in self.view.pasted_images:
            self.view.pasted_images.remove(self.item)
        self.item.hide_handles()


class RemovePastedImageCommand(QUndoCommand):
    """Команда удаления вставленного изображения."""

    def __init__(self, scene, item, view):
        super().__init__("Удалить изображение")
        self.scene = scene
        self.item = item
        self.view = view

    def redo(self):
        if self.item.scene() is self.scene:
            self.scene.removeItem(self.item)
        if self.item in self.view.pasted_images:
            self.view.pasted_images.remove(self.item)
        self.item.hide_handles()

    def undo(self):
        if self.item.scene() is not self.scene:
            self.scene.addItem(self.item)
        if self.item not in self.view.pasted_images:
            self.view.pasted_images.append(self.item)
        self.item.setVisible(True)
        self.item.show_handles()
        self.item.update_handles()


class ResizePastedImageCommand(QUndoCommand):
    """Команда изменения размера вставленного изображения."""

    def __init__(self, item, old_scale, new_scale):
        super().__init__("Изменить размер изображения")
        self.item = item
        self.old_scale = old_scale
        self.new_scale = new_scale

    def redo(self):
        self.item.set_image_scale(self.new_scale)
        self.item.update_handles()

    def undo(self):
        self.item.set_image_scale(self.old_scale)
        self.item.update_handles()


class CropPastedImageCommand(QUndoCommand):
    """Команда обрезки вставленного изображения."""

    def __init__(self, item, old_original, new_original, old_pos, old_scale, crop_scene_pos):
        super().__init__("Обрезать изображение")
        self.item = item
        self.old_original = old_original
        self.new_original = new_original
        self.old_pos = old_pos
        self.old_scale = old_scale
        self.crop_scene_pos = crop_scene_pos

    def redo(self):
        self.item.setPos(self.crop_scene_pos)
        self.item.original_pixmap = self.new_original
        self.item.scale = 1.0
        self.item.setPixmap(self.new_original)
        self.item.update_handles()

    def undo(self):
        self.item.setPos(self.old_pos)
        self.item.original_pixmap = self.old_original
        self.item.scale = self.old_scale
        self.item.set_image_scale(self.old_scale)
        self.item.update_handles()


class RotatePastedImageCommand(QUndoCommand):
    """Команда поворота вставленного изображения."""

    def __init__(self, item, old_original, new_original, old_pos, old_scale):
        super().__init__("Повернуть изображение")
        self.item = item
        self.old_original = old_original
        self.new_original = new_original
        self.old_pos = old_pos
        self.old_scale = old_scale

    def redo(self):
        self.item.original_pixmap = self.new_original
        self.item.scale = 1.0
        self.item.setPixmap(self.new_original)
        self.item.update_handles()

    def undo(self):
        self.item.setPos(self.old_pos)
        self.item.original_pixmap = self.old_original
        self.item.scale = self.old_scale
        self.item.set_image_scale(self.old_scale)
        self.item.update_handles()