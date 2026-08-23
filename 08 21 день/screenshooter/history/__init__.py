"""Менеджер истории Undo/Redo на базе QUndoStack."""

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
    """Команда перемещения элемента."""

    def __init__(self, item, old_pos, new_pos):
        super().__init__("Переместить объект")
        self.item = item
        self.old_pos = old_pos
        self.new_pos = new_pos

    def redo(self):
        self.item.setPos(self.new_pos)

    def undo(self):
        self.item.setPos(self.old_pos)


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
    Сохраняет состояние зон размытия и обрезает их вместе с изображением.
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

        # Сохраняем состояние зон размытия до удаления
        if controller is not None:
            self.blur_state = controller._get_blur_state()
        else:
            self.blur_state = None

    def redo(self):
        # Удаляем аннотации, не попавшие в область обрезки
        for item in self.items_to_remove:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
                self.removed_items.append(item)

        # Применяем новый pixmap
        self.background_item.setPixmap(self.new_pixmap)
        self.background_item.update()

        # Обрезаем зоны размытия
        if self.controller is not None and self.crop_rect is not None:
            self.controller._apply_crop_to_blur_regions(self.crop_rect)
            self.controller.view.setSceneRect(QRectF(self.new_pixmap.rect()))
            self.controller.view.update_resolution_from_background()
            self.controller.view.fit_background_to_view()

    def undo(self):
        # Возвращаем старый pixmap
        self.background_item.setPixmap(self.old_pixmap)
        self.background_item.update()

        # Восстанавливаем аннотации
        for item in self.removed_items:
            if item.scene() is not self.scene:
                self.scene.addItem(item)
        self.removed_items.clear()

        # Восстанавливаем зоны размытия
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
        # Удаляем аннотации (растеризация)
        for item in self.items_to_remove:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
                self.removed_items.append(item)

        # Применяем повёрнутое изображение
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
# Команды для зон размытия (множественные)
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