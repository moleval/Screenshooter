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

# ЭТАП 6.3: опциональная поддержка OpenCV
try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

# ЭТАП 6.1: ленивая инициализация сцены (создаётся при первом вызове)
_blur_scene = None
_blur_item = None
_blur_effect = None


def _ensure_blur_scene():
    """Создаёт сцену для размытия при первом вызове (после QApplication)."""
    global _blur_scene, _blur_item, _blur_effect
    if _blur_scene is None:
        _blur_scene = QGraphicsScene()
        _blur_item = QGraphicsPixmapItem()
        _blur_effect = QGraphicsBlurEffect()
        _blur_item.setGraphicsEffect(_blur_effect)
        _blur_item.setTransformationMode(Qt.SmoothTransformation)
        _blur_scene.addItem(_blur_item)


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

    # ЭТАП 6.3: используем cv2, если доступен (быстрый путь)
    if _CV2_AVAILABLE:
        return _blur_region_cv2(pixmap, blur_rect, radius)

    # ЭТАП 6.1 + 6.2: переиспользование сцены + размытие только области
    return _blur_region_qt(pixmap, blur_rect, radius)


def _blur_region_cv2(pixmap: QPixmap, blur_rect: QRectF, radius: float) -> QPixmap:
    """
    ЭТАП 6.3: Размытие через OpenCV (быстрый путь).
    Ускоряет в 10-20 раз по сравнению с QGraphicsBlurEffect.
    """
    # Конвертируем QPixmap в QImage формата ARGB32
    qimage = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    width, height = qimage.width(), qimage.height()

    # Получаем доступ к данным пикселей
    ptr = qimage.bits()
    ptr.setArraySize(qimage.byteCount())
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4)).copy()

    # Вырезаем область размытия с запасом для корректных границ
    margin = int(radius)
    x1 = max(0, int(blur_rect.x()) - margin)
    y1 = max(0, int(blur_rect.y()) - margin)
    x2 = min(width, int(blur_rect.right()) + 1 + margin)
    y2 = min(height, int(blur_rect.bottom()) + 1 + margin)

    region = arr[y1:y2, x1:x2]

    # Применяем Gaussian blur (размер ядра должен быть нечётным)
    ksize = int(radius * 2) | 1
    blurred = cv2.GaussianBlur(region, (ksize, ksize), 0)

    # Вставляем размытую область обратно
    arr[y1:y2, x1:x2] = blurred

    # Конвертируем обратно в QPixmap
    result_image = QImage(arr.data, width, height, width * 4, QImage.Format_ARGB32)
    return QPixmap.fromImage(result_image)


def _blur_region_qt(pixmap: QPixmap, blur_rect: QRectF, radius: float) -> QPixmap:
    """
    ЭТАП 6.1 + 6.2: Размытие через QGraphicsBlurEffect (запасной путь).
    Переиспользует сцену и размывает только область, а не всё изображение.
    """
    # ЭТАП 6.1: создаём сцену при первом вызове (ленивая инициализация)
    _ensure_blur_scene()

    # ЭТАП 6.2: вырезаем область с запасом для корректных границ размытия
    margin = int(radius * 2)
    expanded_rect = blur_rect.adjusted(-margin, -margin, margin, margin)
    expanded_rect = expanded_rect.intersected(QRectF(pixmap.rect()))

    if expanded_rect.isEmpty():
        return QPixmap(pixmap)

    # Вырезаем только нужную область
    region_pixmap = pixmap.copy(expanded_rect.toRect())

    # Переиспользуем сцену вместо создания новой
    _blur_item.setPixmap(region_pixmap)
    _blur_effect.setBlurRadius(radius)

    # Рендерим только область (а не всё изображение)
    blurred_region = QImage(region_pixmap.size(), QImage.Format_ARGB32)
    blurred_region.fill(Qt.transparent)
    painter = QPainter(blurred_region)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    _blur_scene.render(painter, QRectF(blurred_region.rect()),
                       QRectF(region_pixmap.rect()))
    painter.end()

    # Копируем исходное изображение
    result_image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)

    # Вычисляем смещение области размытия внутри расширенной области
    offset_x = blur_rect.x() - expanded_rect.x()
    offset_y = blur_rect.y() - expanded_rect.y()

    # Накладываем размытую область на исходное изображение
    result_painter = QPainter(result_image)
    result_painter.setRenderHint(QPainter.SmoothPixmapTransform)
    source_rect = QRectF(offset_x, offset_y,
                         blur_rect.width(), blur_rect.height())
    result_painter.drawImage(blur_rect.toRect(), blurred_region,
                             source_rect.toRect())
    result_painter.end()

    # Очищаем пиксмап элемента, чтобы не удерживать память
    _blur_item.setPixmap(QPixmap())

    return QPixmap.fromImage(result_image)