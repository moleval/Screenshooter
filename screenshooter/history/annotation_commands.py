"""
Модуль: history/annotation_commands.py
Описание: команды Undo/Redo для изменения геометрии аннотаций.
"""

from PyQt5.QtWidgets import QUndoCommand


class ResizeAnnotationCommand(QUndoCommand):
    """Команда изменения геометрии аннотации."""

    def __init__(self, item, old_rect, new_rect):
        super().__init__("Изменить размер аннотации")
        self.item = item
        self.old_rect = old_rect
        self.new_rect = new_rect

    def redo(self):
        self.item.setRect(self.new_rect)

    def undo(self):
        self.item.setRect(self.old_rect)
