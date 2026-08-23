"""Линии: прямая, пунктирная, волнистая."""

import math
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPen, QPainterPath, QPainterPathStroker
from PyQt5.QtWidgets import QGraphicsLineItem, QGraphicsPathItem
from ..constants import HIT_AREA_PADDING


class LineItem(QGraphicsLineItem):
    def __init__(self, x1, y1, x2, y2, pen):
        super().__init__(x1, y1, x2, y2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)
        self.setFlags(QGraphicsLineItem.ItemIsMovable | QGraphicsLineItem.ItemIsSelectable)

    def shape(self):
        path = QPainterPath()
        path.moveTo(self.line().p1())
        path.lineTo(self.line().p2())
        stroker = QPainterPathStroker()
        stroker.setWidth(HIT_AREA_PADDING * 2)
        return stroker.createStroke(path)


class WavyLineItem(QGraphicsPathItem):
    def __init__(self, x1, y1, x2, y2, pen):
        super().__init__()
        self._x1, self._y1, self._x2, self._y2 = x1, y1, x2, y2
        self._pen = pen
        self.setPen(pen)
        self.setFlags(QGraphicsPathItem.ItemIsMovable | QGraphicsPathItem.ItemIsSelectable)
        self.set_points(x1, y1, x2, y2)

    def set_points(self, x1, y1, x2, y2):
        self._x1, self._y1, self._x2, self._y2 = x1, y1, x2, y2
        self.update_path()

    def update_path(self):
        x1, y1, x2, y2 = self._x1, self._y1, self._x2, self._y2
        path = QPainterPath()
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length < 1:
            path.moveTo(x1, y1)
            self.setPath(path)
            return
        steps = max(20, int(length / 2))
        path.moveTo(x1, y1)
        base_amp = 3 + self._pen.widthF() * 0.5
        amp = min(15, base_amp + length * 0.02)
        for i in range(1, steps + 1):
            t = i / steps
            x = x1 + dx * t
            y = y1 + dy * t
            norm_x = -dy / length
            norm_y = dx / length
            offset = amp * math.sin(t * 10 * math.pi)
            x += norm_x * offset
            y += norm_y * offset
            path.lineTo(x, y)
        self.setPath(path)

    def setPen(self, pen):
        self._pen = pen
        super().setPen(pen)
        self.update_path()

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(HIT_AREA_PADDING * 2)
        return stroker.createStroke(self.path())