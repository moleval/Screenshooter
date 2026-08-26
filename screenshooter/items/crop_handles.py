"""
Модуль: crop_handles.py
Описание: Класс CropHandles для создания и управления 8 маркерами изменения размера
          (по углам и сторонам рамки). Маркеры не масштабируются вместе с видом.
          Используется в режимах обрезки, размытия и в будущем для обычных аннотаций.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPen, QColor, QBrush
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsItem


class CropHandles:
    """
    Управляющие точки на рамке: 8 круглых маркеров.
    Точки не масштабируются при изменении масштаба просмотра.
    """

    HANDLE_RADIUS = 5
    HIT_RADIUS = 7

    def __init__(self, view, fill_color=QColor(0, 120, 215), show_midpoints=True):
        self.view = view
        self.fill_color = fill_color
        self.show_midpoints = show_midpoints
        self.handle_items = {}
        self.positions = {}

    def create_handles(self, rect: QRectF):
        self.remove_handles()
        ids_positions = self._ids_positions(rect)
        for handle_id, pos in ids_positions.items():
            handle = QGraphicsEllipseItem(-self.HANDLE_RADIUS, -self.HANDLE_RADIUS,
                                          2 * self.HANDLE_RADIUS, 2 * self.HANDLE_RADIUS)
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

    def update_handles(self, rect: QRectF):
        ids_positions = self._ids_positions(rect)
        for handle_id, pos in ids_positions.items():
            if handle_id in self.handle_items:
                self.handle_items[handle_id].setPos(pos)
                self.positions[handle_id] = pos

    def remove_handles(self):
        # ЭТАП 1: защита от удалённых C++ объектов при закрытии
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
        """Возвращает id маркера или None, если мышь не над маркером.
        Используем mapFromScene, потому что он учитывает и трансформацию,
        и прокрутку вида. transform.map() учитывает только трансформацию."""
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