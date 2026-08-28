"""
Модуль: widgets/color_palette.py
Описание: Виджет палитры цветов.
          Предоставляет предустановленные цвета и кнопку для выбора
          произвольного цвета через диалог QColorDialog.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QColorDialog,
                             QSizePolicy)
from PyQt5.QtGui import QColor


class ColorPaletteWidget(QWidget):
    colorSelected = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedWidth(360)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addStretch(1)

        self.color_buttons = []
        colors = [
            ("#FFFFFF", "Белый"),
            ("#878787", "Светло-серый"),
            ("#535353", "Тёмно-серый"),   # rgb(83,83,83)
            ("#383635", "Чёрный"),
            ("#D25145", "Красный"),
            ("#FFA500", "Оранжевый"),
            ("#F9D556", "Жёлтый"),
            ("#A3CA41", "Зелёный"),
            ("#417CB9", "Голубой"),
            # Синий удалён
            ("#926DA8", "Фиолетовый"),
        ]

        for color_str, name in colors:
            button = QPushButton()
            button.setFixedSize(26, 26)
            button.setToolTip(name)
            button.setProperty("color_name", color_str)
            button.setStyleSheet(
                f"background-color: {color_str}; border-radius: 13px; border: 1px solid #888;"
            )
            button.clicked.connect(lambda _, c=color_str, b=button: self._on_color_click(c, b))
            layout.addWidget(button)
            self.color_buttons.append(button)

        layout.addStretch(1)

        self.palette_btn = QPushButton("🎨")
        self.palette_btn.setFixedSize(32, 32)
        self.palette_btn.setToolTip("Выбрать цвет...")
        self.palette_btn.clicked.connect(self._open_palette)
        layout.addWidget(self.palette_btn)

        self.selected_button = None

    def _on_color_click(self, color_str, button):
        color = QColor(color_str)
        self._update_selected_button(button)
        self.colorSelected.emit(color)

    def _update_selected_button(self, button):
        if self.selected_button is not None:
            old_color = self.selected_button.property("color_name")
            if old_color:
                self.selected_button.setStyleSheet(
                    f"background-color: {old_color}; border-radius: 13px; border: 1px solid #888;"
                )

        new_color = button.property("color_name")
        if new_color:
            button.setStyleSheet(
                f"background-color: {new_color}; border-radius: 13px; border: 2px solid #005a9e;"
            )
        self.selected_button = button

    def set_current_color(self, color):
        target = color.name().upper()
        for button in self.color_buttons:
            if button.property("color_name") and button.property("color_name").upper() == target:
                self._update_selected_button(button)
                return

        if self.selected_button is not None:
            old_color = self.selected_button.property("color_name")
            if old_color:
                self.selected_button.setStyleSheet(
                    f"background-color: {old_color}; border-radius: 13px; border: 1px solid #888;"
                )
            self.selected_button = None

    def _open_palette(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.colorSelected.emit(color)
            self.set_current_color(color)