"""
Модуль: ui/options_toolbar.py
Описание: Компонент тулбара опций (QWidget).
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy


class OptionsToolbar(QWidget):
    def __init__(self, thickness_widget, color_palette_widget, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        # Левый отступ для компенсации внутреннего padding кнопок ImageToolbar (~12 px)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(2)

        # Ряд толщины: без растяжек, виджет заполняет всю ширину
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.addWidget(thickness_widget)
        layout.addLayout(row1)

        # Ряд палитры: центрируем с помощью растяжек
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.addStretch(1)
        row2.addWidget(color_palette_widget)
        row2.addStretch(1)
        layout.addLayout(row2)