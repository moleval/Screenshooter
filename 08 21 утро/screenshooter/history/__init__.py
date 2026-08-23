"""Менеджер истории Undo/Redo на базе QUndoStack."""

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
        return self.stack.canUndo()

    def can_redo(self):
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
    Применяет новый QPixmap и удаляет аннотации, не попавшие в область обрезки.
    """

    def __init__(self, scene, background_item, old_pixmap, new_pixmap, items_to_remove):
        super().__init__("Обрезка")
        self.scene = scene
        self.background_item = background_item
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap
        self.items_to_remove = items_to_remove
        self.removed_items = []

    def redo(self):
        # Удаляем аннотации, не попавшие в область
        for item in self.items_to_remove:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
                self.removed_items.append(item)

        # Применяем новую картинку
        self.background_item.setPixmap(self.new_pixmap)
        self.background_item.update()

    def undo(self):
        # Возвращаем старую картинку
        self.background_item.setPixmap(self.old_pixmap)
        self.background_item.update()

        # Возвращаем удалённые элементы
        for item in self.removed_items:
            if item.scene() is not self.scene:
                self.scene.addItem(item)
        self.removed_items.clear()


class RotateCommand(QUndoCommand):
    """
    Команда поворота фонового изображения.
    Растеризует все аннотации в изображение, затем поворачивает фон.
    """

    def __init__(self, scene, background_item, old_pixmap, new_pixmap, items_to_remove):
        super().__init__("Поворот")
        self.scene = scene
        self.background_item = background_item
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap
        self.items_to_remove = items_to_remove
        self.removed_items = []

    def redo(self):
        # Удаляем все аннотации (они уже включены в новый QPixmap)
        for item in self.items_to_remove:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
                self.removed_items.append(item)

        # Применяем повёрнутое изображение
        self.background_item.setPixmap(self.new_pixmap)
        self.background_item.update()

    def undo(self):
        # Возвращаем старое изображение
        self.background_item.setPixmap(self.old_pixmap)
        self.background_item.update()

        # Восстанавливаем аннотации
        for item in self.removed_items:
            if item.scene() is not self.scene:
                self.scene.addItem(item)
        self.removed_items.clear()


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