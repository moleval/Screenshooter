"""Оверлей для выбора монитора (PrintScreen)."""

from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import (QPainter, QPen, QColor, QFont, QGuiApplication,
                         QPainterPath, QPainterPathStroker)
from PyQt5.QtWidgets import QDialog, QApplication
from .virtual_screen import get_virtual_screen_geometry


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

        # Рисуем рамку для каждого экрана отдельно
        offset = self.geometry().topLeft()
        painter.setPen(QPen(Qt.white, 2, Qt.DashLine))

        screens = QGuiApplication.screens()
        multiple_screens = len(screens) > 1

        for i, screen in enumerate(screens):
            local_rect = screen.geometry().translated(-offset.x(), -offset.y())
            painter.drawRect(local_rect)

            # Если мониторов несколько – выводим крупную надпись с номером экрана
            if multiple_screens:
                label = f"Экран {i + 1}"

                # Настройка шрифта
                font = QFont("Arial", 72, QFont.Bold)
                painter.setFont(font)

                # Определяем размеры текста для центрирования
                fm = painter.fontMetrics()
                text_width = fm.horizontalAdvance(label)
                text_height = fm.height()

                # Центр экрана
                center_x = local_rect.center().x()
                center_y = local_rect.center().y()

                # Прямоугольник для размещения текста по центру
                text_rect = QRect(center_x - text_width // 2,
                                  center_y - text_height // 2,
                                  text_width,
                                  text_height)

                # Создаём путь для чёткого контура
                path = QPainterPath()
                path.addText(text_rect.x(), text_rect.y() + text_height, font, label)  # базовая линия

                # Заливка жёлтым
                painter.fillPath(path, QColor(255, 255, 0))

                # Чёрная обводка
                stroker = QPainterPathStroker()
                stroker.setWidth(4)
                outline = stroker.createStroke(path)
                painter.fillPath(outline, QColor(128, 128, 128))

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.globalPos()
            screen = QGuiApplication.screenAt(pos)
            if screen:
                # Скрываем оверлей, чтобы он не попал в захват
                self.hide()
                QApplication.processEvents()  # даём системе скрыть окно

                # Захватываем экран напрямую
                self._selected_pixmap = screen.grabWindow(0)
                self.accept()  # закрываем диалог
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