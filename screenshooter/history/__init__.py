"""
Модуль: history/__init__.py
Описание: Менеджер истории Undo/Redo на базе QUndoStack.
          Содержит команды для добавления, удаления, перемещения, изменения стиля,
          обрезки, поворота и управления зонами размытия.
          Все операции с графической сценой откатываются через эти команды.
"""

from PyQt5 import sip
from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtGui import QPen, QColor, QPixmap
from PyQt5.QtWidgets import QUndoStack, QUndoCommand, QGraphicsItem, QGraphicsTextItem


class HistoryManager:
    """Обёртка над QUndoStack для работы с графической сценой."""

    def __init__(self):
        self.stack = QUndoStack()

    def push(self, command):
        self.stack.push(command)

    def undo(self):
        self.stack.undo()

    def redo(self):
        self.stack.redo()

    def clear(self):
        self.stack.clear()

    def can_undo(self):
        if sip.isdeleted(self.stack):
            return False
        return self.stack.canUndo()

    def can_redo(self):
        if sip.isdeleted(self.stack):
            return False
        return self.stack.canRedo()


# --- Команды для обычных элементов сцены ---
class AddItemCommand(QUndoCommand):
    """Команда добавления элемента в сцену."""

    def __init__(self, scene, item):
        super().__init__("Добавить объект")
        self.scene = scene
        self.item = item

    def redo(self):
        if self.item.scene() is not self.scene:
            self.scene.addItem(self.item)
        self.item.setVisible(True)

    def undo(self):
        if self.item.scene() is self.scene:
            self.scene.removeItem(self.item)


class RemoveItemCommand(QUndoCommand):
    """Команда удаления элемента из сцены."""

    def __init__(self, scene, item):
        super().__init__("Удалить объект")
        self.scene = scene
        self.item = item

    def redo(self):
        if self.item.scene() is self.scene:
            self.scene.removeItem(self.item)

    def undo(self):
        if self.item.scene() is not self.scene:
            self.scene.addItem(self.item)
        self.item.setVisible(True)


class MoveItemCommand(QUndoCommand):
    """Команда перемещения одного элемента."""

    def __init__(self, item, old_pos, new_pos):
        super().__init__("Переместить объект")
        self.item = item
        self.old_pos = old_pos
        self.new_pos = new_pos

    def redo(self):
        self.item.setPos(self.new_pos)

    def undo(self):
        self.item.setPos(self.old_pos)


class MoveItemsCommand(QUndoCommand):
    """Команда перемещения нескольких элементов одновременно."""

    def __init__(self, items, old_positions, new_positions):
        super().__init__("Переместить объекты")
        self.items = items
        self.old_positions = old_positions
        self.new_positions = new_positions

    def redo(self):
        for item, pos in zip(self.items, self.new_positions):
            item.setPos(pos)

    def undo(self):
        for item, pos in zip(self.items, self.old_positions):
            item.setPos(pos)


class ResizeItemCommand(QUndoCommand):
    """Команда изменения геометрии прямоугольных/эллиптических элементов."""

    def __init__(self, item, old_rect, new_rect):
        super().__init__("Изменить размер")
        self.item = item
        self.old_rect = old_rect
        self.new_rect = new_rect

    def redo(self):
        self.item.setRect(self.new_rect)

    def undo(self):
        self.item.setRect(self.old_rect)


class ChangePenCommand(QUndoCommand):
    """Команда изменения пера (цвет/толщина/стиль)."""

    def __init__(self, item, old_pen, new_pen):
        super().__init__("Изменить стиль")
        self.item = item
        self.old_pen = old_pen
        self.new_pen = new_pen

    def redo(self):
        self.item.setPen(self.new_pen)

    def undo(self):
        self.item.setPen(self.old_pen)


class ChangeTextCommand(QUndoCommand):
    """Команда изменения текста."""

    def __init__(self, item, old_text, new_text):
        super().__init__("Изменить текст")
        self.item = item
        self.old_text = old_text
        self.new_text = new_text

    def redo(self):
        self.item.setPlainText(self.new_text)

    def undo(self):
        self.item.setPlainText(self.old_text)


# --------------------------------------------------------------
# Команды для редактирования фонового изображения
# --------------------------------------------------------------

class CropCommand(QUndoCommand):
    """
    Команда обрезки фонового изображения.
    Сохраняет состояние зон размытия, чтобы откат мог их восстановить.
    """

    def __init__(self, scene, background_item, old_pixmap, new_pixmap, items_to_remove,
                 controller=None, crop_rect=None):
        super().__init__("Обрезка")
        self.scene = scene
        self.background_item = background_item
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap
        self.items_to_remove = items_to_remove
        self.removed_items = []
        self.controller = controller
        self.crop_rect = crop_rect

        if controller is not None:
            self.blur_state = controller._get_blur_state()
        else:
            self.blur_state = None

    def redo(self):
        for item in self.items_to_remove:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
                self.removed_items.append(item)

        self.background_item.setPixmap(self.new_pixmap)
        self.background_item.update()

        if self.controller is not None and self.crop_rect is not None:
            self.controller._apply_crop_to_blur_regions(self.crop_rect)
            self.controller.view.setSceneRect(QRectF(self.new_pixmap.rect()))
            self.controller.view.update_resolution_from_background()
            self.controller.view.fit_background_to_view()

    def undo(self):
        self.background_item.setPixmap(self.old_pixmap)
        self.background_item.update()

        for item in self.removed_items:
            if item.scene() is not self.scene:
                self.scene.addItem(item)
        self.removed_items.clear()

        if self.controller is not None and self.blur_state is not None:
            self.controller._restore_blur_state(self.blur_state)
            self.controller.view.setSceneRect(QRectF(self.old_pixmap.rect()))
            self.controller.view.update_resolution_from_background()
            self.controller.view.fit_background_to_view()


class RotateCommand(QUndoCommand):
    """
    Команда поворота фонового изображения.
    Растеризует аннотации, но сохраняет зоны размытия для undo.
    """

    def __init__(self, scene, background_item, old_pixmap, new_pixmap, items_to_remove,
                 controller=None):
        super().__init__("Поворот")
        self.scene = scene
        self.background_item = background_item
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap
        self.items_to_remove = items_to_remove
        self.removed_items = []
        self.controller = controller

        if controller is not None:
            self.blur_state = controller._get_blur_state()
        else:
            self.blur_state = None

    def redo(self):
        for item in self.items_to_remove:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
                self.removed_items.append(item)

        self.background_item.setPixmap(self.new_pixmap)
        self.background_item.update()

        if self.controller is not None:
            self.controller._clear_blur_regions()
            self.controller.view.setSceneRect(QRectF(self.new_pixmap.rect()))
            self.controller.view.update_resolution_from_background()
            self.controller.view.fit_background_to_view()

    def undo(self):
        self.background_item.setPixmap(self.old_pixmap)
        self.background_item.update()

        for item in self.removed_items:
            if item.scene() is not self.scene:
                self.scene.addItem(item)
        self.removed_items.clear()

        if self.controller is not None and self.blur_state is not None:
            self.controller._restore_blur_state(self.blur_state)
            self.controller.view.setSceneRect(QRectF(self.old_pixmap.rect()))
            self.controller.view.update_resolution_from_background()
            self.controller.view.fit_background_to_view()


class BlurCommand(QUndoCommand):
    """Команда размытия области фонового изображения."""

    def __init__(self, background_item, old_pixmap, new_pixmap):
        super().__init__("Размытие")
        self.background_item = background_item
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap

    def redo(self):
        self.background_item.setPixmap(self.new_pixmap)
        self.background_item.update()

    def undo(self):
        self.background_item.setPixmap(self.old_pixmap)
        self.background_item.update()


# --------------------------------------------------------------
# Команды для зон размытия
# --------------------------------------------------------------

class AddBlurRegionCommand(QUndoCommand):
    """Добавление новой зоны размытия."""

    def __init__(self, controller, rect):
        super().__init__("Добавить зону размытия")
        self.controller = controller
        self.rect = rect

    def redo(self):
        self.controller._add_blur_region_internal(self.rect)

    def undo(self):
        self.controller._remove_last_blur_region()


class RemoveBlurRegionCommand(QUndoCommand):
    """Удаление зоны размытия по индексу."""

    def __init__(self, controller, index):
        super().__init__("Удалить зону размытия")
        self.controller = controller
        self.index = index
        self.rect = None

    def redo(self):
        self.rect = self.controller._remove_blur_region_at(self.index)

    def undo(self):
        if self.rect is not None:
            self.controller._insert_blur_region_at(self.index, self.rect)
            self.controller._set_active_blur(self.index)


class MoveBlurRegionCommand(QUndoCommand):
    """Перемещение зоны размытия."""

    def __init__(self, controller, index, old_rect, new_rect):
        super().__init__("Переместить зону размытия")
        self.controller = controller
        self.index = index
        self.old_rect = old_rect
        self.new_rect = new_rect

    def redo(self):
        self.controller._update_blur_region_rect(self.index, self.new_rect)

    def undo(self):
        self.controller._update_blur_region_rect(self.index, self.old_rect)


class ResizeBlurRegionCommand(QUndoCommand):
    """Изменение размера зоны размытия."""

    def __init__(self, controller, index, old_rect, new_rect):
        super().__init__("Изменить размер зоны размытия")
        self.controller = controller
        self.index = index
        self.old_rect = old_rect
        self.new_rect = new_rect

    def redo(self):
        self.controller._update_blur_region_rect(self.index, self.new_rect)

    def undo(self):
        self.controller._update_blur_region_rect(self.index, self.old_rect)


# --------------------------------------------------------------
# Команды для вставленных изображений
# --------------------------------------------------------------

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


# --------------------------------------------------------------
# Команда массового удаления выбранных элементов
# --------------------------------------------------------------

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
            self.removed_blur_rects.append(QRectF(self.view.image_editor.blur_regions[idx]))
            self.removed_blur_was_active.append(self.view.image_editor.active_blur_index == idx)
            self.view.image_editor._remove_blur_region_at(idx)

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
            self.view.image_editor._insert_blur_region_at(idx, rect)
            if was_active:
                self.view.image_editor._set_active_blur(idx)

        if self.active_text_removed is not None:
            self.view.active_text_item = self.active_text_removed
            self.active_text_removed = None


# --------------------------------------------------------------
# Команда вставки элементов из буфера обмена
# --------------------------------------------------------------

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