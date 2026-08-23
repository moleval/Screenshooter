"""Функции обработки изображений (обрезка, поворот, размытие)."""

from PyQt5.QtCore import Qt, QRectF, QRect
from PyQt5.QtGui import QPixmap, QImage, QPainter, QTransform
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect


def crop_pixmap(pixmap: QPixmap, rect: QRectF) -> QPixmap:
    """
    Вырезает прямоугольную область из QPixmap.

    Args:
        pixmap: Исходное изображение.
        rect: Прямоугольник в координатах изображения.

    Returns:
        Новый QPixmap с вырезанной областью.
    """
    if pixmap.isNull() or rect.isEmpty():
        return QPixmap()

    # Пересечение с границами изображения
    image_rect = QRectF(pixmap.rect())
    crop_rect = rect.intersected(image_rect)
    if crop_rect.isEmpty():
        return QPixmap()

    return pixmap.copy(crop_rect.toRect())


def rotate_pixmap(pixmap: QPixmap, angle: float) -> QPixmap:
    """
    Поворачивает изображение на заданный угол (кратно 90°).

    Args:
        pixmap: Исходное изображение.
        angle: Угол в градусах (90, -90, 180, 270 и т.д.).

    Returns:
        Повёрнутый QPixmap.
    """
    if pixmap.isNull():
        return QPixmap()

    transform = QTransform()
    transform.rotate(angle)
    rotated = pixmap.transformed(transform, Qt.SmoothTransformation)
    return rotated


def blur_region(pixmap: QPixmap, rect: QRectF, radius: float = 10.0) -> QPixmap:
    """
    Размывает прямоугольную область на изображении.

    Args:
        pixmap: Исходное изображение.
        rect: Область размытия в координатах изображения.
        radius: Радиус размытия.

    Returns:
        Новый QPixmap с размытой областью.
    """
    if pixmap.isNull() or rect.isEmpty() or radius <= 0:
        return QPixmap(pixmap)

    # Приводим прямоугольник к границам изображения
    image_rect = QRectF(pixmap.rect())
    blur_rect = rect.intersected(image_rect)
    if blur_rect.isEmpty():
        return QPixmap(pixmap)

    # Создаём размытую копию всего изображения через QGraphicsScene + QGraphicsBlurEffect
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(pixmap)
    item.setTransformationMode(Qt.SmoothTransformation)
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(radius)
    item.setGraphicsEffect(effect)
    scene.addItem(item)

    # Рендерим сцену в QImage
    blurred_image = QImage(pixmap.size(), QImage.Format_ARGB32)
    blurred_image.fill(Qt.transparent)
    painter = QPainter(blurred_image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    scene.render(painter, QRectF(blurred_image.rect()), QRectF(pixmap.rect()))
    painter.end()

    # Копируем исходное изображение
    result_image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)

    # Накладываем размытую область на исходное изображение
    result_painter = QPainter(result_image)
    result_painter.setRenderHint(QPainter.SmoothPixmapTransform)
    result_painter.drawImage(blur_rect.toRect(), blurred_image, blur_rect.toRect())
    result_painter.end()

    return QPixmap.fromImage(result_image)