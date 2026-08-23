"""Плавающие тулбары выбора подрежимов инструментов."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QPushButton, QButtonGroup,
                             QSizePolicy, QToolBar)
from .tool_icons import (create_shape_mode_icon, create_ellipse_mode_icon,
                         create_arrow_mode_icon, create_line_mode_icon)


class BaseModeWidget(QFrame):
    """Базовый класс для тулбаров выбора режима."""
    modeChanged = pyqtSignal(str)
    BG_COLOR = "rgba(200,200,200,100)"
    BORDER_RADIUS = 12
    BORDER_COLOR = "rgba(80,80,80,180)"
    PADDING = 3
    BUTTON_SIZE = 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setAutoFillBackground(True)
        self.setStyleSheet(
            f"QFrame {{ background-color: {self.BG_COLOR}; border-radius: {self.BORDER_RADIUS}px; "
            f"border: 2px solid {self.BORDER_COLOR}; padding: {self.PADDING}px; }}")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(self.PADDING, self.PADDING, self.PADDING, self.PADDING)
        self.layout.setSpacing(4)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._current_mode = None

    def _add_button(self, icon, tooltip, mode):
        button = QPushButton()
        button.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        button.setIcon(icon)
        button.setCheckable(True)
        button.setToolTip(tooltip)
        button.clicked.connect(lambda: self._set_mode(mode))
        self.layout.addWidget(button)
        self.button_group.addButton(button)
        return button

    def _set_mode(self, mode):
        self._current_mode = mode
        self.modeChanged.emit(mode)

    def set_current_mode(self, mode):
        self._current_mode = mode
        for button in self.button_group.buttons():
            # Определяем, какой кнопке соответствует режим, можно хранить свойство
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