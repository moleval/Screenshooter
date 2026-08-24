"""
Модуль: tools/line_tool.py
Описание: Инструмент рисования линий.
          Поддерживает режимы: прямая (straight), пунктирная (dashed), волнистая (wavy).
          При зажатом Shift ограничивает направление по горизонтали или вертикали.
"""

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen

from .base_tool import BaseTool
from ..items import LineItem, WavyLineItem


class LineTool(BaseTool):
    def __init__(self, view):
        super().__init__(view)
        self.start_point = None

    def start_draw(self, scene_pos: QPointF):
        self.start_point = scene_pos
        pen = QPen(self.view.current_pen_color, self.view.pen_width)
        mode = self.view.line_mode

        if mode == 'straight':
            return LineItem(scene_pos.x(), scene_pos.y(), scene_pos.x(), scene_pos.y(), pen)
        elif mode == 'dashed':
            dpen = QPen(pen)
            dpen.setStyle(Qt.DashLine)
            return LineItem(scene_pos.x(), scene_pos.y(), scene_pos.x(), scene_pos.y(), dpen)
        elif mode == 'wavy':
            return WavyLineItem(scene_pos.x(), scene_pos.y(), scene_pos.x(), scene_pos.y(), pen)
        return None

    def update_draw(self, temp_item, scene_pos: QPointF, modifiers):
        if not self.start_point:
            return
        start = self.start_point
        end = scene_pos

        # Ограничение по осям при зажатом Shift
        if modifiers & Qt.ShiftModifier:
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            if abs(dx) > abs(dy):
                end.setY(start.y())
            else:
                end.setX(start.x())

        if isinstance(temp_item, LineItem):
            temp_item.setLine(start.x(), start.y(), end.x(), end.y())
        elif isinstance(temp_item, WavyLineItem):
            temp_item.set_points(start.x(), start.y(), end.x(), end.y())

    def finish_draw(self, temp_item) -> bool:
        if not self.start_point:
            return False
        if isinstance(temp_item, LineItem):
            line = temp_item.line()
            length = (line.x2() - line.x1()) ** 2 + (line.y2() - line.y1()) ** 2
        else:  # WavyLineItem
            length = (temp_item._x2 - temp_item._x1) ** 2 + (temp_item._y2 - temp_item._y1) ** 2
        return length > 25  # минимальная длина (5 пикселей)