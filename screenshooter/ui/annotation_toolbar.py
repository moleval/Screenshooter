# screenshooter/ui/annotation_toolbar.py
"""
Модуль: ui/annotation_toolbar.py
Описание: Компонент тулбара аннотаций.
          Отображает переданные QAction в виде кнопок с фиксированной шириной.
          Не содержит бизнес-логики, только представление.
"""

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QToolBar

from ..ui.layout_metrics import TOOL_BUTTON_WIDTH, TOOLBAR_ICON_SIZE


class AnnotationToolbar(QToolBar):
    """Тулбар с инструментами аннотаций (6 кнопок)."""

    def __init__(self, actions, parent=None):
        super().__init__("Аннотации", parent)
        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)

        for act in actions:
            self.addAction(act)
            btn = self.widgetForAction(act)
            if btn:
                btn.setFixedWidth(TOOL_BUTTON_WIDTH)