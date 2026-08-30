"""
Модуль: tools/rect_tool.py
Описание: Инструмент рисования прямоугольника.
          Поддерживает режимы: прямоугольник (rect), квадрат (square), заливка (filled).
"""

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPen, QColor

from .base_tool import BaseTool
from ..items import RectangleItem, FilledRectItem


class RectTool(BaseTool):
    def __init__(self, view):
        super().__init__(view)
        self.start_point = None

    def start_draw(self, scene_pos: QPointF):
        """Создаёт временный элемент в зависимости от режима shape_mode."""
        self.start_point = scene_pos

        if self.view.shape_mode == 'filled':
            # Жёлтый цвет, как жёлтый на палитре
            item = FilledRectItem(QRectF(scene_pos, scene_pos), QColor("#F9D556"))
        else:
            # Красный цвет (текущий цвет пера) для контура/квадрата
            pen = QPen(self.view.current_pen_color, self.view.pen_width)
            item = RectangleItem(QRectF(scene_pos, scene_pos), pen)
        return item

    def update_draw(self, temp_item, scene_pos: QPointF, modifiers):
        """Обновляет геометрию с учётом режима квадрата или зажатого Shift."""
        if not self.start_point:
            return
        if (modifiers & Qt.ShiftModifier) or (self.view.shape_mode == 'square'):
            dx = scene_pos.x() - self.start_point.x()
            dy = scene_pos.y() - self.start_point.y()
            side = max(abs(dx), abs(dy))
            x = self.start_point.x() if dx >= 0 else self.start_point.x() - side
            y = self.start_point.y() if dy >= 0 else self.start_point.y() - side
            rect = QRectF(x, y, side, side)
        else:
            rect = QRectF(self.start_point, scene_pos).normalized()
        temp_item.setRect(rect)

    def finish_draw(self, temp_item) -> bool:
        """Проверяет, достаточно ли велик элемент."""
        rect = temp_item.rect()
        if rect.width() < 5 or rect.height() < 5:
            return False
        return True