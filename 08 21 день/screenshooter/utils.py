"""Вспомогательные утилиты."""

import os
import sys
from PyQt5.QtWidgets import QLineEdit


def resource_path(relative_path):
    """Возвращает абсолютный путь к ресурсу, работает и в PyInstaller."""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)


class SelectAllLineEdit(QLineEdit):
    """QLineEdit с автоматическим выделением текста при фокусе."""

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.selectAll()

    def focusInEvent(self, event):
        self.selectAll()
        super().focusInEvent(event)