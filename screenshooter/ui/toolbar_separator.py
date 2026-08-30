"""
Модуль: ui/toolbar_separator.py
Описание: Компонент вертикального разделителя для EditorToolbarStrip.
          Представляет собой тонкую линию с горизонтальными и вертикальными
          отступами для визуального разделения тулбаров.
"""

from PyQt5.QtWidgets import QFrame, QHBoxLayout, QWidget

from ..ui.layout_metrics import (
    TOOLBAR_SEPARATOR_LINE_WIDTH,
    TOOLBAR_SEPARATOR_H_MARGIN,
    TOOLBAR_SEPARATOR_V_MARGIN,
)


class ToolbarSeparator(QWidget):
    """Вертикальный разделитель между тулбарами.

    Структура:
        QWidget (обёртка с отступами)
         └── QFrame (тонкая вертикальная линия)

    Отступы:
        - горизонтальные: TOOLBAR_SEPARATOR_H_MARGIN слева и справа
        - вертикальные: TOOLBAR_SEPARATOR_V_MARGIN сверху и снизу
          (линия не тянется на всю высоту панели)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toolbarSeparator")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            TOOLBAR_SEPARATOR_H_MARGIN,
            TOOLBAR_SEPARATOR_V_MARGIN,
            TOOLBAR_SEPARATOR_H_MARGIN,
            TOOLBAR_SEPARATOR_V_MARGIN,
        )
        layout.setSpacing(0)

        self._line = QFrame(self)
        self._line.setObjectName("toolbarSeparatorLine")
        self._line.setFrameShape(QFrame.VLine)
        self._line.setFrameShadow(QFrame.Plain)
        self._line.setFixedWidth(TOOLBAR_SEPARATOR_LINE_WIDTH)
        layout.addWidget(self._line)