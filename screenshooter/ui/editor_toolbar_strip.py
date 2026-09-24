"""Модуль: ui/editor_toolbar_strip.py — контейнерная панель инструментов."""

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QToolButton, QSizePolicy

from .toolbar_separator import ToolbarSeparator
from .layout_metrics import TOOLBAR_BUTTON_SIZE, TOOLBAR_ICON_SIZE


class EditorToolbarStrip(QWidget):
    """Плоская панель инструментов редактора."""

    def __init__(self, annotation_toolbar, image_toolbar, options_toolbar,
                 trim_action=None, parent=None):
        super().__init__(parent)
        self.setObjectName("editorToolbarStrip")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(annotation_toolbar)
        layout.addWidget(ToolbarSeparator())
        layout.addWidget(image_toolbar)
        layout.addWidget(ToolbarSeparator())

        self.trim_button = None
        if trim_action is not None:
            self.trim_button = QToolButton()
            self.trim_button.setDefaultAction(trim_action)
            self.trim_button.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
            self.trim_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            self.trim_button.setFixedSize(TOOLBAR_BUTTON_SIZE, TOOLBAR_BUTTON_SIZE)
            self.trim_button.setCheckable(False)
            layout.addWidget(self.trim_button)

        layout.addStretch(1)
        layout.addWidget(options_toolbar)
