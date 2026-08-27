"""
Модуль: history/item_commands.py
Описание: Команды для обычных элементов сцены (аннотаций).
"""

from PyQt5.QtWidgets import QUndoCommand


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