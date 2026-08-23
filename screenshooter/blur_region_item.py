"""Графический элемент зоны размытия."""

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPen, QColor, QBrush
from PyQt5.QtWidgets import QGraphicsRectItem
from .crop_handles import CropHandles


class BlurRegionItem(QGraphicsRectItem):
    """
    Прямоугольник зоны размытия.
    Режимы:
    - drawing: красная полупрозрачная заливка, пунктирная красная граница (без маркеров)
    - active: без заливки, синяя пунктирная граница + 8 маркеров
    - inactive: тонкая красная пунктирная рамка, полупрозрачная заливка (постоянное состояние)
    """

    DRAWING_PEN_COLOR = QColor(255, 0, 0)
    DRAWING_BRUSH_COLOR = QColor(255, 0, 0, 60)
    ACTIVE_PEN_COLOR = QColor(0, 120, 215)
    ACTIVE_HANDLE_COLOR = QColor(0, 120, 215)
    INACTIVE_PEN_COLOR = QColor(255, 0, 0)
    INACTIVE_BRUSH_COLOR = QColor(255, 0, 0, 20)  # очень слабая заливка, чтобы зона была заметна

    def __init__(self, rect: QRectF, view, mode: str = 'active'):
        super().__init__(rect)
        self.view = view
        self.mode = mode
        self.handles = None

        self.setZValue(500)  # ниже аннотаций, чтобы не мешать им
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFlag(QGraphicsRectItem.ItemIsMovable, False)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, False)

        self._apply_mode()

    def _apply_mode(self):
        if self.mode == 'drawing':
            pen = QPen(self.DRAWING_PEN_COLOR, 2, Qt.DashLine)
            pen.setCosmetic(True)
            self.setPen(pen)
            self.setBrush(self.DRAWING_BRUSH_COLOR)
            self._remove_handles()
        elif self.mode == 'active':
            pen = QPen(self.ACTIVE_PEN_COLOR, 2, Qt.DashLine)
            pen.setCosmetic(True)
            self.setPen(pen)
            self.setBrush(QBrush(Qt.NoBrush))
            self._create_handles()
        elif self.mode == 'inactive':
            pen = QPen(self.INACTIVE_PEN_COLOR, 1, Qt.DashLine)
            pen.setCosmetic(True)
            self.setPen(pen)
            self.setBrush(self.INACTIVE_BRUSH_COLOR)
            self._remove_handles()

    def _create_handles(self):
        self._remove_handles()
        self.handles = CropHandles(self.view, fill_color=self.ACTIVE_HANDLE_COLOR)
        self.handles.create_handles(self.rect())

    def _remove_handles(self):
        if self.handles:
            self.handles.remove_handles()
            self.handles = None

    def set_mode(self, mode: str):
        if mode != self.mode:
            self.mode = mode
            self._apply_mode()

    def update_rect(self, rect: QRectF):
        self.setRect(rect)
        if self.handles:
            self.handles.update_handles(rect)

    def remove(self):
        self._remove_handles()
        if self.scene():
            self.scene().removeItem(self)