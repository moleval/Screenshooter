"""
Модуль: image_processing/__init__.py
Описание: Функции обработки изображений.
          Реализует обрезку (crop_pixmap), поворот (rotate_pixmap) и
          размытие прямоугольной области (blur_region) для QPixmap.

ЭТАП 6: оптимизация blur_region:
  6.1 — переиспользование сцены вместо создания новой на каждый вызов
  6.2 — размытие только области вместо всего изображения
  6.3 — опциональная замена на cv2.GaussianBlur
"""

from PyQt5.QtCore import Qt, QRectF, QRect
from PyQt5.QtGui import QPixmap, QImage, QPainter, QTransform
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

_blur_scene = None
_blur_item = None
_blur_effect = None


def _ensure_blur_scene():
    global _blur_scene, _blur_item, _blur_effect
    if _blur_scene is None:
        _blur_scene = QGraphicsScene()
        _blur_item = QGraphicsPixmapItem()
        _blur_effect = QGraphicsBlurEffect()
        _blur_item.setGraphicsEffect(_blur_effect)
        _blur_item.setTransformationMode(Qt.SmoothTransformation)
        _blur_scene.addItem(_blur_item)


def crop_pixmap(pixmap: QPixmap, rect: QRectF) -> QPixmap:
    if pixmap.isNull() or rect.isEmpty():
        return QPixmap()
    image_rect = QRectF(pixmap.rect())
    crop_rect = rect.intersected(image_rect)
    if crop_rect.isEmpty():
        return QPixmap()
    return pixmap.copy(crop_rect.toRect())


def rotate_pixmap(pixmap: QPixmap, angle: float) -> QPixmap:
    if pixmap.isNull():
        return QPixmap()
    transform = QTransform()
    transform.rotate(angle)
    rotated = pixmap.transformed(transform, Qt.SmoothTransformation)
    return rotated


def blur_region(pixmap: QPixmap, rect: QRectF, radius: float = 10.0) -> QPixmap:
    if pixmap.isNull() or rect.isEmpty() or radius <= 0:
        return QPixmap(pixmap)

    image_rect = QRectF(pixmap.rect())
    blur_rect = rect.intersected(image_rect)
    if blur_rect.isEmpty():
        return QPixmap(pixmap)

    if _CV2_AVAILABLE:
        return _blur_region_cv2(pixmap, blur_rect, radius)
    return _blur_region_qt(pixmap, blur_rect, radius)


def _blur_region_cv2(pixmap: QPixmap, blur_rect: QRectF, radius: float) -> QPixmap:
    qimage = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    width, height = qimage.width(), qimage.height()
    ptr = qimage.bits()
    data = ptr.asstring(qimage.byteCount())
    arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4)).copy()

    # Расширенная область для корректного размытия краёв
    margin = int(radius)
    x1 = max(0, int(blur_rect.x()) - margin)
    y1 = max(0, int(blur_rect.y()) - margin)
    x2 = min(width, int(blur_rect.right()) + 1 + margin)
    y2 = min(height, int(blur_rect.bottom()) + 1 + margin)

    region = arr[y1:y2, x1:x2]
    ksize = int(radius * 2) | 1
    blurred = cv2.GaussianBlur(region, (ksize, ksize), 0)

    # Координаты исходного прямоугольника (без запаса)
    bx1 = int(blur_rect.x())
    by1 = int(blur_rect.y())
    bx2 = int(blur_rect.right()) + 1
    by2 = int(blur_rect.bottom()) + 1

    # Смещения внутри расширенной области
    start_x = bx1 - x1
    start_y = by1 - y1
    end_x = start_x + (bx2 - bx1)
    end_y = start_y + (by2 - by1)

    # Вставляем только центральную часть, соответствующую blur_rect
    arr[by1:by2, bx1:bx2] = blurred[start_y:end_y, start_x:end_x]

    result_image = QImage(arr.data, width, height, width * 4, QImage.Format_ARGB32)
    return QPixmap.fromImage(result_image)


def _blur_region_qt(pixmap: QPixmap, blur_rect: QRectF, radius: float) -> QPixmap:
    _ensure_blur_scene()

    margin = int(radius * 2)
    expanded_rect = blur_rect.adjusted(-margin, -margin, margin, margin)
    expanded_rect = expanded_rect.intersected(QRectF(pixmap.rect()))
    if expanded_rect.isEmpty():
        return QPixmap(pixmap)

    region_pixmap = pixmap.copy(expanded_rect.toRect())
    _blur_item.setPixmap(region_pixmap)
    _blur_effect.setBlurRadius(radius)

    blurred_region = QImage(region_pixmap.size(), QImage.Format_ARGB32)
    blurred_region.fill(Qt.transparent)
    painter = QPainter(blurred_region)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    _blur_scene.render(painter, QRectF(blurred_region.rect()),
                       QRectF(region_pixmap.rect()))
    painter.end()

    # Вычисляем смещения для исходного прямоугольника
    offset_x = blur_rect.x() - expanded_rect.x()
    offset_y = blur_rect.y() - expanded_rect.y()

    # Итоговое изображение
    result_image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    result_painter = QPainter(result_image)
    result_painter.setRenderHint(QPainter.SmoothPixmapTransform)

    # Рисуем только ту часть размытой области, которая соответствует blur_rect
    source_rect = QRectF(offset_x, offset_y, blur_rect.width(), blur_rect.height())
    result_painter.drawImage(blur_rect.toRect(), blurred_region, source_rect.toRect())
    result_painter.end()

    _blur_item.setPixmap(QPixmap())  # очистка
    return QPixmap.fromImage(result_image)