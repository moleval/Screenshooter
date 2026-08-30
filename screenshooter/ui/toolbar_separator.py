# screenshooter/ui/toolbar_separator.py
"""
Модуль: ui/toolbar_separator.py
Описание: Компонент вертикального разделителя для будущего EditorToolbarStrip.
          Пока используется только как заготовка. Стилизация будет добавлена позже.
"""

from PyQt5.QtWidgets import QFrame


class ToolbarSeparator(QFrame):
    """Вертикальный разделитель между тулбарами."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toolbarSeparator")
        self.setFrameShape(QFrame.VLine)
        self.setFixedWidth(2)