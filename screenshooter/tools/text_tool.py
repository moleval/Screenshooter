"""
Модуль: tools/text_tool.py
Описание: Инструмент для создания текстовых аннотаций.
          Одиночный клик по свободному полю завершает редактирование активного текста.
          Двойной клик по свободному полю создаёт новый текст.
          Клик по существующему тексту активирует его редактирование.
"""

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QFont, QColor

from .base_tool import BaseTool
from ..items import TextItem


class TextTool(BaseTool):
    def __init__(self, view):
        super().__init__(view)

    def start_draw(self, scene_pos: QPointF):
        """Создаёт новый текст (используется по двойному клику)."""
        if self.view.active_text_item:
            self.view.active_text_item.setEditable(False)
            self.view.active_text_item = None

        ti = TextItem(self.view, bg_color=self.view.current_text_bg)
        # Жёлтый цвет, как жёлтый на палитре
        ti.setDefaultTextColor(QColor("#F9D556"))
        font = QFont()
        font.setPointSize(self.view.text_size * 4)
        ti.setFont(font)
        ti.setPos(scene_pos)

        self.view.active_text_item = ti
        ti.setSelected(True)
        ti.setEditable(True)
        self.view._first_click_after_activation = False
        return ti

    def update_draw(self, temp_item, scene_pos, modifiers):
        pass  # не требуется

    def finish_draw(self, temp_item) -> bool:
        return True  # не требуется

    def handle_double_click(self, scene_pos: QPointF):
        """Обрабатывает двойной клик: если клик на тексте – активирует его, иначе создаёт новый."""
        item = self.view.scene().itemAt(scene_pos, self.view.transform())
        if isinstance(item, TextItem):
            if self.view.active_text_item is not None and self.view.active_text_item is not item:
                self.view.active_text_item.setEditable(False)
            self.view.active_text_item = item
            item.setEditable(True)
            if self.view.current_tool == 'text':
                self.view._first_click_after_activation = False
            return True
        else:
            # Двойной клик по свободному полю – создаём новый текст
            ti = self.start_draw(scene_pos)
            if ti:
                self.view.scene().addItem(ti)
                self.view.active_text_item = ti
                ti.setSelected(True)
                ti.setEditable(True)
                self.view._first_click_after_activation = False
                from ..history import AddItemCommand
                self.view.history.push(AddItemCommand(self.view.scene(), ti))
                return True
            return False