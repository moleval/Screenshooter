"""Прямоугольник, эллипс, заливка, облако."""

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPen, QColor, QPainterPath, QPainterPathStroker
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPathItem
from ..constants import HIT_AREA_PADDING


class RectangleItem(QGraphicsRectItem):
    def __init__(self, rect, pen):
        super().__init__(rect)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)
        self.setFlags(QGraphicsRectItem.ItemIsMovable | QGraphicsRectItem.ItemIsSelectable)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.rect().adjusted(-HIT_AREA_PADDING, -HIT_AREA_PADDING,
                                         HIT_AREA_PADDING, HIT_AREA_PADDING))
        return path


class EllipseItem(QGraphicsEllipseItem):
    def __init__(self, rect, pen):
        super().__init__(rect)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)
        self.setFlags(QGraphicsEllipseItem.ItemIsMovable | QGraphicsEllipseItem.ItemIsSelectable)

    def shape(self):
        path = QPainterPath()
        path.addEllipse(self.rect().adjusted(-HIT_AREA_PADDING, -HIT_AREA_PADDING,
                                             HIT_AREA_PADDING, HIT_AREA_PADDING))
        return path


class FilledRectItem(QGraphicsRectItem):
    def __init__(self, rect, color):
        super().__init__(rect)
        self.setPen(QPen(Qt.NoPen))
        self.setBrush(QColor(color.red(), color.green(), color.blue(), 80))
        self.setFlags(QGraphicsRectItem.ItemIsMovable | QGraphicsRectItem.ItemIsSelectable)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.rect().adjusted(-HIT_AREA_PADDING, -HIT_AREA_PADDING,
                                         HIT_AREA_PADDING, HIT_AREA_PADDING))
        return path


class CloudItem(QGraphicsPathItem):
    def __init__(self, rect, pen):
        super().__init__()
        self._rect = rect
        self._pen = pen
        self.setPen(pen)
        self.setFlags(QGraphicsPathItem.ItemIsMovable | QGraphicsPathItem.ItemIsSelectable)
        self.build_path(rect, pen)

    def build_path(self, rect, pen):
        path = QPainterPath()
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        if w <= 0 or h <= 0:
            self.setPath(path)
            return
        pw = pen.widthF()
        corner_radius = max(5, pw * 1.5 + 5)
        corner_radius = min(corner_radius, min(w, h) * 0.3)
        margin = corner_radius
        top_len = w - 2 * margin
        right_len = h - 2 * margin
        bottom_len = top_len
        left_len = right_len
        step = 15 + pw * 1.5
        top_steps = max(2, int(top_len / step))
        right_steps = max(2, int(right_len / step))
        bottom_steps = max(2, int(bottom_len / step))
        left_steps = max(2, int(left_len / step))
        amp_base = min(pw * 2 + 8, 30)
        amp_top = min(top_len * 0.4, amp_base)
        amp_bottom = amp_top
        amp_left = min(left_len * 0.4, amp_base)
        amp_right = amp_left

        path.moveTo(x + margin, y)
        for i in range(top_steps):
            seg_start = x + margin + i * top_len / top_steps
            seg_end = x + margin + (i + 1) * top_len / top_steps
            mid = (seg_start + seg_end) / 2
            path.quadTo(mid, y - amp_top, seg_end, y)

        path.arcTo(QRectF(x + w - 2 * corner_radius, y, 2 * corner_radius, 2 * corner_radius), 90, -90)

        for i in range(right_steps):
            seg_start = y + margin + i * right_len / right_steps
            seg_end = y + margin + (i + 1) * right_len / right_steps
            mid = (seg_start + seg_end) / 2
            path.quadTo(x + w + amp_right, mid, x + w, seg_end)

        path.arcTo(QRectF(x + w - 2 * corner_radius, y + h - 2 * corner_radius,
                          2 * corner_radius, 2 * corner_radius), 0, -90)

        for i in range(bottom_steps):
            seg_start = x + w - margin - i * bottom_len / bottom_steps
            seg_end = x + w - margin - (i + 1) * bottom_len / bottom_steps
            mid = (seg_start + seg_end) / 2
            path.quadTo(mid, y + h + amp_bottom, seg_end, y + h)

        path.arcTo(QRectF(x, y + h - 2 * corner_radius, 2 * corner_radius, 2 * corner_radius), 270, -90)

        for i in range(left_steps):
            seg_start = y + h - margin - i * left_len / left_steps
            seg_end = y + h - margin - (i + 1) * left_len / left_steps
            mid = (seg_start + seg_end) / 2
            path.quadTo(x - amp_left, mid, x, seg_end)

        path.arcTo(QRectF(x, y, 2 * corner_radius, 2 * corner_radius), 180, -90)
        path.closeSubpath()
        self.setPath(path)

    def setRect(self, rect):
        self._rect = rect
        self.build_path(rect, self._pen)

    def setPen(self, pen):
        self._pen = pen
        super().setPen(pen)
        self.build_path(self._rect, pen)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(HIT_AREA_PADDING * 2)
        return stroker.createStroke(self.path())