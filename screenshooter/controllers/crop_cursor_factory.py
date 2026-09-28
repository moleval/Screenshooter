"""
Модуль: controllers/crop_cursor_factory.py
Описание: Фабрика курсоров для режима обрезки.
          Создаёт и кэширует курсор с иконкой обрезки.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor

from ..widgets.icon_manager import IconManager

from ..constants import CROP_CURSOR_SIZE
from ..theme import theme_manager


class CropCursorFactory:
    """Создаёт и кэширует курсоры для режима обрезки."""

    _cursor = None

    @classmethod
    def get_cursor(cls):
        """Возвращает курсор с иконкой обрезки."""
        if cls._cursor is not None:
            return cls._cursor

        size = CROP_CURSOR_SIZE
        center = size // 2
        pixmap = IconManager.icon(
            "crop",
            size=size,
            color=theme_manager.get_color("crop_cursor_line"),
        ).pixmap(size, size)

        cls._cursor = QCursor(pixmap, center, center)
        return cls._cursor

    @classmethod
    def reset(cls):
        cls._cursor = None