"""
Модуль: ui/image_toolbar.py
Описание: Компонент тулбара операций с изображением (QWidget + QToolButton).
"""

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QToolButton, QSizePolicy

from ..ui.layout_metrics import TOOL_BUTTON_WIDTH, TOOLBAR_ICON_SIZE


class ImageToolbar(QWidget):
    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for act in actions:
            btn = QToolButton()
            btn.setDefaultAction(act)
            btn.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setFixedWidth(TOOL_BUTTON_WIDTH)
            btn.setCheckable(act.isCheckable())
            layout.addWidget(btn)