"""Супер-пипетка: выбор исходного цвета с любого подключённого экрана."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QGuiApplication
from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget,
)

from .icon_manager import IconManager


class ScreenColorPicker(QWidget):
    """Прозрачный overlay над виртуальным рабочим столом."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self._captures = []
        self._press_pos = None

    def start(self):
        self._captures = []
        for screen in QGuiApplication.screens():
            pixmap = screen.grabWindow(0)
            self._captures.append((screen.geometry(), pixmap))
        virtual = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virtual)
        self.show()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event):
        # Прозрачный overlay намеренно ничего не рисует.
        return

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            self.close()
            return
        global_pos = event.globalPos()
        color = self._sample_global(global_pos)
        self.close()
        if color.isValid():
            self.colorPicked(color, global_pos)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def _sample_global(self, point):
        for geometry, pixmap in self._captures:
            if not geometry.contains(point) or pixmap.isNull():
                continue
            image = pixmap.toImage()
            x = round(
                (point.x() - geometry.left())
                * image.width() / max(geometry.width(), 1)
            )
            y = round(
                (point.y() - geometry.top())
                * image.height() / max(geometry.height(), 1)
            )
            x = max(0, min(image.width() - 1, x))
            y = max(0, min(image.height() - 1, y))
            return image.pixelColor(x, y)
        return QColor()

    def colorPicked(self, color, global_pos):
        """Переопределяется владельцем; оставлено методом вместо сигнала."""


class ColorResultPopup(QWidget):
    """Небольшое окно результатов с отдельной кнопкой копирования."""

    def __init__(self, color, global_pos, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        preview = QLabel()
        preview.setFixedSize(34, 34)
        preview.setStyleSheet(
            "border: 1px solid palette(mid); border-radius: 4px;"
            f"background: {self.color.name(QColor.HexRgb)};"
        )
        header = QHBoxLayout()
        header.addWidget(preview)
        header.addWidget(QLabel("Цвет с экрана"))
        header.addStretch()
        layout.addLayout(header)

        for name, value in self._formats().items():
            self._add_row(layout, name, value)

        self.status = QLabel("")
        self.status.setMinimumHeight(18)
        layout.addWidget(self.status)

        self.adjustSize()
        self._move_near(global_pos)

    def _formats(self):
        r, g, b, a = (
            self.color.red(), self.color.green(),
            self.color.blue(), self.color.alpha(),
        )
        h = self.color.hsvHue()
        h = 0 if h < 0 else h
        s = self.color.hsvSaturation()
        v = self.color.value()
        sl = self.color.hslSaturation()
        l = self.color.lightness()
        c = self.color.cyan()
        m = self.color.magenta()
        y = self.color.yellow()
        k = self.color.black()
        return {
            "HEX": self.color.name(QColor.HexRgb).upper(),
            "RGB": f"rgb({r}, {g}, {b})",
            "RGBA": f"rgba({r}, {g}, {b}, {a})",
            "HSL": f"hsl({h}, {sl}%, {l}%)",
            "HSV": f"hsv({h}, {s}%, {v}%)",
            "CMYK": f"cmyk({c}%, {m}%, {y}%, {k}%)",
        }

    def _add_row(self, layout, name, value):
        row = QHBoxLayout()
        label = QLabel(name)
        label.setFixedWidth(48)
        value_label = QLabel(value)
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        copy_btn = QToolButton()
        copy_btn.setIcon(IconManager.icon("clipboard-copy", size=16))
        copy_btn.setToolTip("Копировать")
        copy_btn.setFixedSize(24, 24)
        copy_btn.clicked.connect(
            lambda checked=False, text=value: self._copy_value(text)
        )
        row.addWidget(label)
        row.addWidget(value_label, 1)
        row.addWidget(copy_btn)
        layout.addLayout(row)

    def _copy_value(self, value):
        QApplication.clipboard().setText(value)
        self.status.setText("Скопировано")

    def _move_near(self, global_pos):
        screen = QGuiApplication.screenAt(global_pos)
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        pos = global_pos + self._offset()
        x = min(max(pos.x(), area.left()), area.right() - self.width())
        y = min(max(pos.y(), area.top()), area.bottom() - self.height())
        self.move(x, y)

    @staticmethod
    def _offset():
        from PyQt5.QtCore import QPoint
        return QPoint(14, 14)


class SuperEyedropper:
    """Координатор: экранный выбор → результат → выбор цвета в редакторе."""

    def __init__(self, parent=None, color_callback=None):
        self.parent = parent
        self.color_callback = color_callback
        self._picker = None
        self._popup = None

    def start(self):
        self._picker = ScreenColorPicker(self.parent)
        self._picker.colorPicked = self._picked
        self._picker.start()

    def _picked(self, color, global_pos):
        self._picker = None
        self._popup = ColorResultPopup(color, global_pos, self.parent)
        self._popup.show()
        if self.color_callback is not None:
            self.color_callback(color, global_pos)
        return color
