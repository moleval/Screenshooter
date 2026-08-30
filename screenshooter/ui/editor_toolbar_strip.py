"""
Модуль: ui/editor_toolbar_strip.py
Описание: Контейнерная панель инструментов.
          Объединяет AnnotationToolbar, ImageToolbar и OptionsToolbar
          в плоскую горизонтальную компоновку.
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSizePolicy

from .toolbar_separator import ToolbarSeparator


class EditorToolbarStrip(QWidget):
    """Плоская панель инструментов.

    Геометрия:
      - ширина: Expanding (занимает всю ширину окна);
      - высота: Fixed (определяется самым высоким дочерним элементом).
    """

    def __init__(self, annotation_toolbar, image_toolbar, options_toolbar, parent=None):
        super().__init__(parent)
        self.setObjectName("editorToolbarStrip")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(annotation_toolbar)
        layout.addWidget(ToolbarSeparator())
        layout.addWidget(image_toolbar)
        layout.addStretch(1)
        layout.addWidget(options_toolbar)