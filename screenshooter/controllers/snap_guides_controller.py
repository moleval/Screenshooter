"""
Модуль: controllers/snap_guides_controller.py
Описание: мягкая привязка перемещаемых объектов к осям подложки
и других объектов с временными направляющими.
"""

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPen
from PyQt5.QtWidgets import QGraphicsLineItem


class SnapGuidesController:
    """Вычисляет snap-delta и управляет временными направляющими."""

    SNAP_DISTANCE_PX = 8.0
    GUIDE_Z_VALUE = 9998

    def __init__(self, view):
        self.view = view
        self._scene = view.scene()
        self._drag_rects = []
        self._candidate_x = []
        self._candidate_y = []
        self._guides = []

    def begin_drag(self, items, background_item):
        """Фиксирует исходную геометрию drag-группы и оси привязки."""
        self.clear_guides()
        selected = set(items)
        self._drag_rects = [
            item.sceneBoundingRect()
            for item in items
            if item is not None and item.scene() is self._scene
        ]

        self._candidate_x = []
        self._candidate_y = []

        if background_item is not None and background_item.scene() is self._scene:
            self._add_rect_candidates(background_item.sceneBoundingRect())

        for item in self._scene.items():
            if item in selected or item is background_item:
                continue
            if item.scene() is not self._scene:
                continue
            # Направляющие и служебные scene-items не являются целями.
            if item.zValue() >= 2000:
                continue
            self._add_rect_candidates(item.sceneBoundingRect())

    def _add_rect_candidates(self, rect):
        rect = QRectF(rect)
        if rect.isEmpty():
            return
        self._candidate_x.extend((rect.left(), rect.center().x(), rect.right()))
        self._candidate_y.extend((rect.top(), rect.center().y(), rect.bottom()))

    @staticmethod
    def _union_rects(rects):
        if not rects:
            return QRectF()
        result = QRectF(rects[0])
        for rect in rects[1:]:
            result = result.united(rect)
        return result

    def snap_delta(self, delta, snap_x=True, snap_y=True):
        """Возвращает скорректированный delta и показывает активные guides."""
        if not self._drag_rects:
            return QPointF(delta)

        zoom = abs(self.view.transform().m11())
        if zoom < 1e-6:
            zoom = 1.0
        threshold = self.SNAP_DISTANCE_PX / zoom

        group_rect = self._union_rects(
            [QRectF(rect).translated(delta.x(), delta.y()) for rect in self._drag_rects]
        )

        dx = 0.0
        dy = 0.0
        x_guide = None
        y_guide = None

        if snap_x:
            x_guide = self._find_best(
                (group_rect.left(), group_rect.center().x(), group_rect.right()),
                self._candidate_x,
                threshold,
            )
            if x_guide is not None:
                dx = x_guide[0] - x_guide[1]

        if snap_y:
            y_guide = self._find_best(
                (group_rect.top(), group_rect.center().y(), group_rect.bottom()),
                self._candidate_y,
                threshold,
            )
            if y_guide is not None:
                dy = y_guide[0] - y_guide[1]

        result = QPointF(delta.x() + dx, delta.y() + dy)
        self._show_guides(x_guide[0] if x_guide else None,
                          y_guide[0] if y_guide else None)
        return result

    @staticmethod
    def _find_best(values, candidates, threshold):
        best = None
        for value in values:
            for candidate in candidates:
                distance = abs(candidate - value)
                if distance <= threshold and (best is None or distance < best[2]):
                    best = (candidate, value, distance)
        return best

    def _show_guides(self, x=None, y=None):
        self.clear_guides()
        bg = getattr(self.view.image_editor, "background_item", None)
        if bg is not None and bg.scene() is self._scene:
            rect = bg.sceneBoundingRect()
        else:
            rect = self._union_rects(self._drag_rects)

        if rect.isEmpty():
            return

        pen = QPen(QColor(0, 120, 215, 150), 1, Qt.DashLine)
        pen.setCosmetic(True)

        if x is not None:
            line = QGraphicsLineItem(x, rect.top(), x, rect.bottom())
            line.setPen(pen)
            line.setZValue(self.GUIDE_Z_VALUE)
            line.setFlag(QGraphicsLineItem.ItemIsSelectable, False)
            self._scene.addItem(line)
            self._guides.append(line)

        if y is not None:
            line = QGraphicsLineItem(rect.left(), y, rect.right(), y)
            line.setPen(pen)
            line.setZValue(self.GUIDE_Z_VALUE)
            line.setFlag(QGraphicsLineItem.ItemIsSelectable, False)
            self._scene.addItem(line)
            self._guides.append(line)

    def clear_guides(self):
        for guide in self._guides:
            if guide.scene() is self._scene:
                self._scene.removeItem(guide)
        self._guides.clear()

    @property
    def guides(self):
        return tuple(self._guides)
