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
        self.setCacheMode(QGraphicsItem.NoCache)
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
        self._p2 = end - QPointF(arrow_size * math.cos(angle - ar),
                                 arrow_size * math.sin(angle - ar))
        self._p3 = end - QPointF(arrow_size * math.cos(angle + ar),
                                 arrow_size * math.sin(angle + ar))
        t = (length - arrow_size * math.cos(ar)) / length
        self._line_end = QPointF(start.x() + dx * t, start.y() + dy * t)

        shape = QPainterPath()

        # Обводка линии с теми же Cap/Join, что в paint()
        line_path = QPainterPath(start)
        line_path.lineTo(self._line_end)
        line_stroker = QPainterPathStroker()
        line_stroker.setWidth(pw)
        line_stroker.setCapStyle(Qt.RoundCap)
        line_stroker.setJoinStyle(Qt.RoundJoin)
        shape.addPath(line_stroker.createStroke(line_path))

        # Обводка наконечника (как в paint: FlatCap/MiterJoin)
        head_path = QPainterPath()
        head_path.moveTo(self._p2)
        head_path.lineTo(self._p1)
        head_path.lineTo(self._p3)
        head_path.closeSubpath()
        head_stroker = QPainterPathStroker()
        head_stroker.setWidth(pw)
        head_stroker.setCapStyle(Qt.FlatCap)
        head_stroker.setJoinStyle(Qt.MiterJoin)
        shape.addPath(head_stroker.createStroke(head_path))
        shape.addPath(head_path)

        self._shape_path = shape

    def boundingRect(self):
        if not hasattr(self, '_shape_path'):
            return QRectF()
        margin = self._pen.widthF() / 2 + 1
        return self._shape_path.boundingRect().adjusted(
            -margin, -margin, margin, margin)

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

        # Линия
        lp = QPen(self._pen)
        lp.setCapStyle(Qt.RoundCap)
        lp.setJoinStyle(Qt.RoundJoin)
        painter.setPen(lp)
        painter.drawLine(self._start, self._line_end)

        # Наконечник
        hp = QPen(self._pen)
        hp.setCapStyle(Qt.FlatCap)
        hp.setJoinStyle(Qt.MiterJoin)
        painter.setPen(hp)
        painter.setBrush(self._brush)
        painter.drawPolygon(QPolygonF([self._p2, self._p1, self._p3]))

        # Рамка выделения
        if option.state & QStyle.State_Selected:
            pen = QPen(QColor(0, 120, 215), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect().adjusted(2, 2, -2, -2))


# ==================== CurvedArrowItem ====================
class CurvedArrowItem(QGraphicsPathItem):
    """Изогнутая стрелка (квадратичная кривая Безье).
    Кривая обрезается внутри тела наконечника, чтобы обводка
    не выходила за его пределы при любой толщине пера."""

    # Коэффициент притапливания: 1.0 = по основанию, <1.0 = глубже
    TRIM_FACTOR = 0.65

    def __init__(self, start, end, ctrl, pen):
        super().__init__()
        self._start = start
        self._end = end
        self._ctrl = ctrl
        self._pen = QPen(pen)
        self.setFlags(QGraphicsPathItem.ItemIsMovable | QGraphicsPathItem.ItemIsSelectable)
        self.setCacheMode(QGraphicsItem.NoCache)
        self.setPen(pen)
        self.build_path(start, end, ctrl)

    def set_curve(self, start, end, ctrl):
        self.prepareGeometryChange()
        self._start = start
        self._end = end
        self._ctrl = ctrl
        self.build_path(start, end, ctrl)

    def build_path(self, start, end, ctrl):
        """Строит обрезанную кривую, заканчивающуюся внутри наконечника."""
        pw = self._pen.widthF()
        asz = max(8, 8 + pw * 3)
        ar = math.radians(20)

        # Расстояние от острия до точки обрезки вдоль касательной
        back_offset = asz * math.cos(ar) * self.TRIM_FACTOR

        # Касательная в конце кривой (от ctrl к end)
        dx = end.x() - ctrl.x()
        dy = end.y() - ctrl.y()
        tangent_len = math.hypot(dx, dy)

        if tangent_len < 1 or back_offset < 1:
            # Вырожденный случай — рисуем полную кривую
            path = QPainterPath()
            path.moveTo(start)
            path.quadTo(ctrl, end)
            self.setPath(path)
            return

        # Проверяем, что кривая достаточно длинная для обрезки
        total_len = math.hypot(end.x() - start.x(), end.y() - start.y())
        if back_offset >= total_len * 0.8:
            path = QPainterPath()
            path.moveTo(start)
            path.quadTo(ctrl, end)
            self.setPath(path)
            return

        # Находим параметр t_cut бинарным поиском
        t_cut = self._find_t_for_distance(start, ctrl, end, back_offset)

        if t_cut <= 0.05:
            path = QPainterPath()
            path.moveTo(start)
            path.quadTo(ctrl, end)
            self.setPath(path)
            return

        # Обрезаем кривую декомпозицией де Кастельжо
        p01 = self._lerp(start, ctrl, t_cut)
        p12 = self._lerp(ctrl, end, t_cut)
        p012 = self._lerp(p01, p12, t_cut)

        path = QPainterPath()
        path.moveTo(start)
        path.quadTo(p01, p012)
        self.setPath(path)

    @staticmethod
    def _lerp(a, b, t):
        """Линейная интерполяция между QPointF."""
        return QPointF(a.x() + t * (b.x() - a.x()),
                       a.y() + t * (b.y() - a.y()))

    @staticmethod
    def _quad_bezier_point(start, ctrl, end, t):
        """Точка на квадратичной кривой Безье при параметре t."""
        mt = 1.0 - t
        x = mt * mt * start.x() + 2 * mt * t * ctrl.x() + t * t * end.x()
        y = mt * mt * start.y() + 2 * mt * t * ctrl.y() + t * t * end.y()
        return QPointF(x, y)

    def _find_t_for_distance(self, start, ctrl, end, target_distance):
        """Бинарный поиск параметра t, при котором точка на кривой
        находится на расстоянии target_distance от end."""
        lo, hi = 0.0, 1.0
        for _ in range(30):
            mid = (lo + hi) / 2.0
            point = self._quad_bezier_point(start, ctrl, end, mid)
            dist = math.hypot(point.x() - end.x(), point.y() - end.y())
            if dist < target_distance:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    def setPen(self, pen):
        self.prepareGeometryChange()
        self._pen = QPen(pen)
        super().setPen(pen)
        self.build_path(self._start, self._end, self._ctrl)

    def pen(self):
        """Возвращает текущее перо."""
        return self._pen

    def paint(self, painter, option, widget):
        # Кривая — рисуем напрямую с RoundCap (как у прямой стрелки)
        lp = QPen(self._pen)
        lp.setCapStyle(Qt.RoundCap)
        lp.setJoinStyle(Qt.RoundJoin)
        painter.setPen(lp)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

        # Наконечник — рисуется по оригинальным _end и _ctrl
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
        p2 = end_point - QPointF(asz * math.cos(angle - ar),
                                 asz * math.sin(angle - ar))
        p3 = end_point - QPointF(asz * math.cos(angle + ar),
                                 asz * math.sin(angle + ar))

        hp = QPen(self._pen)
        hp.setCapStyle(Qt.FlatCap)
        hp.setJoinStyle(Qt.MiterJoin)
        painter.setPen(hp)
        painter.setBrush(QColor(self._pen.color()))
        painter.drawPolygon(QPolygonF([p2, p1, p3]))

        # Рамка выделения
        if option.state & QStyle.State_Selected:
            pen = QPen(QColor(0, 120, 215), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect().adjusted(2, 2, -2, -2))

    def boundingRect(self):
        pw = self._pen.widthF()
        arrow_size = max(8, 8 + pw * 3)
        margin = arrow_size + pw / 2 + 5
        return self.path().boundingRect().adjusted(-margin, -margin, margin, margin)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(HIT_AREA_PADDING * 2)
        path = stroker.createStroke(self.path())
        # Добавляем область наконечника для корректного клика
        end_point = self._end
        dx = end_point.x() - self._ctrl.x()
        dy = end_point.y() - self._ctrl.y()
        length = math.hypot(dx, dy)
        if length > 0:
            angle = math.atan2(dy, dx)
            pw = self._pen.widthF()
            asz = max(8, 8 + pw * 3)
            ar = math.radians(20)
            p1 = end_point
            p2 = end_point - QPointF(asz * math.cos(angle - ar),
                                     asz * math.sin(angle - ar))
            p3 = end_point - QPointF(asz * math.cos(angle + ar),
                                     asz * math.sin(angle + ar))
            head = QPainterPath()
            head.moveTo(p2)
            head.lineTo(p1)
            head.lineTo(p3)
            head.closeSubpath()
            path.addPath(head)
        return path

    def isEmpty(self):
        return math.hypot(self._end.x() - self._start.x(),
                          self._end.y() - self._start.y()) < 1


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
        self.setCacheMode(QGraphicsItem.NoCache)
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
        p2_end = end - QPointF(arrow_size * math.cos(angle - ar),
                               arrow_size * math.sin(angle - ar))
        p3_end = end - QPointF(arrow_size * math.cos(angle + ar),
                               arrow_size * math.sin(angle + ar))

        base_start = start + e * back_offset
        p2_start = start + QPointF(arrow_size * math.cos(angle - ar),
                                   arrow_size * math.sin(angle - ar))
        p3_start = start + QPointF(arrow_size * math.cos(angle + ar),
                                   arrow_size * math.sin(angle + ar))

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