"""
Модуль: crop_handles.py
Описание: Универсальный класс маркеров изменения размера.
          Поддерживает произвольные точки и совместимый API для QRectF.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPen, QColor
from ..widgets.icon_manager import IconManager
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsPixmapItem, QGraphicsItem

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
        self.rotate_color = QColor("#FFFFFF")

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
            if handle_id == 'rotate':
                handle = QGraphicsPixmapItem(
                    IconManager.icon("rotate-handle", size=20, color=self.rotate_color).pixmap(20, 20)
                )
                handle.setOffset(-10, -10)
            else:
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

    def set_rotate_color(self, color):
        color = QColor(color)
        if color == self.rotate_color:
            return
        self.rotate_color = color
        handle = self.handle_items.get("rotate")
        if handle is not None:
            handle.setPixmap(
                IconManager.icon(
                    "rotate-handle", size=20, color=self.rotate_color
                ).pixmap(20, 20)
            )
            handle.setOffset(-10, -10)
            handle.update()
            self.view.scene().update()

    def update_handles(self, points):
        """Обновляет произвольный набор маркеров.

        Если передан QRectF, используется старый прямоугольный API.
        """
        if isinstance(points, QRectF):
            points = self._ids_positions(points)
        else:
            points = self._normalize_points(points)

        # Набор ручек может меняться при переключении типа аннотации
        # (например, появление/исчезновение rotate). В таком случае старые
        # служебные маркеры нельзя оставлять в positions/scene.
        if set(self.handle_items) != set(points):
            self.create_handles(points)
            return

        for handle_id, pos in points.items():
            handle = self.handle_items[handle_id]
            if handle.pos() != pos:
                handle.setPos(pos)
            self.positions[handle_id] = pos
            handle.update()

        # setPos() сам планирует перерисовку изменённого QGraphicsItem.
        # Принудительная перерисовка всей сцены на каждом движении мыши
        # заметно снижает плавность обрезки, поэтому здесь она не нужна.

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
        had_handles = bool(self.handle_items)
        self.handle_items.clear()
        self.positions.clear()
        if had_handles:
            self.view.scene().update()

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
        elif handle_id in ('tm', 'bm', 'top'):
            return Qt.SizeVerCursor
        elif handle_id in ('lm', 'rm', 'right'):
            return Qt.SizeHorCursor
        elif handle_id == 'rotate':
            return Qt.OpenHandCursor
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
