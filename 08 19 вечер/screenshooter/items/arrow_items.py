"""Стрелки: прямая, изогнутая, размерная линия."""

import math
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF
from PyQt5.QtGui import QPen, QColor, QPolygonF, QPainterPath, QPainterPathStroker, QFont
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsItemGroup, QGraphicsLineItem, QGraphicsTextItem, QStyle
from ..constants import HIT_AREA_PADDING


class ArrowItem(QGraphicsItem):
    """Прямая стрелка с наконечником."""

    def __init__(self, start, end, pen):
        super().__init__()
        self._start = start
        self._end = end
        self._line_end = start
        self._p1 = end
        self._p2 = end
        self._p3 = end
        self._pen = QPen(pen)
        self._pen.setCapStyle(Qt.FlatCap)
        self._pen.setJoinStyle(Qt.MiterJoin)
        self._brush = QColor(pen.color())
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        self.set_line(start, end)

    def set_line(self, start, end):
        self.prepareGeometryChange()
        self._start = start
        self._end = end
        self._update_geometry()
        self.update()

    def setPen(self, pen):
        self.prepareGeometryChange()
        self._pen = QPen(pen)
        self._pen.setCapStyle(Qt.FlatCap)
        self._pen.setJoinStyle(Qt.MiterJoin)
        self._brush = QColor(pen.color())
        self._update_geometry()
        self.update()

    def _update_geometry(self):
        start, end = self._start, self._end
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.hypot(dx, dy)
        if length == 0:
            self._line_end = start
            self._p1 = end
            self._p2 = end
            self._p3 = end
            self._shape_path = QPainterPath()
            return
        pw = self._pen.widthF()
        arrow_size = max(8, 8 + pw * 3)
        angle = math.atan2(dy, dx)
        ar = math.radians(20)
        self._p1 = end
        self._p2 = end - QPointF(arrow_size * math.cos(angle - ar), arrow_size * math.sin(angle - ar))
        self._p3 = end - QPointF(arrow_size * math.cos(angle + ar), arrow_size * math.sin(angle + ar))
        t = (length - arrow_size * math.cos(ar)) / length
        self._line_end = QPointF(start.x() + dx * t, start.y() + dy * t)
        shape = QPainterPath()
        line_path = QPainterPath(start)
        line_path.lineTo(self._line_end)
        stroker = QPainterPathStroker()
        stroker.setWidth(pw)
        shape.addPath(stroker.createStroke(line_path))
        head_path = QPainterPath()
        head_path.moveTo(self._p2)
        head_path.lineTo(self._p1)
        head_path.lineTo(self._p3)
        head_path.closeSubpath()
        shape.addPath(head_path)
        self._shape_path = shape

    def boundingRect(self):
        return self._shape_path.boundingRect() if hasattr(self, '_shape_path') else QRectF()

    def shape(self):
        if not hasattr(self, '_shape_path'):
            return QPainterPath()
        stroker = QPainterPathStroker()
        stroker.setWidth(HIT_AREA_PADDING * 2)
        ep = stroker.createStroke(self._shape_path)
        ep.addPath(self._shape_path)
        return ep

    def paint(self, painter, option, widget):
        if not hasattr(self, '_line_end'):
            return
        lp = QPen(self._pen)
        lp.setCapStyle(Qt.RoundCap)
        lp.setJoinStyle(Qt.RoundJoin)
        painter.setPen(lp)
        painter.drawLine(self._start, self._line_end)
        hp = QPen(self._pen)
        hp.setCapStyle(Qt.FlatCap)
        hp.setJoinStyle(Qt.MiterJoin)
        painter.setPen(hp)
        painter.setBrush(self._brush)
        painter.drawPolygon(QPolygonF([self._p2, self._p1, self._p3]))
        if option.state & QStyle.State_Selected:
            pen = QPen(QColor(0, 120, 215), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect().adjusted(2, 2, -2, -2))


class CurvedArrowItem(QGraphicsPathItem):
    """Изогнутая стрелка (квадратичная кривая Безье)."""

    def __init__(self, start, end, ctrl, pen):
        super().__init__()
        self._start = start
        self._end = end
        self._ctrl = ctrl
        self._pen = QPen(pen)
        self.setFlags(QGraphicsPathItem.ItemIsMovable | QGraphicsPathItem.ItemIsSelectable)
        self.setPen(pen)
        self.build_path(start, end, ctrl)

    def set_curve(self, start, end, ctrl):
        self._start = start
        self._end = end
        self._ctrl = ctrl
        self.build_path(start, end, ctrl)

    def build_path(self, start, end, ctrl):
        path = QPainterPath()
        path.moveTo(start)
        path.quadTo(ctrl, end)
        self.setPath(path)

    def setPen(self, pen):
        self._pen = QPen(pen)
        super().setPen(pen)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        end_point = self._end
        dx = end_point.x() - self._ctrl.x()
        dy = end_point.y() - self._ctrl.y()
        length = math.hypot(dx, dy)
        if length == 0:
            return
        angle = math.atan2(dy, dx)
        pw = self._pen.widthF()
        asz = max(8, 8 + pw * 3)
        ar = math.radians(20)
        p1 = end_point
        p2 = end_point - QPointF(asz * math.cos(angle - ar), asz * math.sin(angle - ar))
        p3 = end_point - QPointF(asz * math.cos(angle + ar), asz * math.sin(angle + ar))
        hp = QPen(self._pen)
        hp.setCapStyle(Qt.FlatCap)
        hp.setJoinStyle(Qt.MiterJoin)
        painter.setPen(hp)
        painter.setBrush(QColor(self._pen.color()))
        painter.drawPolygon(QPolygonF([p2, p1, p3]))
        if option.state & QStyle.State_Selected:
            pen = QPen(QColor(0, 120, 215), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect().adjusted(2, 2, -2, -2))

    def boundingRect(self):
        return self.path().boundingRect().adjusted(-20, -20, 20, 20)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(HIT_AREA_PADDING * 2)
        return stroker.createStroke(self.path())

    def isEmpty(self):
        return math.hypot(self._end.x() - self._start.x(), self._end.y() - self._start.y()) < 1


class DimensionItem(QGraphicsItemGroup):
    """Размерная линия с текстом и засечками."""

    def __init__(self, start, end, pen, text_color):
        super().__init__()
        self._start = start
        self._end = end
        self._pen = QPen(pen)
        self._text_color = text_color
        self._text_item = None
        self._rotation = 0
        self._text_font_size = 12
        self._text_scale_ratio = self._text_font_size / max(1, self._pen.widthF())
        self.build_items(start, end)

    def build_items(self, start, end):
        self.prepareGeometryChange()
        if self._text_item:
            self._text_font_size = max(1, self._text_item.font().pointSize())
        for child in self.childItems():
            self.removeFromGroup(child)
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.hypot(dx, dy)
        if length == 0:
            return
        angle = math.atan2(dy, dx)
        self._rotation = math.degrees(angle)

        pen = QPen(QColor(160, 0, 0), self._pen.widthF())
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)

        line = QGraphicsLineItem(start.x(), start.y(), end.x(), end.y())
        line.setPen(pen)
        self.addToGroup(line)
        line.setFlag(QGraphicsItem.ItemIsMovable, False)
        line.setFlag(QGraphicsItem.ItemIsSelectable, False)

        asz = max(8, 8 + self._pen.widthF() * 3)
        ar = math.radians(20)

        p1 = end
        p2 = end - QPointF(asz * math.cos(angle - ar), asz * math.sin(angle - ar))
        p3 = end - QPointF(asz * math.cos(angle + ar), asz * math.sin(angle + ar))
        hp = QPainterPath()
        hp.moveTo(p2)
        hp.lineTo(p1)
        hp.lineTo(p3)
        hp.closeSubpath()
        h1 = QGraphicsPathItem(hp)
        h1.setPen(QPen(QColor(160, 0, 0), 1))
        h1.setBrush(QColor(160, 0, 0))
        self.addToGroup(h1)
        h1.setFlag(QGraphicsItem.ItemIsMovable, False)
        h1.setFlag(QGraphicsItem.ItemIsSelectable, False)

        p1 = start
        p2 = start + QPointF(asz * math.cos(angle - ar), asz * math.sin(angle - ar))
        p3 = start + QPointF(asz * math.cos(angle + ar), asz * math.sin(angle + ar))
        hp2 = QPainterPath()
        hp2.moveTo(p2)
        hp2.lineTo(p1)
        hp2.lineTo(p3)
        hp2.closeSubpath()
        h2 = QGraphicsPathItem(hp2)
        h2.setPen(QPen(QColor(160, 0, 0), 1))
        h2.setBrush(QColor(160, 0, 0))
        self.addToGroup(h2)
        h2.setFlag(QGraphicsItem.ItemIsMovable, False)
        h2.setFlag(QGraphicsItem.ItemIsSelectable, False)

        perp = angle + math.pi / 2
        plen = asz * 0.9
        su = start + QPointF(plen * 0.3 * math.cos(perp), plen * 0.3 * math.sin(perp))
        sd = start - QPointF(plen * 0.5 * math.cos(perp), plen * 0.5 * math.sin(perp))
        t1 = QGraphicsLineItem(su.x(), su.y(), sd.x(), sd.y())
        t1.setPen(pen)
        self.addToGroup(t1)
        t1.setFlag(QGraphicsItem.ItemIsMovable, False)
        t1.setFlag(QGraphicsItem.ItemIsSelectable, False)

        eu = end + QPointF(plen * 0.3 * math.cos(perp), plen * 0.3 * math.sin(perp))
        ed = end - QPointF(plen * 0.5 * math.cos(perp), plen * 0.5 * math.sin(perp))
        t2 = QGraphicsLineItem(eu.x(), eu.y(), ed.x(), ed.y())
        t2.setPen(pen)
        self.addToGroup(t2)
        t2.setFlag(QGraphicsItem.ItemIsMovable, False)
        t2.setFlag(QGraphicsItem.ItemIsSelectable, False)

        dist = int(length)
        self._text_item = DimensionTextItem(self, str(dist))
        self._text_item.setDefaultTextColor(self._text_color)
        font = QFont("Arial", self._text_font_size)
        self._text_item.setFont(font)
        self.addToGroup(self._text_item)
        self._text_item.setFlag(QGraphicsItem.ItemIsMovable, False)
        self._text_item.setFlag(QGraphicsItem.ItemIsSelectable, False)

        self._calculate_text_geometry()
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)

    def _calculate_text_geometry(self):
        if not self._text_item:
            return
        start, end = self._start, self._end
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.hypot(dx, dy)
        if length <= 0:
            return
        mid = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
        ang = math.degrees(math.atan2(dy, dx))
        if ang > 90 or ang < -90:
            ang += 180
        ang = (ang + 180) % 360 - 180
        rad = math.radians(ang)
        normal = QPointF(math.sin(rad), -math.cos(rad))
        rect = self._text_item.boundingRect()
        gap = 8
        center = mid + normal * (gap + rect.height() / 2)
        c = rect.center()
        self._text_item.setTransformOriginPoint(c)
        self._text_item.setRotation(ang)
        self._text_item.setPos(center - c)

    def update_text_position(self):
        if not self._text_item:
            return
        t = self._text_item.toPlainText()
        if not t.strip():
            t = "0"
        if self._text_item.toPlainText() != t:
            self._text_item.setPlainText(t)
        self._calculate_text_geometry()
        self._text_item.update()

    def setTextColor(self, color):
        self._text_color = color
        if self._text_item:
            self._text_item.setDefaultTextColor(color)

    def setDimensionWidth(self, width):
        width = max(1, min(100, int(width)))
        old = max(0.1, self._pen.widthF())
        cf = self._text_item.font().pointSize() if self._text_item else self._text_font_size
        self._text_scale_ratio = cf / old
        pen = QPen(self._pen)
        pen.setWidthF(float(width))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self._pen = pen
        nf = max(1, int(round(self._text_scale_ratio * width)))
        self._text_font_size = nf
        self.build_items(self._start, self._end)
        if self._text_item:
            font = self._text_item.font()
            font.setPointSize(nf)
            self._text_item.setFont(font)
            self._calculate_text_geometry()
            self._text_item.update()

    def setTextFontSize(self, size):
        self._text_font_size = max(1, int(size))
        if self._text_item:
            font = self._text_item.font()
            font.setPointSize(self._text_font_size)
            self._text_item.setFont(font)
            self._text_scale_ratio = self._text_font_size / max(0.1, self._pen.widthF())
            self._calculate_text_geometry()
            self._text_item.update()

    def setPen(self, pen):
        self._pen = pen
        self.build_items(self._start, self._end)

    def setRect(self, start, end):
        self._start = start
        self._end = end
        self.build_items(start, end)

    def boundingRect(self):
        return self.childrenBoundingRect()

    def shape(self):
        path = QPainterPath()
        for child in self.childItems():
            path.addPath(child.shape())
        return path