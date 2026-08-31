"""
Модуль: ui/annotation_toolbar.py
Описание: Компонент тулбара аннотаций (QWidget + QToolButton).
"""

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QToolButton, QSizePolicy

from ..ui.layout_metrics import TOOLBAR_ICON_SIZE


class AnnotationToolbar(QWidget):
    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        buttons = []
        for act in actions:
            btn = QToolButton()
            btn.setDefaultAction(act)
            btn.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setCheckable(act.isCheckable())
            layout.addWidget(btn)
            buttons.append(btn)

        # Ширина вычисляется по sizeHint, который зависит от текущего шрифта.
        # Убедитесь, что тема применена до создания тулбара.
        max_width = max(btn.sizeHint().width() for btn in buttons)
        for btn in buttons:
            btn.setFixedWidth(max_width)