"""
Модуль: widgets/thickness.py
Описание: Виджеты управления толщиной линии.
          Содержит ThicknessSlider и ThicknessWidget с пресетами,
          слайдером и полем ввода.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QSlider,
                             QLineEdit, QToolTip, QInputDialog, QSizePolicy)
from PyQt5.QtGui import QFont
from ..utils import SelectAllLineEdit


class ThicknessSlider(QSlider):
    customEditRequested = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.customEditRequested.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.customEditRequested.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def enterEvent(self, event):
        QToolTip.showText(self.mapToGlobal(self.rect().center()), str(self.value()), self)
        super().enterEvent(event)

    def mouseMoveEvent(self, event):
        QToolTip.showText(event.globalPos(), str(self.value()), self)
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        if self.underMouse():
            delta = event.angleDelta().y()
            self.setValue(self.value() + (1 if delta > 0 else -1))
            event.accept()
        else:
            super().wheelEvent(event)


class ThicknessWidget(QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Важно: Expanding, чтобы заполнять доступную ширину в OptionsToolbar
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Кнопки пресетов
        self.preset_buttons = []
        presets = [1, 2, 5, 10, 20]
        for value in presets:
            button = QPushButton(f"x{value}")
            button.setMinimumHeight(24)
            button.setFont(QFont("Arial", 8))
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
            button.setStyleSheet("padding: 2px 4px;")
            button.clicked.connect(lambda _, v=value: self._set_value(v))
            layout.addWidget(button)
            self.preset_buttons.append(button)

        # Слайдер
        self.slider = ThicknessSlider(Qt.Horizontal)
        self.slider.setRange(1, 100)
        self.slider.setValue(3)
        self.slider.setFixedHeight(26)
        self.slider.setMinimumWidth(80)          # минимальная ширина для удобства
        # Ограничение максимальной ширины не задаём — слайдер должен расширяться
        self.slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.slider.customEditRequested.connect(self._open_value_dialog)
        layout.addWidget(self.slider)

        # Поле ручного ввода
        self.value_edit = SelectAllLineEdit("3")
        self.value_edit.setFixedSize(32, 32)
        self.value_edit.setAlignment(Qt.AlignCenter)
        self.value_edit.setFont(QFont("Arial", 10))
        self.value_edit.returnPressed.connect(self._on_edit)
        layout.addWidget(self.value_edit)

        self._value = 3
        self._update_preset_highlight(3)

    def set_value_silent(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self._value = value
        self.value_edit.setText(str(value))
        self._update_preset_highlight(value)

    def _set_value(self, value):
        self.slider.setValue(value)
        self._value = value
        self.value_edit.setText(str(value))
        self._update_preset_highlight(value)
        self.valueChanged.emit(value)

    def _on_slider_changed(self, value):
        self._value = value
        self.value_edit.setText(str(value))
        self._update_preset_highlight(value)
        self.valueChanged.emit(value)

    def _on_edit(self):
        try:
            value = int(self.value_edit.text())
        except ValueError:
            value = self._value
        if 1 <= value <= 100:
            self.slider.setValue(value)
            self._value = value
            self._update_preset_highlight(value)
            self.valueChanged.emit(value)
        else:
            self.value_edit.setText(str(self._value))

    def _open_value_dialog(self):
        value, ok = QInputDialog.getInt(self, "Толщина линии", "Введите значение (1–100):",
                                        self._value, 1, 100, 1)
        if ok:
            self._set_value(value)

    def _update_preset_highlight(self, value):
        presets = [1, 2, 5, 10, 20]
        for button, preset in zip(self.preset_buttons, presets):
            button.setChecked(value == preset)