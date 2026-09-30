"""
Модуль: capture/virtual_screen.py
Описание: DPI-safe захват отдельных экранов, виртуального рабочего стола
          и областей в физических пикселях.
"""

import platform

import win32api
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtGui import QPixmap, QPainter


def get_virtual_screen_geometry():
    """Возвращает объединённую геометрию экранов в координатах Qt."""
    screens = QGuiApplication.screens()
    if not screens:
        return QRect()
    rect = screens[0].geometry()
    for screen in screens[1:]:
        rect = rect.united(screen.geometry())
    return rect


def get_screen_physical_geometry(screen):
    """Возвращает физическую геометрию монитора в координатах Windows."""
    if platform.system() == "Windows":
        try:
            for handle, _, _ in win32api.EnumDisplayMonitors():
                info = win32api.GetMonitorInfo(handle)
                if info.get("Device") == screen.name():
                    left, top, right, bottom = info["Monitor"]
                    return QRect(left, top, right - left, bottom - top)
        except Exception:
            pass

    geometry = screen.geometry()
    dpr = float(screen.devicePixelRatio() or 1.0)
    return QRect(
        round(geometry.left() * dpr),
        round(geometry.top() * dpr),
        round(geometry.width() * dpr),
        round(geometry.height() * dpr),
    )


def grab_screen_physical(screen):
    """Захватывает весь экран и возвращает изображение без логического DPR."""
    pixmap = screen.grabWindow(0)
    if pixmap.isNull():
        return QPixmap()

    result = QPixmap(pixmap)
    result.setDevicePixelRatio(1.0)
    return result


def _logical_rect_to_physical(screen, logical_rect):
    """Переводит прямоугольник Qt внутри экрана в физические пиксели."""
    geometry = screen.geometry()
    dpr = float(screen.devicePixelRatio() or 1.0)

    left = round((logical_rect.x() - geometry.x()) * dpr)
    top = round((logical_rect.y() - geometry.y()) * dpr)
    width = round(logical_rect.width() * dpr)
    height = round(logical_rect.height() * dpr)

    return QRect(left, top, max(0, width), max(0, height))


def grab_virtual_screen():
    """Создаёт физически точный снимок всего виртуального рабочего стола."""
    screens = QGuiApplication.screens()
    if not screens:
        return QPixmap()

    physical_rects = [
        (screen, get_screen_physical_geometry(screen))
        for screen in screens
    ]
    total_rect = physical_rects[0][1]
    for _, rect in physical_rects[1:]:
        total_rect = total_rect.united(rect)

    if total_rect.isNull():
        return QPixmap()

    pixmap = QPixmap(total_rect.size())
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)

    for screen, physical_rect in physical_rects:
        screen_pixmap = grab_screen_physical(screen)
        if screen_pixmap.isNull():
            continue
        offset = physical_rect.topLeft() - total_rect.topLeft()
        painter.drawPixmap(offset, screen_pixmap)

    painter.end()
    pixmap.setDevicePixelRatio(1.0)
    return pixmap


def grab_virtual_screen_region(logical_rect):
    """Захватывает область оверлея сразу в физических пикселях."""
    logical_rect = QRect(logical_rect).normalized()
    if logical_rect.isNull():
        return QPixmap()

    screens = QGuiApplication.screens()
    if not screens:
        return QPixmap()

    pieces = []
    physical_union = None

    for screen in screens:
        intersection = logical_rect.intersected(screen.geometry())
        if intersection.isNull():
            continue

        source = _logical_rect_to_physical(screen, intersection)
        screen_pixmap = grab_screen_physical(screen)
        if screen_pixmap.isNull() or source.isNull():
            continue

        source = source.intersected(screen_pixmap.rect())
        if source.isNull():
            continue

        monitor_rect = get_screen_physical_geometry(screen)
        physical_piece_rect = QRect(
            monitor_rect.left() + source.left(),
            monitor_rect.top() + source.top(),
            source.width(),
            source.height(),
        )
        pieces.append((screen_pixmap, source, physical_piece_rect))

        physical_union = (
            physical_piece_rect
            if physical_union is None
            else physical_union.united(physical_piece_rect)
        )

    if not pieces or physical_union is None or physical_union.isNull():
        return QPixmap()

    result = QPixmap(physical_union.size())
    result.fill(Qt.transparent)
    painter = QPainter(result)

    for screen_pixmap, source, physical_piece_rect in pieces:
        destination = physical_piece_rect.topLeft() - physical_union.topLeft()
        painter.drawPixmap(destination, screen_pixmap, source)

    painter.end()
    result.setDevicePixelRatio(1.0)
    return result


def grab_physical_rect(physical_rect):
    """Захватывает заданный прямоугольник виртуального рабочего стола."""
    physical_rect = QRect(physical_rect).normalized()
    if physical_rect.isNull():
        return QPixmap()

    screens = QGuiApplication.screens()
    pieces = []
    for screen in screens:
        monitor_rect = get_screen_physical_geometry(screen)
        intersection = physical_rect.intersected(monitor_rect)
        if intersection.isNull():
            continue

        screen_pixmap = grab_screen_physical(screen)
        if screen_pixmap.isNull():
            continue

        source = QRect(
            intersection.left() - monitor_rect.left(),
            intersection.top() - monitor_rect.top(),
            intersection.width(),
            intersection.height(),
        ).intersected(screen_pixmap.rect())
        if source.isNull():
            continue

        pieces.append((screen_pixmap, source, intersection))

    if not pieces:
        return QPixmap()

    result = QPixmap(physical_rect.size())
    result.fill(Qt.transparent)
    painter = QPainter(result)

    for screen_pixmap, source, piece_rect in pieces:
        destination = piece_rect.topLeft() - physical_rect.topLeft()
        painter.drawPixmap(destination, screen_pixmap, source)

    painter.end()
    result.setDevicePixelRatio(1.0)
    return result
