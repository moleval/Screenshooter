"""
Модуль: widgets/text_format_widget.py
Описание: Плавающий тулбар выбора фона текста.
          Позволяет переключать фон текста: белый, чёрный или без фона.
          Стили задаются глобально через ThemeManager.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QPushButton, QButtonGroup


class TextFormatWidget(QFrame):
    bgChanged = pyqtSignal(object)  # None, 'white', 'black'

    PADDING = 3
    BUTTON_SIZE = 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setAutoFillBackground(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(self.PADDING, self.PADDING, self.PADDING, self.PADDING)
        layout.setSpacing(6)

        self.bg_white_btn = QPushButton()
        self.bg_white_btn.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.bg_white_btn.setCheckable(True)
        self.bg_white_btn.setToolTip("Белый фон")
        self.bg_white_btn.clicked.connect(lambda: self._set_bg('white'))

        self.bg_black_btn = QPushButton()
        self.bg_black_btn.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.bg_black_btn.setCheckable(True)
        self.bg_black_btn.setToolTip("Чёрный фон")
        self.bg_black_btn.clicked.connect(lambda: self._set_bg('black'))

        self.bg_none_btn = QPushButton()
        self.bg_none_btn.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.bg_none_btn.setCheckable(True)
        self.bg_none_btn.setToolTip("Без фона")
        self.bg_none_btn.setText("×")
        self.bg_none_btn.clicked.connect(lambda: self._set_bg(None))

        layout.addWidget(self.bg_white_btn)
        layout.addWidget(self.bg_black_btn)
        layout.addWidget(self.bg_none_btn)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.button_group.addButton(self.bg_white_btn)
        self.button_group.addButton(self.bg_black_btn)
        self.button_group.addButton(self.bg_none_btn)

        self._current_bg = None
        self.setFixedSize(self.sizeHint())

    def _set_bg(self, mode):
        self._current_bg = mode
        self.bgChanged.emit(mode)

    def set_current_bg(self, mode):
        self._current_bg = mode
        self.bg_white_btn.setChecked(mode == 'white')
        self.bg_black_btn.setChecked(mode == 'black')
        self.bg_none_btn.setChecked(mode is None)