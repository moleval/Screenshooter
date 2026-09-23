"""
Модуль: history/annotation_commands.py
Описание: команды Undo/Redo для изменения геометрии аннотаций.
"""

from PyQt5.QtWidgets import QUndoCommand


class ResizeAnnotationCommand(QUndoCommand):
    """Команда изменения геометрии аннотации."""

    def __init__(self, item, old_rect, new_rect, old_pos=None, new_pos=None):
        super().__init__("Изменить размер аннотации")
        self.item = item
        self.old_rect = old_rect
        self.new_rect = new_rect
        self.old_pos = old_pos
        self.new_pos = new_pos

    def _apply(self, rect, pos):
        self.item.setRect(rect)
        if pos is not None:
            self.item.setPos(pos)

    def redo(self):
        self._apply(self.new_rect, self.new_pos)

    def undo(self):
        self._apply(self.old_rect, self.old_pos)
