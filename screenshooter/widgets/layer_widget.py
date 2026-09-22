"""Виджет выбора слоя для изображений и зон размытия."""

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from ..theme import theme_manager


class LayerWidget(QWidget):
    """Показывает и изменяет пользовательский слой объекта."""

    layerChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False

        self.setObjectName("layerWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(6)

        self.label = QLabel("Слой", self)
        self.combo = QComboBox(self)
        self.combo.addItems(["0", "1", "2"])
        self.combo.setFixedWidth(46)
        self.combo.setCursor(Qt.ArrowCursor)
        self.combo.currentIndexChanged.connect(self._on_changed)

        layout.addWidget(self.label)
        layout.addWidget(self.combo)

        self.setStyleSheet(self._style())
        self.adjustSize()

    def _style(self):
        return (
            "#layerWidget {"
            "background-color: rgba(200,200,200,100);"
            "color: #333;"
            "border-radius: 8px;"
            "border: 1px solid rgba(80,80,80,180);"
            "}"
            "QComboBox {"
            "background-color: rgba(255,255,255,180);"
            "border: 1px solid rgba(80,80,80,120);"
            "border-radius: 4px;"
            "padding: 1px 4px;"
            "}"
        )

    def _on_changed(self, index):
        if self._updating:
            return
        self.layerChanged.emit(index)

    def set_layer(self, layer):
        layer = max(0, min(2, int(layer)))
        self._updating = True
        try:
            self.combo.setCurrentIndex(layer)
        finally:
            self._updating = False

    def layer(self):
        return self.combo.currentIndex()
