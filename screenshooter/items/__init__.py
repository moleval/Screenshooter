"""
Модуль: items/__init__.py
Описание: Пакет графических элементов аннотаций.
          Реэкспортирует классы текстовых элементов, фигур, линий, стрелок,
          вставленных изображений и зон размытия для удобного импорта.
"""

from .text_item import TextItem, DimensionTextItem
from .shape_items import RectangleItem, EllipseItem, FilledRectItem, CloudItem
from .line_items import LineItem, WavyLineItem
from .arrow_items import ArrowItem, CurvedArrowItem, DimensionItem
from .pasted_image_item import PastedImageItem        # <-- ДОБАВЛЕНО
from .blur_region_item import BlurRegionItem          # <-- ДОБАВЛЕНО