"""
Модуль: tools/ellipse_tool.py
Описание: Инструмент рисования эллипса.
          Поддерживает режимы: эллипс (ellipse), круг (circle), облако (cloud).
"""

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPen

from .base_tool import BaseTool
from ..items import EllipseItem, CloudItem


class EllipseTool(BaseTool):
    def __init__(self, view):
        super().__init__(view)
        self.start_point = None

    def start_draw(self, scene_pos: QPointF):
        """Создаёт временный элемент в зависимости от режима ellipse_mode."""
        self.start_point = scene_pos
        pen = QPen(self.view.current_pen_color, self.view.pen_width)
        if self.view.ellipse_mode == 'cloud':
            item = CloudItem(QRectF(scene_pos, scene_pos), pen)
        else:
            item = EllipseItem(QRectF(scene_pos, scene_pos), pen)
        return item

    def update_draw(self, temp_item, scene_pos: QPointF, modifiers):
        """Обновляет геометрию с учётом режима круга или зажатого Shift."""
        if not self.start_point:
            return
        # Если зажат Shift или включён режим 'circle' – рисуем круг
        if (modifiers & Qt.ShiftModifier) or (self.view.ellipse_mode == 'circle'):
            dx = scene_pos.x() - self.start_point.x()
            dy = scene_pos.y() - self.start_point.y()
            radius = max(abs(dx), abs(dy))
            x = self.start_point.x() if dx >= 0 else self.start_point.x() - radius
            y = self.start_point.y() if dy >= 0 else self.start_point.y() - radius
            rect = QRectF(x, y, radius, radius)
        else:
            rect = QRectF(self.start_point, scene_pos).normalized()
        temp_item.setRect(rect)

    def finish_draw(self, temp_item) -> bool:
        """Проверяет, достаточно ли велик элемент."""
        rect = temp_item.rect()
        if rect.width() < 5 or rect.height() < 5:
            return False
        return True