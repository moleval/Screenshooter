"""Текстовые элементы: обычный текст и текст размерной линии."""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath
from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsItem
from ..constants import HIT_AREA_PADDING


class TextItem(QGraphicsTextItem):
    PADDING_LEFT, PADDING_TOP, PADDING_RIGHT, PADDING_BOTTOM = -16, 0, 16, 0

    def __init__(self, view, bg=None, *args, **kwargs):
        if 'bg_color' in kwargs:
            bg = kwargs.pop('bg_color')
        super().__init__(*args, **kwargs)
        self.view = view
        self.bg_color = bg
        self._deleting = False
        self._editable = False
        self.setFlags(QGraphicsTextItem.ItemIsMovable | QGraphicsTextItem.ItemIsSelectable)
        self.setTextInteractionFlags(Qt.NoTextInteraction)

    def setEditable(self, editable):
        if editable == self._editable:
            return
        self._editable = editable
        if editable:
            self.setTextInteractionFlags(Qt.TextEditorInteraction)
            self.setFocus(Qt.MouseFocusReason)
        else:
            self.setTextInteractionFlags(Qt.NoTextInteraction)
            self.clearFocus()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        event.accept()
        return

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            if event.modifiers() & Qt.ControlModifier:
                self.clearFocus()
                event.accept()
                return
            super().keyPressEvent(event)
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        if self.toPlainText().strip() == "":
            if not self._deleting:
                self._deleting = True
                QTimer.singleShot(0, self._delete_self)
        else:
            if self.view:
                self.view._text_editing_finished(self)
            self.setSelected(True)
        super().focusOutEvent(event)

    def _delete_self(self):
        if self.scene():
            self.scene().removeItem(self)
        if self.view:
            self.view._remove_empty_text(self)
        self._deleting = False

    def paint(self, painter, option, widget):
        if self.bg_color is not None:
            rect = self.boundingRect().adjusted(
                self.PADDING_LEFT, self.PADDING_TOP, self.PADDING_RIGHT, self.PADDING_BOTTOM
            )
            painter.save()
            painter.setBrush(self.bg_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 8, 8)
            painter.restore()
        super().paint(painter, option, widget)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.boundingRect().adjusted(
            -HIT_AREA_PADDING, -HIT_AREA_PADDING, HIT_AREA_PADDING, HIT_AREA_PADDING
        ))
        return path


class DimensionTextItem(QGraphicsTextItem):
    def __init__(self, parent_item, text, *args, **kwargs):
        super().__init__(text, *args, **kwargs)
        self.parent_dimension = parent_item
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)   # Разрешаем выделение
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setTextInteractionFlags(Qt.NoTextInteraction)

    def begin_editing(self):
        if self.parent_dimension and self.parent_dimension.scene():
            self.parent_dimension.scene().clearSelection()
            self.parent_dimension.setSelected(True)
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFocus(Qt.MouseFocusReason)
        if self.scene():
            self.scene().setFocusItem(self)

        # Выделяем весь текст, чтобы сразу можно было вводить новое значение
        cursor = self.textCursor()
        cursor.select(cursor.Document)
        self.setTextCursor(cursor)

    def mousePressEvent(self, event):
        # Одиночный клик по тексту запускает редактирование
        if event.button() == Qt.LeftButton and self.textInteractionFlags() == Qt.NoTextInteraction:
            self.begin_editing()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.begin_editing()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        if self.parent_dimension:
            self.parent_dimension.update_text_position()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            if event.modifiers() & Qt.ControlModifier:
                self.clearFocus()
                event.accept()
                return
            cursor = self.textCursor()
            cursor.insertText("\n")
            self.setTextCursor(cursor)
            if self.parent_dimension:
                self.parent_dimension.update_text_position()
            event.accept()
            return
        super().keyPressEvent(event)