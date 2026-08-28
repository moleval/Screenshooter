"""
Модуль: widgets/zoom_widget.py
Описание: Виджет управления масштабом.
          Содержит кнопки вписать, увеличения/уменьшения, слайдер и поле ввода.
          Все стили задаются глобально через ThemeManager.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSlider
from PyQt5.QtGui import QFont
from ..utils import SelectAllLineEdit


class ZoomSlider(QSlider):
    def wheelEvent(self, event):
        if self.underMouse():
            delta = event.angleDelta().y()
            step = 5
            self.setValue(self.value() + (step if delta > 0 else -step))
            event.accept()
        else:
            super().wheelEvent(event)


class ZoomWidget(QWidget):
    zoomChanged = pyqtSignal(int)
    fitRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 6)
        layout.setSpacing(2)

        self.fit_btn = QPushButton("⤢")
        self.fit_btn.setFixedSize(28, 24)
        self.fit_btn.setToolTip("Вписать всё изображение в окно")
        self.fit_btn.clicked.connect(self.fitRequested.emit)
        layout.addWidget(self.fit_btn)

        self.minus_btn = QPushButton("−")
        self.minus_btn.setFixedSize(28, 24)
        self.minus_btn.clicked.connect(self._zoom_out)
        layout.addWidget(self.minus_btn)

        self.slider = ZoomSlider(Qt.Horizontal)
        self.slider.setRange(10, 400)
        self.slider.setValue(100)
        self.slider.setFixedWidth(100)
        self.slider.setFixedHeight(24)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

        self.plus_btn = QPushButton("+")
        self.plus_btn.setFixedSize(28, 24)
        self.plus_btn.clicked.connect(self._zoom_in)
        layout.addWidget(self.plus_btn)

        self.percent_edit = SelectAllLineEdit()
        self.percent_edit.setFixedSize(42, 24)
        self.percent_edit.setFont(QFont("Arial", 9))
        self.percent_edit.setText("100%")
        self.percent_edit.setAlignment(Qt.AlignCenter)
        self.percent_edit.returnPressed.connect(self._on_edit)
        layout.addWidget(self.percent_edit)

        self._current_zoom = 100
        self.setFixedSize(self.sizeHint())

    def _on_slider_changed(self, value):
        self.percent_edit.setText(f"{value}%")
        self.zoomChanged.emit(value)

    def _zoom_in(self):
        self.slider.setValue(self.slider.value() + 10)

    def _zoom_out(self):
        self.slider.setValue(self.slider.value() - 10)

    def _on_edit(self):
        text = self.percent_edit.text().replace('%', '')
        try:
            value = int(text)
            if 10 <= value <= 400:
                self.slider.setValue(value)
        except ValueError:
            pass

    def set_zoom(self, percent):
        self.slider.blockSignals(True)
        self.slider.setValue(int(percent))
        self.slider.blockSignals(False)
        self.percent_edit.setText(f"{int(percent)}%")