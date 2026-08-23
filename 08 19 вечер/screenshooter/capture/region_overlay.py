"""Оверлей для выделения области (горячая клавиша Alt+PrintScreen)."""

from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import QDialog
from .virtual_screen import grab_virtual_screen, get_virtual_screen_geometry


class RegionCaptureOverlay(QDialog):
    captured = pyqtSignal(object)  # QPixmap

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setGeometry(get_virtual_screen_geometry())
        self.setCursor(Qt.CrossCursor)
        self._start_point = None
        self._end_point = None
        self._selection_rect = None
        self._pixmap = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 30))
        if self._selection_rect and not self._selection_rect.isNull():
            painter.fillRect(self._selection_rect, QColor(0, 0, 0, 0))
            painter.setPen(QPen(Qt.white, 2, Qt.SolidLine))
            painter.drawRect(self._selection_rect)
            x, y, w, h = self._selection_rect.x(), self._selection_rect.y(), self._selection_rect.width(), self._selection_rect.height()
            info = f"({x}, {y})  {w}×{h}"
            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 10))
            text_rect = painter.boundingRect(QRect(0, 0, 200, 30), Qt.AlignLeft, info)
            text_rect.moveTopLeft(QPoint(self._selection_rect.left() + 4, self._selection_rect.top() - 24))
            if text_rect.top() < 0:
                text_rect.moveTopLeft(QPoint(self._selection_rect.left() + 4, self._selection_rect.bottom() + 4))
            painter.fillRect(text_rect, QColor(0, 0, 0, 150))
            painter.drawText(text_rect, Qt.AlignLeft, info)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start_point = event.globalPos()
            self._end_point = self._start_point
            self._selection_rect = QRect(self._start_point, self._end_point).normalized()
            self.update()
        elif event.button() == Qt.RightButton:
            self.reject()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._start_point is not None:
            self._end_point = event.globalPos()
            self._selection_rect = QRect(self._start_point, self._end_point).normalized()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._selection_rect and not self._selection_rect.isNull():
            offset = self.geometry().topLeft()
            local_rect = self._selection_rect.translated(-offset.x(), -offset.y())
            full_pixmap = grab_virtual_screen()
            if not full_pixmap.isNull():
                self._pixmap = full_pixmap.copy(local_rect)
                self.accept()
            else:
                self.reject()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        super().keyPressEvent(event)

    def get_pixmap(self):
        return self._pixmap