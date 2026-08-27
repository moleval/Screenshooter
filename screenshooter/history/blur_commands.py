"""
Модуль: history/blur_commands.py
Описание: Команды для зон размытия.
          Добавление, удаление, перемещение, изменение размера.
"""

from PyQt5.QtWidgets import QUndoCommand


class AddBlurRegionCommand(QUndoCommand):
    """Добавление новой зоны размытия."""

    def __init__(self, controller, rect):
        super().__init__("Добавить зону размытия")
        self.controller = controller
        self.rect = rect

    def redo(self):
        self.controller._add_blur_region_internal(self.rect)

    def undo(self):
        self.controller._remove_last_blur_region()


class RemoveBlurRegionCommand(QUndoCommand):
    """Удаление зоны размытия по индексу."""

    def __init__(self, controller, index):
        super().__init__("Удалить зону размытия")
        self.controller = controller
        self.index = index
        self.rect = None

    def redo(self):
        self.rect = self.controller._remove_blur_region_at(self.index)

    def undo(self):
        if self.rect is not None:
            self.controller._insert_blur_region_at(self.index, self.rect)
            self.controller._set_active_blur(self.index)


class MoveBlurRegionCommand(QUndoCommand):
    """Перемещение зоны размытия."""

    def __init__(self, controller, index, old_rect, new_rect):
        super().__init__("Переместить зону размытия")
        self.controller = controller
        self.index = index
        self.old_rect = old_rect
        self.new_rect = new_rect

    def redo(self):
        self.controller._update_blur_region_rect(self.index, self.new_rect)

    def undo(self):
        self.controller._update_blur_region_rect(self.index, self.old_rect)


class ResizeBlurRegionCommand(QUndoCommand):
    """Изменение размера зоны размытия."""

    def __init__(self, controller, index, old_rect, new_rect):
        super().__init__("Изменить размер зоны размытия")
        self.controller = controller
        self.index = index
        self.old_rect = old_rect
        self.new_rect = new_rect

    def redo(self):
        self.controller._update_blur_region_rect(self.index, self.new_rect)

    def undo(self):
        self.controller._update_blur_region_rect(self.index, self.old_rect)