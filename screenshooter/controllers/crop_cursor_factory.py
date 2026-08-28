"""
Модуль: controllers/crop_cursor_factory.py
Описание: Фабрика курсоров для режима обрезки.
          Создаёт и кэширует контрастный курсор-перекрестие.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPen, QPixmap, QPainter, QCursor

from ..constants import (
    CROP_CURSOR_SIZE,
    CROP_CURSOR_OUTLINE_WIDTH,
    CROP_CURSOR_LINE_WIDTH,
)
from ..theme import theme_manager


class CropCursorFactory:
    """Создаёт и кэширует курсоры для режима обрезки."""

    _cursor = None

    @classmethod
    def get_cursor(cls):
        """Возвращает курсор-перекрестие для режима обрезки."""
        if cls._cursor is not None:
            return cls._cursor

        size = CROP_CURSOR_SIZE
        center = size // 2
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        outline_color = theme_manager.get_color('crop_cursor_outline')
        line_color = theme_manager.get_color('crop_cursor_line')

        pen_outline = QPen(outline_color, CROP_CURSOR_OUTLINE_WIDTH)
        painter.setPen(pen_outline)
        painter.drawLine(center, 0, center, size)
        painter.drawLine(0, center, size, center)

        pen_main = QPen(line_color, CROP_CURSOR_LINE_WIDTH)
        painter.setPen(pen_main)
        painter.drawLine(center, 0, center, size)
        painter.drawLine(0, center, size, center)

        painter.end()

        cls._cursor = QCursor(pixmap, center, center)
        return cls._cursor

    @classmethod
    def reset(cls):
        """Сбрасывает кэш курсора, чтобы он пересоздался с новыми цветами."""
        cls._cursor = None