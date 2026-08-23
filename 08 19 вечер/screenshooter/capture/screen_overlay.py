"""Оверлей для выбора монитора (горячая клавиша PrintScreen)."""

from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QGuiApplication
from PyQt5.QtWidgets import QDialog
from .virtual_screen import grab_virtual_screen, get_virtual_screen_geometry


class ScreenCaptureOverlay(QDialog):
    captured = pyqtSignal(object)  # QPixmap

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setGeometry(get_virtual_screen_geometry())
        self.setCursor(Qt.CrossCursor)
        self._selected_pixmap = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 30))
        painter.setPen(QPen(Qt.white, 2, Qt.DashLine))
        offset = self.geometry().topLeft()
        for screen in QGuiApplication.screens():
            rect = screen.geometry().translated(-offset.x(), -offset.y())
            painter.drawRect(rect)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.globalPos()
            screen = QGuiApplication.screenAt(pos)
            if screen:
                full = grab_virtual_screen()
                if not full.isNull():
                    total_rect = get_virtual_screen_geometry()
                    offset = total_rect.topLeft()
                    geo = screen.geometry()
                    local_rect = QRect(geo.x() - offset.x(), geo.y() - offset.y(),
                                       geo.width(), geo.height())
                    self._selected_pixmap = full.copy(local_rect)
                else:
                    self._selected_pixmap = screen.grabWindow(0)
                self.accept()
            else:
                event.ignore()
        elif event.button() == Qt.RightButton:
            self.reject()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        super().keyPressEvent(event)

    def get_pixmap(self):
        return self._selected_pixmap