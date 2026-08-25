"""Элемент вставленного изображения."""

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPixmap, QColor, QTransform
from PyQt5.QtWidgets import QGraphicsPixmapItem
from .crop_handles import CropHandles


class PastedImageItem(QGraphicsPixmapItem):
    """
    Вставленное изображение как аннотация.
    Поддерживает перемещение, изменение размера, удаление.
    """

    HANDLE_COLOR = QColor(0, 120, 215)
    MIN_SIZE = 10

    def __init__(self, pixmap: QPixmap, view):
        super().__init__(pixmap)
        self.view = view
        self.original_pixmap = pixmap
        self.scale = 1.0

        self.setFlags(QGraphicsPixmapItem.ItemIsMovable | QGraphicsPixmapItem.ItemIsSelectable)
        self.setTransformationMode(Qt.SmoothTransformation)
        self.setZValue(500)

        self.handles = None

    def set_image_scale(self, scale: float):
        if scale <= 0:
            return
        self.scale = scale
        # Вызываем prepareGeometryChange, чтобы boundingRect обновился корректно
        self.prepareGeometryChange()
        new_pixmap = self.original_pixmap.scaled(
            int(self.original_pixmap.width() * scale),
            int(self.original_pixmap.height() * scale),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.setPixmap(new_pixmap)
        self.update_handles()

    def crop(self, rect: QRectF):
        """Обрезает изображение по прямоугольнику в локальных координатах."""
        if rect.isEmpty():
            return
        new_pixmap = self.original_pixmap.copy(rect.toRect())
        if new_pixmap.isNull():
            return
        self.prepareGeometryChange()
        self.original_pixmap = new_pixmap
        self.scale = 1.0
        self.setPixmap(new_pixmap)
        self.update_handles()

    def rotate(self, angle: float):
        """Поворачивает изображение на заданный угол (кратно 90°)."""
        transform = QTransform().rotate(angle)
        new_pixmap = self.original_pixmap.transformed(transform, Qt.SmoothTransformation)
        if new_pixmap.isNull():
            return
        self.prepareGeometryChange()
        self.original_pixmap = new_pixmap
        self.scale = 1.0
        self.setPixmap(new_pixmap)
        self.update_handles()

    def show_handles(self):
        if self.handles is None:
            # Показываем только угловые маркеры
            self.handles = CropHandles(self.view, fill_color=self.HANDLE_COLOR, show_midpoints=False)
            scene_rect = self.mapRectToScene(self.boundingRect())
            self.handles.create_handles(scene_rect)
        else:
            self.update_handles()

    def hide_handles(self):
        if self.handles:
            self.handles.remove_handles()
            self.handles = None

    def update_handles(self):
        if self.handles:
            scene_rect = self.mapRectToScene(self.boundingRect())
            self.handles.update_handles(scene_rect)

    def remove(self):
        self.hide_handles()
        if self.scene():
            self.scene().removeItem(self)