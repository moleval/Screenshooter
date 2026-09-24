"""Локальный менеджер SVG-иконок интерфейса.

SVG-файлы используют stroke="currentColor". Цвет задаётся при построении
QIcon, поэтому один и тот же набор SVG работает для светлой/тёмной темы.
"""

from pathlib import Path

from PyQt5.QtCore import QByteArray, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer

from ..theme import theme_manager


class IconManager:
    """Загружает локальные Lucide SVG и применяет семантический цвет."""

    ICON_SIZE = 28
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
        "blur": (EDITING, "scan-eye.svg"),
        "trim": (EDITING, "scan.svg"),
        "rotate-cw": (EDITING, "rotate-cw.svg"),
        "rotate-ccw": (EDITING, "rotate-cw.svg"),
        "undo": (EDITING, "undo-2.svg"),
        "redo": (EDITING, "redo-2.svg"),
    }

    _SELECTION_COLOR = QColor("#333333")
    _ANNOTATION_COLOR = QColor("#D25145")
    _EDITING_COLOR = QColor("#005A9E")
    _EDITING_COLOR_DARK = QColor("#D7F5FF")

    @classmethod
    def _color_for_category(cls, category):
        if category == cls.SELECTION:
            return theme_manager.get_color("text")
        if category == cls.ANNOTATION:
            return QColor(cls._ANNOTATION_COLOR)
        if category == cls.EDITING:
            color = (
                cls._EDITING_COLOR_DARK
                if theme_manager.effective_theme == "dark"
                else cls._EDITING_COLOR
            )
            return QColor(color)
        raise ValueError(f"Unknown icon category: {category}")

    @classmethod
    def _render(cls, path, color):
        svg = path.read_text(encoding="utf-8")
        opacity = color.alphaF()
        render_color = QColor(color)
        render_color.setAlpha(255)
        svg = svg.replace("currentColor", render_color.name(QColor.HexRgb))

        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        if not renderer.isValid():
            raise FileNotFoundError(f"Invalid SVG icon: {path}")

        size = QSize(cls.ICON_SIZE, cls.ICON_SIZE)
        image = QImage(size, QImage.Format_ARGB32)
        image.fill(Qt.transparent)

        painter = QPainter(image)
        renderer.render(painter)
        painter.end()

        if opacity < 1.0:
            for y in range(image.height()):
                for x in range(image.width()):
                    pixel = image.pixelColor(x, y)
                    alpha = round(pixel.alpha() * opacity)
                    pixel.setAlpha(alpha)
                    image.setPixelColor(x, y, pixel)

        return QPixmap.fromImage(image)

    @classmethod
    def icon(cls, name):
        try:
            category, filename = cls._ICONS[name]
        except KeyError as exc:
            raise KeyError(f"Unknown icon: {name}") from exc

        path = cls._ROOT / category / filename
        color = cls._color_for_category(category)

        normal = cls._render(path, color)
        disabled_color = QColor(color)
        disabled_color.setAlpha(round(255 * cls.DISABLED_OPACITY))
        disabled = cls._render(path, disabled_color)

        if name == "rotate-ccw":
            normal = QPixmap.fromImage(normal.toImage().mirrored(True, False))
            disabled = QPixmap.fromImage(disabled.toImage().mirrored(True, False))

        icon = QIcon()
        icon.addPixmap(normal, QIcon.Normal, QIcon.Off)
        icon.addPixmap(disabled, QIcon.Disabled, QIcon.Off)
        return icon
