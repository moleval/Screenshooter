"""
Модуль: items/text_item.py
Описание: Текстовые элементы.
          TextItem — обычный текст с возможностью редактирования и фоновой подложкой.
          DimensionTextItem — текст размерной линии (устаревший, не используется в новой логике,
                               оставлен для совместимости).
"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath
from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsItem
from ..constants import HIT_AREA_PADDING


class TextItem(QGraphicsTextItem):
    """
    Текстовый элемент с возможностью редактирования.
    Поддерживает фон (белый/чёрный/прозрачный).
    При пустом тексте и потере фокуса удаляется автоматически.
    """

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
        """
        Включает/выключает режим редактирования текста.
        """
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
        # Отключаем контекстное меню для простоты
        event.accept()
        return

    def keyPressEvent(self, event):
        # Ctrl+Enter завершает редактирование
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            if event.modifiers() & Qt.ControlModifier:
                self.clearFocus()
                event.accept()
                return
            super().keyPressEvent(event)
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        """
        При потере фокуса:
        - Если текст пустой — удаляем элемент.
        - Если не пустой — завершаем редактирование и оставляем выделенным.
        """
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)

        # Проверка на пустой текст
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
        """Удаляет элемент со сцены и уведомляет view."""
        if self.scene():
            self.scene().removeItem(self)
        if self.view:
            self.view._remove_empty_text(self)
        self._deleting = False

    def paint(self, painter, option, widget):
        """
        Отрисовывает фон (если задан) и сам текст.
        """
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
        """
        Расширяет область захвата для удобства выделения.
        """
        path = QPainterPath()
        path.addRect(self.boundingRect().adjusted(
            -HIT_AREA_PADDING, -HIT_AREA_PADDING, HIT_AREA_PADDING, HIT_AREA_PADDING
        ))
        return path


class DimensionTextItem(QGraphicsTextItem):
    """
    Устаревший класс для текста размерной линии.
    Оставлен для обратной совместимости, но не используется в текущей логике.
    """
    def __init__(self, parent_item, text, *args, **kwargs):
        super().__init__(text, *args, **kwargs)
        self.parent_dimension = parent_item
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
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
        cursor = self.textCursor()
        cursor.select(cursor.Document)
        self.setTextCursor(cursor)

    def mousePressEvent(self, event):
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
            self.parent_dimension.update_text_position(self)

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
                self.parent_dimension.update_text_position(self)
            event.accept()
            return
        super().keyPressEvent(event)