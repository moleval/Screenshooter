"""
Модуль: tools/arrow_tool.py
Описание: Инструмент рисования стрелок.
          Поддерживает режимы: прямая (straight), изогнутая (curved), размерная линия (dimension).
          При зажатом Shift ограничивает направление по горизонтали или вертикали для всех режимов.
"""

import math
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QFont

from .base_tool import BaseTool
from ..items import ArrowItem, CurvedArrowItem, DimensionItem, TextItem
from ..constants import MIN_ARROW_LENGTH


class ArrowTool(BaseTool):
    def __init__(self, view):
        super().__init__(view)
        self.start_point = None

    def start_draw(self, scene_pos: QPointF):
        self.start_point = scene_pos
        pen = QPen(self.view.current_pen_color, self.view.pen_width)
        mode = self.view.arrow_mode

        if mode == 'straight':
            return ArrowItem(scene_pos, scene_pos, pen)
        elif mode == 'curved':
            return CurvedArrowItem(scene_pos, scene_pos, (scene_pos + scene_pos) / 2, pen)
        elif mode == 'dimension':
            return DimensionItem(scene_pos, scene_pos, pen)
        return None

    def update_draw(self, temp_item, scene_pos: QPointF, modifiers):
        if not self.start_point:
            return
        start = self.start_point
        end = scene_pos
        mode = self.view.arrow_mode

        # Ограничение по осям при зажатом Shift для всех режимов
        if modifiers & Qt.ShiftModifier:
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            if abs(dx) > abs(dy):
                end.setY(start.y())
            else:
                end.setX(start.x())

        if mode == 'straight':
            temp_item.set_line(start, end)
        elif mode == 'curved':
            mid = (start + end) / 2
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            length = math.hypot(dx, dy)
            if length > 0:
                perp_x = -dy / length
                perp_y = dx / length
                bend = 0.3
                ctrl = mid + QPointF(perp_x * length * bend, perp_y * length * bend)
                cross = dx * (end.y() - start.y()) - dy * (end.x() - start.x())
                if cross < 0:
                    ctrl = mid - QPointF(perp_x * length * bend, perp_y * length * bend)
                temp_item.set_curve(start, end, ctrl)
        elif mode == 'dimension':
            temp_item.setRect(start, end)

    def finish_draw(self, temp_item) -> bool:
        if not self.start_point:
            return False
        start = self.start_point
        end = temp_item._end if hasattr(temp_item, '_end') else None
        if end is None:
            return False
        length = math.hypot(end.x() - start.x(), end.y() - start.y())
        if length < MIN_ARROW_LENGTH:
            return False

        if self.view.arrow_mode == 'dimension':
            self._create_dimension_text(start, end)

        return True

    def _create_dimension_text(self, start, end):
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.hypot(dx, dy)
        if length == 0:
            return

        mid = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
        angle_deg = math.degrees(math.atan2(dy, dx))
        if angle_deg > 90 or angle_deg < -90:
            angle_deg += 180
        angle_deg = (angle_deg + 180) % 360 - 180
        rad = math.radians(angle_deg)
        normal = QPointF(math.sin(rad), -math.cos(rad))

        ti = TextItem(self.view, bg_color=self.view.current_text_bg)
        ti.setDefaultTextColor(self.view.current_pen_color)
        font = QFont()
        font.setPointSize(self.view.text_size * 4)
        ti.setFont(font)
        ti.setPlainText("")

        rect = ti.boundingRect()
        gap = 8
        center = mid + normal * (gap + rect.height() / 2)
        ti.setPos(center - rect.center())
        ti.setTransformOriginPoint(rect.center())
        ti.setRotation(angle_deg)

        ti.setZValue(20)
        self.view.scene().addItem(ti)
        ti.setSelected(True)
        ti.setEditable(True)
        self.view.active_text_item = ti
        self.view._update_floating_widgets_visibility()