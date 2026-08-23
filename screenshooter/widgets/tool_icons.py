"""Функции генерации иконок для инструментов."""

import math
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QPolygonF, QFont, QIcon, QPainterPath


def create_tool_icon(tool_type, color):
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    if tool_type == "pointer":
        painter.setBrush(QColor(30, 30, 30))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(QPolygonF([QPointF(7,5), QPointF(7,25), QPointF(12,20),
                                      QPointF(18,27), QPointF(21,24), QPointF(15,17),
                                      QPointF(25,15)]))
    elif tool_type == "rect":
        painter.setPen(QPen(color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(6, 6, 20, 20)
    elif tool_type == "ellipse":
        painter.setPen(QPen(color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(6, 6, 20, 20)
    elif tool_type == "arrow":
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(QPolygonF([QPointF(25,5), QPointF(25,25), QPointF(20,20),
                                      QPointF(14,27), QPointF(11,24), QPointF(16,17),
                                      QPointF(7,15)]))
    elif tool_type == "text":
        painter.setPen(QPen(color, 2))
        painter.setFont(QFont("Arial", 20, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "T")
    elif tool_type == "line":
        painter.setPen(QPen(color, 2))
        painter.drawLine(6, 6, 26, 26)
    painter.end()
    return QIcon(pixmap)


def create_line_mode_icon(mode):
    pixmap = QPixmap(26, 26)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    if mode == "straight":
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.drawLine(3, 13, 23, 13)
    elif mode == "dashed":
        pen = QPen(QColor(50, 50, 50), 2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(3, 13, 23, 13)
    elif mode == "wavy":
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        path = QPainterPath()
        path.moveTo(3, 13)
        x_start, y_start = 3, 13
        for x in range(4, 24, 2):
            y = 13 + 4 * math.sin((x - 3) * 0.9)
            mid_x = (x_start + x) / 2
            mid_y = (y_start + y) / 2
            path.quadTo(mid_x, mid_y, x, y)
            x_start, y_start = x, y
        painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def create_arrow_mode_icon(mode):
    pixmap = QPixmap(26, 26)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    color = QColor(50, 50, 50)

    if mode == "straight":
        painter.setPen(QPen(color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(3, 13, 20, 13)
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([QPointF(23,13), QPointF(16,8), QPointF(16,18)]))
    elif mode == "curved":
        cx, cy = 13.0, 14.0
        radius = 10.0
        start_angle = 210.0
        sweep_angle = -210.0
        rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
        path = QPainterPath()
        path.arcMoveTo(rect, start_angle)
        path.arcTo(rect, start_angle, sweep_angle)
        painter.setPen(QPen(color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        end_angle = start_angle + sweep_angle
        end_angle_rad = math.radians(end_angle)
        end_point = QPointF(cx + radius * math.cos(end_angle_rad),
                            cy - radius * math.sin(end_angle_rad))

        tangent_angle = math.radians(end_angle - 90.0)
        arrow_rotation_offset_deg = 35
        tangent_angle += math.radians(arrow_rotation_offset_deg)
        tx = math.cos(tangent_angle)
        ty = -math.sin(tangent_angle)
        length = math.hypot(tx, ty)
        if length != 0:
            tx /= length
            ty /= length

        arrow_length = 10.0
        arrow_half_width = 6.0
        back_x, back_y = -tx, -ty
        normal_x, normal_y = -ty, tx

        p1 = end_point
        p2 = QPointF(end_point.x() + back_x * arrow_length + normal_x * arrow_half_width,
                     end_point.y() + back_y * arrow_length + normal_y * arrow_half_width)
        p3 = QPointF(end_point.x() + back_x * arrow_length - normal_x * arrow_half_width,
                     end_point.y() + back_y * arrow_length - normal_y * arrow_half_width)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([p1, p2, p3]))
    elif mode == "dimension":
        dimension_color = QColor(160, 0, 0)
        painter.setPen(QPen(dimension_color, 1))
        painter.drawLine(3, 15, 23, 15)
        painter.setBrush(dimension_color)
        painter.drawPolygon(QPolygonF([QPointF(3,15), QPointF(8,10), QPointF(8,20)]))
        painter.drawPolygon(QPolygonF([QPointF(23,15), QPointF(18,10), QPointF(18,20)]))
        painter.setPen(QPen(dimension_color, 2))
        painter.drawLine(3, 10, 3, 20)
        painter.drawLine(23, 10, 23, 20)
        painter.setPen(QColor(50, 50, 50))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(QRectF(5, 0, 16, 10), Qt.AlignCenter, "22")
    painter.end()
    return QIcon(pixmap)


def create_shape_mode_icon(mode):
    pixmap = QPixmap(26, 26)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    if mode == "rect":
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(3, 7, 20, 12))
    elif mode == "square":
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(3, 3, 20, 20))
    elif mode == "filled":
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 230, 0, 180))
        painter.drawRect(QRectF(4, 4, 18, 18))
        painter.setPen(QPen(QColor(200, 180, 0), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(4, 4, 18, 18))
    painter.end()
    return QIcon(pixmap)


def create_ellipse_mode_icon(mode):
    pixmap = QPixmap(26, 26)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    if mode == "ellipse":
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(3, 7, 20, 12))
    elif mode == "circle":
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(3, 3, 20, 20))
    elif mode == "cloud":
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.setBrush(Qt.NoBrush)
        x0, y0, x1, y1 = 4, 4, 22, 22
        amp, segments = 2, 3
        path = QPainterPath()
        path.moveTo(x0, y0)
        for i in range(1, segments + 1):
            t = i / segments
            cx = x0 + (x1 - x0) * (i - 0.5) / segments
            cy = y0 - amp
            ex = x0 + (x1 - x0) * t
            ey = y0
            path.quadTo(cx, cy, ex, ey)
        for i in range(1, segments + 1):
            t = i / segments
            cx = x1 + amp
            cy = y0 + (y1 - y0) * (i - 0.5) / segments
            ex = x1
            ey = y0 + (y1 - y0) * t
            path.quadTo(cx, cy, ex, ey)
        for i in range(1, segments + 1):
            t = i / segments
            cx = x1 - (x1 - x0) * (i - 0.5) / segments
            cy = y1 + amp
            ex = x1 - (x1 - x0) * t
            ey = y1
            path.quadTo(cx, cy, ex, ey)
        for i in range(1, segments + 1):
            t = i / segments
            cx = x0 - amp
            cy = y1 - (y1 - y0) * (i - 0.5) / segments
            ex = x0
            ey = y1 - (y1 - y0) * t
            path.quadTo(cx, cy, ex, ey)
        path.closeSubpath()
        painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


# --------------------------------------------------------------
# Иконки для тулбара «Редактирование скриншота»
# --------------------------------------------------------------

EDIT_ICON_COLOR = QColor(42, 130, 218)  # голубовато-синий


def create_crop_icon():
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    pen = QPen(EDIT_ICON_COLOR, 2)
    pen.setCosmetic(True)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    # Прямоугольник (уменьшен до ~90% от исходного размера)
    painter.drawRect(QRectF(7.2, 7.2, 17.6, 17.6))

    painter.setPen(Qt.NoPen)
    painter.setBrush(EDIT_ICON_COLOR)
    dot_radius = 1.8   # было 2.0, теперь ~90%

    positions = [
        QPointF(4.2, 7.2), QPointF(7.2, 4.2),
        QPointF(27.8, 7.2), QPointF(24.8, 4.2),
        QPointF(27.8, 24.8), QPointF(24.8, 27.8),
        QPointF(4.2, 24.8), QPointF(7.2, 27.8)
    ]
    for pos in positions:
        painter.drawEllipse(pos, dot_radius, dot_radius)

    painter.end()
    return QIcon(pixmap)


def create_rotate_icon(clockwise=True):
    if clockwise:
        return create_rotate_icon_cw()
    else:
        cw = create_rotate_icon_cw()
        img = cw.pixmap(32, 32).toImage()
        mirror = img.mirrored(True, False)
        return QIcon(QPixmap.fromImage(mirror))


def create_rotate_icon_cw():
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    cx, cy = 16.0, 16.0
    radius = 11.0
    start_angle = 210.0
    sweep_angle = -210.0
    rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)

    path = QPainterPath()
    path.arcMoveTo(rect, start_angle)
    path.arcTo(rect, start_angle, sweep_angle)

    pen = QPen(EDIT_ICON_COLOR, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    pen.setCosmetic(True)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)

    end_angle = start_angle + sweep_angle
    end_angle_rad = math.radians(end_angle)
    end_point = QPointF(cx + radius * math.cos(end_angle_rad),
                        cy - radius * math.sin(end_angle_rad))

    tangent_angle = math.radians(end_angle - 90.0)
    arrow_rotation_offset_deg = 35
    tangent_angle += math.radians(arrow_rotation_offset_deg)
    tx = math.cos(tangent_angle)
    ty = -math.sin(tangent_angle)
    length = math.hypot(tx, ty)
    if length != 0:
        tx /= length
        ty /= length

    arrow_length = 10.0
    arrow_half_width = 6.0
    back_x, back_y = -tx, -ty
    normal_x, normal_y = -ty, tx

    p1 = end_point
    p2 = QPointF(end_point.x() + back_x * arrow_length + normal_x * arrow_half_width,
                 end_point.y() + back_y * arrow_length + normal_y * arrow_half_width)
    p3 = QPointF(end_point.x() + back_x * arrow_length - normal_x * arrow_half_width,
                 end_point.y() + back_y * arrow_length - normal_y * arrow_half_width)

    painter.setPen(Qt.NoPen)
    painter.setBrush(EDIT_ICON_COLOR)
    painter.drawPolygon(QPolygonF([p1, p2, p3]))

    painter.end()
    return QIcon(pixmap)


def create_blur_icon():
    """Иконка в виде кисточки."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Ручка кисточки
    pen = QPen(EDIT_ICON_COLOR, 2)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawLine(QPointF(20, 4), QPointF(8, 16))

    # Щетина
    painter.setPen(Qt.NoPen)
    painter.setBrush(EDIT_ICON_COLOR)
    path = QPainterPath()
    path.moveTo(10, 16)
    path.lineTo(24, 26)
    path.lineTo(10, 24)
    path.closeSubpath()
    painter.drawPath(path)

    # Блик на щетине
    painter.setBrush(QColor(255, 255, 255, 200))
    painter.drawEllipse(QPointF(14, 21), 1.5, 2.5)

    painter.end()
    return QIcon(pixmap)