"""Функции генерации иконок для инструментов."""

import math
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QPolygonF, QFont, QIcon, QPainterPath
from PyQt5.QtWidgets import QStyle


def create_tool_icon(tool_type, color):
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    if tool_type == 'pointer':
        painter.setBrush(QColor(30, 30, 30))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(QPolygonF([QPointF(7,5), QPointF(7,25), QPointF(12,20),
                                      QPointF(18,27), QPointF(21,24), QPointF(15,17),
                                      QPointF(25,15)]))
    elif tool_type == 'rect':
        painter.setPen(QPen(color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(6, 6, 20, 20)
    elif tool_type == 'ellipse':
        painter.setPen(QPen(color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(6, 6, 20, 20)
    elif tool_type == 'arrow':
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(QPolygonF([QPointF(25,5), QPointF(25,25), QPointF(20,20),
                                      QPointF(14,27), QPointF(11,24), QPointF(16,17),
                                      QPointF(7,15)]))
    elif tool_type == 'text':
        painter.setPen(QPen(color, 2))
        painter.setFont(QFont("Arial", 20, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "T")
    elif tool_type == 'line':
        painter.setPen(QPen(color, 2))
        painter.drawLine(6, 6, 26, 26)
    painter.end()
    return QIcon(pixmap)


def create_line_mode_icon(mode):
    pixmap = QPixmap(26, 26)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    if mode == 'straight':
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.drawLine(3, 13, 23, 13)
    elif mode == 'dashed':
        pen = QPen(QColor(50, 50, 50), 2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(3, 13, 23, 13)
    elif mode == 'wavy':
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        path = QPainterPath()
        path.moveTo(3, 13)
        for x in range(4, 24, 2):
            y = 13 + 4 * math.sin(x * 1.5)
            path.lineTo(x, y)
        painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def create_arrow_mode_icon(mode):
    pixmap = QPixmap(26, 26)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    if mode == 'straight':
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(3, 13, 20, 13)
        painter.drawPolygon(QPolygonF([QPointF(20,13), QPointF(14,8), QPointF(14,18)]))
    elif mode == 'curved':
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(3, 15)
        path.quadTo(13, 3, 20, 13)
        painter.drawPath(path)
        painter.drawPolygon(QPolygonF([QPointF(20,13), QPointF(14,8), QPointF(14,18)]))
    elif mode == 'dimension':
        painter.setPen(QPen(QColor(160, 0, 0), 2))
        painter.drawLine(3, 13, 23, 13)
        painter.drawPolygon(QPolygonF([QPointF(3,13), QPointF(8,8), QPointF(8,18)]))
        painter.drawPolygon(QPolygonF([QPointF(23,13), QPointF(18,8), QPointF(18,18)]))
        painter.drawLine(3, 8, 3, 18)
        painter.drawLine(23, 8, 23, 18)
        painter.setPen(QColor(50, 50, 50))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(QRectF(5, 0, 16, 10), Qt.AlignCenter, "12")
    painter.end()
    return QIcon(pixmap)


def create_shape_mode_icon(mode):
    pixmap = QPixmap(26, 26)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    if mode == 'rect':
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(3, 7, 20, 12))
    elif mode == 'square':
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(3, 3, 20, 20))
    elif mode == 'filled':
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
    if mode == 'ellipse':
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(3, 7, 20, 12))
    elif mode == 'circle':
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(3, 3, 20, 20))
    elif mode == 'cloud':
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(3, 3, 20, 20))
        painter.drawArc(QRectF(0, 0, 10, 8), 0, 180 * 16)
        painter.drawArc(QRectF(16, 0, 10, 8), 0, 180 * 16)
    painter.end()
    return QIcon(pixmap)