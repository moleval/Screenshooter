"""
Модуль: utils.py
Описание: Вспомогательные функции и классы.
          Содержит resource_path для корректной работы с ресурсами при сборке,
          SelectAllLineEdit — QLineEdit с авто-выделением текста при фокусе,
          и загрузчик иконки приложения.
"""

import os
import sys

from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QLineEdit


def resource_path(relative_path):
    """Возвращает абсолютный путь к ресурсу, работает и в PyInstaller."""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def load_app_icon():
    """Загружает иконку приложения.

    Ищет иконку в resources/icon.png или resources/icon.jpg.
    Если не находит — возвращает пустой QIcon.
    """
    candidates = [
        resource_path("screenshooter/resources/icon.png"),
        resource_path("screenshooter/resources/icon.jpg"),
        resource_path("screenshooter/resources/icon.jpeg"),
        resource_path("screenshooter/resources/icon.ico"),
    ]
    for path in candidates:
        if os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                return QIcon(pixmap)
    return QIcon()


class SelectAllLineEdit(QLineEdit):
    """QLineEdit с автоматическим выделением текста при фокусе."""

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.selectAll()

    def focusInEvent(self, event):
        self.selectAll()
        super().focusInEvent(event)