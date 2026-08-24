"""
Модуль: tools/base_tool.py
Описание: Базовый класс для всех инструментов рисования.
          Определяет интерфейс для создания и обновления временных элементов.
"""

from PyQt5.QtCore import QPointF


class BaseTool:
    def __init__(self, view):
        self.view = view

    def start_draw(self, scene_pos: QPointF):
        """
        Начать рисование: создать временный элемент и вернуть его.
        """
        raise NotImplementedError

    def update_draw(self, temp_item, scene_pos: QPointF, modifiers):
        """
        Обновить геометрию временного элемента в процессе рисования.
        """
        raise NotImplementedError

    def finish_draw(self, temp_item) -> bool:
        """
        Проверить, достаточно ли велик элемент, чтобы его сохранить.
        Возвращает True, если элемент следует добавить в сцену, иначе False.
        """
        raise NotImplementedError