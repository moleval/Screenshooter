"""
Модуль: widgets/mode_widgets.py
Описание: Плавающие тулбары выбора подрежимов инструментов.
          Реализованы виджеты для прямоугольника, эллипса, стрелки и линии.
          Все стили задаются локально и не зависят от глобальной темы.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QPushButton, QButtonGroup,
                             QSizePolicy, QLabel, QSlider)
from .tool_icons import (create_shape_mode_icon, create_ellipse_mode_icon,
                         create_arrow_mode_icon, create_line_mode_icon)


class BaseModeWidget(QFrame):
    modeChanged = pyqtSignal(str)
    BG_COLOR = "rgba(200,200,200,100)"
    BORDER_RADIUS = 12
    BORDER_COLOR = "rgba(80,80,80,180)"
    PADDING = 3
    BUTTON_SIZE = 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            f"QFrame {{ background-color: {self.BG_COLOR}; border-radius: {self.BORDER_RADIUS}px; "
            f"border: 2px solid {self.BORDER_COLOR}; padding: {self.PADDING}px; }}")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(self.PADDING, self.PADDING, self.PADDING, self.PADDING)
        self.layout.setSpacing(8)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._current_mode = None

    def _add_button(self, icon, tooltip, mode):
        button = QPushButton()
        button.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        button.setIcon(icon)
        button.setCheckable(True)
        button.setToolTip(tooltip)
        button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 20);
            }
            QPushButton:checked {
                background-color: #b0d4f1;
                border: 2px solid #005a9e;
                border-radius: 4px;
            }
        """)
        button.clicked.connect(lambda: self._set_mode(mode))
        self.layout.addWidget(button)
        self.button_group.addButton(button)
        return button

    def _set_mode(self, mode):
        self._current_mode = mode
        self.modeChanged.emit(mode)

    def set_current_mode(self, mode):
        pass

    def get_mode(self):
        return self._current_mode


class ShapeModeWidget(BaseModeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rect_btn = self._add_button(create_shape_mode_icon('rect'), "Прямоугольник", 'rect')
        self.square_btn = self._add_button(create_shape_mode_icon('square'), "Квадрат", 'square')
        self.filled_btn = self._add_button(create_shape_mode_icon('filled'), "Поле (заливка)", 'filled')
        self._current_mode = 'rect'
        self.rect_btn.setChecked(True)
        self.setFixedSize(self.sizeHint())

    def set_current_mode(self, mode):
        self._current_mode = mode
        self.rect_btn.setChecked(mode == 'rect')
        self.square_btn.setChecked(mode == 'square')
        self.filled_btn.setChecked(mode == 'filled')


class ShapeModeWidgetEllipse(BaseModeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ellipse_btn = self._add_button(create_ellipse_mode_icon('ellipse'), "Эллипс", 'ellipse')
        self.circle_btn = self._add_button(create_ellipse_mode_icon('circle'), "Круг", 'circle')
        self.cloud_btn = self._add_button(create_ellipse_mode_icon('cloud'), "Пометочное облако", 'cloud')
        self._current_mode = 'ellipse'
        self.ellipse_btn.setChecked(True)
        self.setFixedSize(self.sizeHint())

    def set_current_mode(self, mode):
        self._current_mode = mode
        self.ellipse_btn.setChecked(mode == 'ellipse')
        self.circle_btn.setChecked(mode == 'circle')
        self.cloud_btn.setChecked(mode == 'cloud')


class ShapeModeWidgetArrow(BaseModeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.straight_btn = self._add_button(create_arrow_mode_icon('straight'), "Прямая стрелка", 'straight')
        self.curved_btn = self._add_button(create_arrow_mode_icon('curved'), "Изогнутая стрелка", 'curved')
        self.dimension_btn = self._add_button(create_arrow_mode_icon('dimension'), "Размер с текстом", 'dimension')
        self._current_mode = 'straight'
        self.straight_btn.setChecked(True)
        self.setFixedSize(self.sizeHint())

    def set_current_mode(self, mode):
        self._current_mode = mode
        self.straight_btn.setChecked(mode == 'straight')
        self.curved_btn.setChecked(mode == 'curved')
        self.dimension_btn.setChecked(mode == 'dimension')


class LineModeWidget(BaseModeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.straight_btn = self._add_button(create_line_mode_icon('straight'), "Прямая линия", 'straight')
        self.dashed_btn = self._add_button(create_line_mode_icon('dashed'), "Пунктирная линия", 'dashed')
        self.wavy_btn = self._add_button(create_line_mode_icon('wavy'), "Волнистая линия", 'wavy')
        self._current_mode = 'straight'
        self.straight_btn.setChecked(True)
        self.setFixedSize(self.sizeHint())

    def set_current_mode(self, mode):
        self._current_mode = mode
        self.straight_btn.setChecked(mode == 'straight')
        self.dashed_btn.setChecked(mode == 'dashed')
        self.wavy_btn.setChecked(mode == 'wavy')


class LayerModeWidget(BaseModeWidget):
    """Две кнопки выбора слоя для изображения/размытия."""

    layerChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layer1_btn = self._add_button(
            QIcon(), "Слой 1 — выше слоя 2", 1)
        self.layer2_btn = self._add_button(
            QIcon(), "Слой 2 — ниже слоя 1", 2)
        self.layer1_btn.setText("1")
        self.layer2_btn.setText("2")
        self.layer1_btn.setStyleSheet(self._button_style())
        self.layer2_btn.setStyleSheet(self._button_style())
        self._current_mode = 1
        self.layer1_btn.setChecked(True)
        self.setFixedSize(self.sizeHint())

    @staticmethod
    def _button_style():
        return """
            QPushButton {
                background-color: transparent;
                border: none;
                font-weight: normal;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 20);
            }
            QPushButton:checked {
                background-color: #b0d4f1;
                border: 2px solid #005a9e;
                border-radius: 4px;
            }
        """

    def _set_mode(self, mode):
        self._current_mode = 1 if int(mode) == 1 else 2
        self.layerChanged.emit(self._current_mode)

    def set_current_mode(self, mode):
        mode = 1 if int(mode) == 1 else 2
        self._current_mode = mode
        self.layer1_btn.setChecked(mode == 1)
        self.layer2_btn.setChecked(mode == 2)

    def get_mode(self):
        return self._current_mode


class ImageOpacityWidget(QFrame):
    """Ползунок прозрачности только для выбранных вставленных изображений."""

    opacityChanged = pyqtSignal(int)
    editingFinished = pyqtSignal()

    BG_COLOR = "rgba(200,200,200,100)"
    BORDER_RADIUS = 12
    BORDER_COLOR = "rgba(80,80,80,180)"
    BORDER_WIDTH = 2
    HEIGHT = 38

    def __init__(self, parent=None, width=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            f"QFrame {{ background-color: {self.BG_COLOR}; "
            f"border-radius: {self.BORDER_RADIUS}px; "
            f"border: {self.BORDER_WIDTH}px solid {self.BORDER_COLOR}; "
            f"padding: 3px; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(4)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(10)
        self.slider.setCursor(Qt.ArrowCursor)

        self.value_label = QLabel("100%")
        self.value_label.setFixedWidth(36)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setStyleSheet(
            "QLabel { background: transparent; border: none; }"
        )

        layout.addWidget(self.slider, 1)
        layout.setStretch(0, 1)
        layout.setStretch(1, 0)
        layout.addWidget(self.value_label)

        self.slider.valueChanged.connect(self._on_value_changed)
        self.slider.sliderReleased.connect(self.editingFinished.emit)

        self.set_opacity(100)

        if width is not None:
            self.setFixedWidth(int(width))
        else:
            self.setFixedWidth(72)
        self.setFixedHeight(self.HEIGHT)

    def _on_value_changed(self, value):
        self.value_label.setText(f"{value}%")
        self.opacityChanged.emit(int(value))

    def set_opacity(self, value):
        value = max(0, min(100, int(value)))
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self.value_label.setText(f"{value}%")

    def get_opacity(self):
        return self.slider.value()
