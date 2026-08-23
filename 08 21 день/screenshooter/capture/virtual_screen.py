"""Функции для работы с виртуальным экраном (мультимониторность)."""

from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPixmap, QPainter, QGuiApplication


def get_virtual_screen_geometry():
    """Возвращает объединённую геометрию всех экранов."""
    screens = QGuiApplication.screens()
    if not screens:
        return QRect()
    rect = screens[0].geometry()
    for screen in screens[1:]:
        rect = rect.united(screen.geometry())
    return rect


def grab_virtual_screen():
    """Создаёт скриншот всего виртуального рабочего стола."""
    screens = QGuiApplication.screens()
    if not screens:
        return QPixmap()
    total_rect = get_virtual_screen_geometry()
    if total_rect.isNull():
        return QPixmap()
    pixmap = QPixmap(total_rect.size())
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    for screen in screens:
        geo = screen.geometry()
        offset = geo.topLeft() - total_rect.topLeft()
        screen_pixmap = screen.grabWindow(0)
        painter.drawPixmap(offset, screen_pixmap)
    painter.end()
    return pixmap