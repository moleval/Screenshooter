"""
Модуль: widgets/info_widget.py
Описание: Плавающий информационный виджет.
          Отображает текущий цвет (круглый индикатор) и толщину линии.
          Общий стиль задаётся глобально, динамически меняется только цвет индикатора.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy
from PyQt5.QtGui import QFont


class InfoWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setAutoFillBackground(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        self.color_label = QLabel()
        self.color_label.setFixedSize(22, 22)
        layout.addWidget(self.color_label)

        self.thickness_label = QLabel("x2")
        self.thickness_label.setAlignment(Qt.AlignCenter)
        self.thickness_label.setFont(QFont("Arial", 9))
        self.thickness_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.thickness_label.setMinimumWidth(28)
        layout.addWidget(self.thickness_label)

        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.adjustSize()

    def set_info(self, color, thickness):
        # Динамически обновляем только цвет индикатора
        self.color_label.setStyleSheet(
            f"border-radius: 11px; border: 1px solid #888; background-color: {color.name()};"
        )
        self.thickness_label.setText(f"x{thickness}")
        self.adjustSize()