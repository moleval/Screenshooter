"""
Модуль: widgets/info_widget.py
Описание: Плавающий информационный виджет.
          Отображает текущий цвет (круглый индикатор) и толщину линии (например, "x2").
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy
from PyQt5.QtGui import QFont


class InfoWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setAutoFillBackground(True)
        self.setStyleSheet(
            "QFrame { background-color: rgba(200,200,200,100); border-radius: 12px; "
            "border: 2px solid rgba(80,80,80,180); padding: 2px; }")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        self.color_label = QLabel()
        self.color_label.setFixedSize(22, 22)
        self.color_label.setStyleSheet(
            "border-radius: 11px; border: 1px solid #888; background-color: #FF0000;")
        layout.addWidget(self.color_label)
        self.thickness_label = QLabel("x2")
        self.thickness_label.setAlignment(Qt.AlignCenter)
        self.thickness_label.setFont(QFont("Arial", 9))
        self.thickness_label.setStyleSheet(
            "QLabel { background-color: rgba(255,255,255,150); border: 2px solid #b0d4f1; "
            "border-radius: 4px; color: #333; padding: 0 4px; }")
        self.thickness_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.thickness_label.setMinimumWidth(28)
        layout.addWidget(self.thickness_label)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.adjustSize()

    def set_info(self, color, thickness):
        self.color_label.setStyleSheet(
            f"border-radius: 11px; border: 1px solid #888; background-color: {color.name()};")
        self.thickness_label.setText(f"x{thickness}")
        self.adjustSize()