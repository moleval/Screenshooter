"""Команды Undo/Redo для изменения геометрии аннотаций."""

from PyQt5.QtWidgets import QUndoCommand

from ..items import LineItem, WavyLineItem, ArrowItem, DimensionItem


class ResizeAnnotationCommand(QUndoCommand):
    """Атомарное изменение геометрии аннотации через её нативный API."""

    def __init__(self, item, old_rect=None, new_rect=None, old_pos=None,
                 new_pos=None, old_geometry=None, new_geometry=None):
        super().__init__("Изменить размер аннотации")
        self.item = item
        self.old_rect = old_rect
        self.new_rect = new_rect
        self.old_pos = old_pos
        self.new_pos = new_pos
        self.old_geometry = old_geometry
        self.new_geometry = new_geometry

    def _apply(self, rect, pos, geometry):
        if geometry is not None:
            start, end = geometry
            if isinstance(self.item, LineItem):
                self.item.setLine(start.x(), start.y(), end.x(), end.y())
            elif isinstance(self.item, WavyLineItem):
                self.item.set_points(start.x(), start.y(), end.x(), end.y())
            elif isinstance(self.item, ArrowItem):
                self.item.set_line(start, end)
            elif isinstance(self.item, DimensionItem):
                self.item.setRect(start, end)
            else:
                raise TypeError("Unsupported annotation geometry")
        elif rect is not None:
            self.item.setRect(rect)

        if pos is not None:
            self.item.setPos(pos)

    def redo(self):
        self._apply(self.new_rect, self.new_pos, self.new_geometry)

    def undo(self):
        self._apply(self.old_rect, self.old_pos, self.old_geometry)
