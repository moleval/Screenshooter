# screenshooter/ui/options_toolbar.py
"""
Модуль: ui/options_toolbar.py
Описание: Компонент тулбара опций (толщина и палитра).
          Содержит двухрядную компоновку из ThicknessWidget и ColorPaletteWidget.
          Не содержит бизнес-логики, только представление.
"""

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import (QHBoxLayout, QSizePolicy, QToolBar, QVBoxLayout,
                             QWidget)

from ..ui.layout_metrics import TOOLBAR_ICON_SIZE


class OptionsToolbar(QToolBar):
    """Тулбар с настройками толщины и цвета."""

    def __init__(self, thickness_widget, color_palette_widget, parent=None):
        super().__init__("Опции аннотаций", parent)
        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.setContentsMargins(0, 0, 0, 0)

        # Временное сохранение текущей структуры: два горизонтальных ряда
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.addWidget(thickness_widget)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.addWidget(color_palette_widget)
        layout.addLayout(row2)

        self.addWidget(container)