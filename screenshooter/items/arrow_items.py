"""
Модуль: items/arrow_items.py
Описание: Элементы стрелок.
          ArrowItem — прямая стрелка с наконечником.
          CurvedArrowItem — изогнутая стрелка (квадратичная кривая Безье).
          DimensionItem — размерная линия с засечками и стрелками (без текста).
"""

import math
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPen, QColor, QPolygonF, QPainterPath, QPainterPathStroker
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPathItem, QStyle
from ..constants import HIT_AREA_PADDING


# ==================== ArrowItem ====================
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

    def pen(self):
        """Возвращает текущее перо."""
        return self._pen

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


# ==================== CurvedArrowItem ====================
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

    def pen(self):
        """Возвращает текущее перо."""
        return self._pen

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


# ==================== DimensionItem ====================
class DimensionItem(QGraphicsItem):
    """
    Размерная линия с засечками и стрелками.
    Текст создаётся отдельно и не входит в состав.
    """

    # ------ НАСТРАИВАЕМЫЕ ПАРАМЕТРЫ ЗАСЕЧЕК ------
    TICK_LENGTH_FACTOR = 1.2
    TICK_GAP_FACTOR = -0.5
    # ----------------------------------------------

    def __init__(self, start, end, pen, text_color=None):
        super().__init__()
        self._start = start
        self._end = end
        self._pen = QPen(pen)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        self.setZValue(10)

    def setRect(self, start, end):
        self.prepareGeometryChange()
        self._start = start
        self._end = end
        self.update()

    def setPen(self, pen):
        self._pen = QPen(pen)
        self.update()

    def pen(self):
        """Возвращает текущее перо."""
        return self._pen

    def boundingRect(self):
        start = self._start
        end = self._end
        if start == end:
            return QRectF(start, QPointF(1, 1))
        margin = max(30, self._pen.widthF() * 5 + 20)
        return QRectF(start, end).normalized().adjusted(-margin, -margin, margin, margin)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.boundingRect().adjusted(-HIT_AREA_PADDING, -HIT_AREA_PADDING,
                                                  HIT_AREA_PADDING, HIT_AREA_PADDING))
        return path

    def paint(self, painter, option, widget):
        start = self._start
        end = self._end
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.hypot(dx, dy)
        if length == 0:
            return
        angle = math.atan2(dy, dx)

        pen_color = self._pen.color()
        pen_width = self._pen.widthF()
        arrow_size = max(8, 8 + pen_width * 3)
        ar = math.radians(20)

        # Единичные векторы
        e = QPointF(math.cos(angle), math.sin(angle))
        perp = QPointF(-math.sin(angle), math.cos(angle))

        # Точки стрелок
        back_offset = arrow_size * math.cos(ar)
        base_end = end - e * back_offset
        p2_end = end - QPointF(arrow_size * math.cos(angle - ar), arrow_size * math.sin(angle - ar))
        p3_end = end - QPointF(arrow_size * math.cos(angle + ar), arrow_size * math.sin(angle + ar))

        base_start = start + e * back_offset
        p2_start = start + QPointF(arrow_size * math.cos(angle - ar), arrow_size * math.sin(angle - ar))
        p3_start = start + QPointF(arrow_size * math.cos(angle + ar), arrow_size * math.sin(angle + ar))

        # Основная линия
        pen = QPen(pen_color, pen_width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(base_start, base_end)

        # Засечки
        tick_length = arrow_size * self.TICK_LENGTH_FACTOR
        half_tick = tick_length / 2.0
        tick_gap = pen_width * self.TICK_GAP_FACTOR

        tick_center_start = start + e * tick_gap
        tick_start1 = tick_center_start - perp * half_tick
        tick_end1 = tick_center_start + perp * half_tick
        painter.setPen(QPen(pen_color, pen_width))
        painter.drawLine(tick_start1, tick_end1)

        tick_center_end = end - e * tick_gap
        tick_start2 = tick_center_end - perp * half_tick
        tick_end2 = tick_center_end + perp * half_tick
        painter.drawLine(tick_start2, tick_end2)

        # Стрелки
        painter.setBrush(pen_color)
        painter.setPen(QPen(pen_color, 1))
        painter.drawPolygon(QPolygonF([p2_end, end, p3_end]))
        painter.drawPolygon(QPolygonF([p2_start, start, p3_start]))

        # Рамка выделения
        if option.state & QStyle.State_Selected:
            pen = QPen(QColor(0, 120, 215), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect().adjusted(2, 2, -2, -2))