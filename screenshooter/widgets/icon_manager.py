"""Локальный менеджер SVG-иконок интерфейса.

SVG-файлы используют stroke="currentColor". Цвет задаётся при построении
QIcon, поэтому один и тот же набор SVG работает для светлой/тёмной темы.
"""

from pathlib import Path

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer

from ..theme import theme_manager


class IconManager:
    """Загружает локальные Lucide SVG и применяет семантический цвет."""

    ICON_SIZE = 20
    DISABLED_OPACITY = 0.4

    SELECTION = "selection"
    ANNOTATION = "annotation"
    EDITING = "editing"

    _ROOT = Path(__file__).resolve().parents[1] / "resources" / "icons"

    _ICONS = {
        "pointer": (SELECTION, "mouse-pointer-2.svg"),
        "line": (ANNOTATION, "minus.svg"),
        "rect": (ANNOTATION, "square.svg"),
        "ellipse": (ANNOTATION, "circle.svg"),
        "arrow": (ANNOTATION, "arrow-right.svg"),
        "text": (ANNOTATION, "type.svg"),
        "crop": (EDITING, "crop.svg"),
        "rotate-cw": (EDITING, "rotate-cw.svg"),
        "rotate-ccw": (EDITING, "rotate-cw.svg"),
        "undo": (EDITING, "undo-2.svg"),
        "redo": (EDITING, "redo-2.svg"),
    }

    _SELECTION_COLOR = QColor("#333333")
    _ANNOTATION_COLOR = QColor("#D25145")
    _EDITING_COLOR = QColor("#005A9E")

    @classmethod
    def _color_for_category(cls, category):
        if category == cls.SELECTION:
            return theme_manager.get_color("text")
        if category == cls.ANNOTATION:
            return QColor(cls._ANNOTATION_COLOR)
        if category == cls.EDITING:
            return QColor(cls._EDITING_COLOR)
        raise ValueError(f"Unknown icon category: {category}")

    @classmethod
    def _render(cls, path, color):
        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            raise FileNotFoundError(f"Invalid SVG icon: {path}")

        size = QSize(cls.ICON_SIZE, cls.ICON_SIZE)
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), color)
        painter.end()
        return pixmap

    @classmethod
    def icon(cls, name):
        try:
            category, filename = cls._ICONS[name]
        except KeyError as exc:
            raise KeyError(f"Unknown icon: {name}") from exc

        path = cls._ROOT / category / filename
        color = cls._color_for_category(category)

        normal = cls._render(path, color)
        if name == "rotate-ccw":
            normal = normal.transformed(QTransform())
            normal = normal.transformed(QTransform(-1, 0, 0, 1, 0, 0))
        disabled_color = QColor(color)
        disabled_color.setAlphaF(cls.DISABLED_OPACITY)
        disabled = cls._render(path, disabled_color)

        icon = QIcon()
        icon.addPixmap(normal, QIcon.Normal, QIcon.Off)
        icon.addPixmap(disabled, QIcon.Disabled, QIcon.Off)
        return icon
