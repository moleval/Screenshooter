"""
Модуль: crop_handles.py
Описание: Универсальный класс маркеров изменения размера.
          Поддерживает произвольные точки и совместимый API для QRectF.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPen
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsItem

from ..theme import theme_manager


class CropHandles:
    HANDLE_RADIUS = 5
    HIT_RADIUS = 7

    def __init__(self, view, fill_color=None, show_midpoints=True):
        self.view = view
        self.fill_color = fill_color or theme_manager.get_color('crop_rect')
        self.show_midpoints = show_midpoints
        self.handle_items = {}
        self.positions = {}

    def create_handles(self, points):
        """Создаёт маркеры по словарю {handle_id: QPointF}.

        Для обратной совместимости старый вызов create_handles(QRectF)
        по-прежнему создаёт стандартные 4/8 прямоугольных маркеров.
        """
        if isinstance(points, QRectF):
            points = self._ids_positions(points)
        else:
            points = self._normalize_points(points)

        self.remove_handles()
        for handle_id, pos in points.items():
            handle = QGraphicsEllipseItem(
                -self.HANDLE_RADIUS, -self.HANDLE_RADIUS,
                2 * self.HANDLE_RADIUS, 2 * self.HANDLE_RADIUS
            )
            pen = QPen(Qt.white, 2)
            pen.setCosmetic(True)
            handle.setPen(pen)
            handle.setBrush(self.fill_color)
            handle.setZValue(2000)
            handle.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            handle.setAcceptedMouseButtons(Qt.LeftButton)
            handle.setPos(pos)
            self.view.scene().addItem(handle)
            self.handle_items[handle_id] = handle
            self.positions[handle_id] = pos

    def create_rect_handles(self, rect: QRectF):
        """Явная обёртка для стандартных прямоугольных маркеров."""
        self.create_handles(rect)

    def update_handles(self, points):
        """Обновляет произвольный набор маркеров.

        Если передан QRectF, используется старый прямоугольный API.
        """
        if isinstance(points, QRectF):
            points = self._ids_positions(points)
        else:
            points = self._normalize_points(points)

        for handle_id, pos in points.items():
            if handle_id in self.handle_items:
                self.handle_items[handle_id].setPos(pos)
                self.positions[handle_id] = pos

    def update_rect_handles(self, rect: QRectF):
        """Явная обёртка для стандартных прямоугольных маркеров."""
        self.update_handles(rect)

    def remove_handles(self):
        for handle in self.handle_items.values():
            try:
                if sip.isdeleted(handle):
                    continue
                if handle.scene() is self.view.scene():
                    self.view.scene().removeItem(handle)
            except RuntimeError:
                continue
        self.handle_items.clear()
        self.positions.clear()

    def hit_test(self, device_pos: QPointF):
        device_pos = QPointF(device_pos)
        for handle_id, scene_pos in self.positions.items():
            handle_device_pos = QPointF(self.view.mapFromScene(scene_pos))
            diff = device_pos - handle_device_pos
            if (diff.x() ** 2 + diff.y() ** 2) <= self.HIT_RADIUS ** 2:
                return handle_id
        return None

    def get_cursor_for_handle(self, handle_id):
        if handle_id in ('tl', 'br'):
            return Qt.SizeFDiagCursor
        elif handle_id in ('tr', 'bl'):
            return Qt.SizeBDiagCursor
        elif handle_id in ('tm', 'bm'):
            return Qt.SizeVerCursor
        elif handle_id in ('lm', 'rm'):
            return Qt.SizeHorCursor
        return Qt.ArrowCursor

    def _normalize_points(self, points):
        if not hasattr(points, 'items'):
            raise TypeError("points must be a dict-like object of handle_id -> QPointF")

        normalized = {}
        for handle_id, pos in points.items():
            normalized[handle_id] = QPointF(pos)
        return normalized

    def _ids_positions(self, rect: QRectF):
        positions = {
            'tl': rect.topLeft(),
            'tr': rect.topRight(),
            'bl': rect.bottomLeft(),
            'br': rect.bottomRight(),
        }
        if self.show_midpoints:
            positions.update({
                'tm': QPointF(rect.center().x(), rect.top()),
                'bm': QPointF(rect.center().x(), rect.bottom()),
                'lm': QPointF(rect.left(), rect.center().y()),
                'rm': QPointF(rect.right(), rect.center().y()),
            })
        return positions
