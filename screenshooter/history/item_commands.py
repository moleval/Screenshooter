"""
Модуль: history/item_commands.py
Описание: Команды для обычных элементов сцены (аннотаций).
"""

from PyQt5.QtWidgets import QUndoCommand


class AddItemCommand(QUndoCommand):
    """Команда добавления элемента в сцену."""

    def __init__(self, scene, item):
        super().__init__("Добавить объект")
        self.scene = scene
        self.item = item

    def redo(self):
        if self.item.scene() is not self.scene:
            self.scene.addItem(self.item)
        self.item.setVisible(True)

    def undo(self):
        if self.item.scene() is self.scene:
            self.scene.removeItem(self.item)


class RemoveItemCommand(QUndoCommand):
    """Команда удаления элемента из сцены."""

    def __init__(self, scene, item):
        super().__init__("Удалить объект")
        self.scene = scene
        self.item = item

    def redo(self):
        if self.item.scene() is self.scene:
            self.scene.removeItem(self.item)

    def undo(self):
        if self.item.scene() is not self.scene:
            self.scene.addItem(self.item)
        self.item.setVisible(True)


class MoveItemCommand(QUndoCommand):
    """Команда перемещения одного элемента."""

    def __init__(self, item, old_pos, new_pos):
        super().__init__("Переместить объект")
        self.item = item
        self.old_pos = old_pos
        self.new_pos = new_pos

    def redo(self):
        self.item.setPos(self.new_pos)

    def undo(self):
        self.item.setPos(self.old_pos)


class MoveItemsCommand(QUndoCommand):
    """Команда перемещения объектов вместе с изменением подложки."""

    def __init__(self, items, old_positions, new_positions,
                 background_item=None, old_pixmap=None, new_pixmap=None,
                 old_background_pos=None, new_background_pos=None,
                 blur_controller=None, old_blur_state=None, new_blur_state=None):
        super().__init__("Переместить объекты")
        self.items = items
        self.old_positions = old_positions
        self.new_positions = new_positions
        self.background_item = background_item
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap
        self.old_background_pos = old_background_pos
        self.new_background_pos = new_background_pos
        self.blur_controller = blur_controller
        self.old_blur_state = old_blur_state
        self.new_blur_state = new_blur_state

    def _apply_canvas(self, pixmap, pos, blur_state):
        if self.background_item is not None and pixmap is not None:
            self.background_item.setPixmap(pixmap)
            if pos is not None:
                self.background_item.setPos(pos)
            self.background_item.update()
        if self.blur_controller is not None and blur_state is not None:
            self.blur_controller._restore_blur_state(blur_state)
        if self.background_item is not None and self.background_item.scene() is not None:
            views = self.background_item.scene().views()
            if views:
                view = views[0]
                view.setSceneRect(self.background_item.sceneBoundingRect())
                view.update_resolution_from_background()

    def redo(self):
        for item, pos in zip(self.items, self.new_positions):
            item.setPos(pos)
        self._apply_canvas(self.new_pixmap, self.new_background_pos, self.new_blur_state)

    def undo(self):
        for item, pos in zip(self.items, self.old_positions):
            item.setPos(pos)
        self._apply_canvas(self.old_pixmap, self.old_background_pos, self.old_blur_state)


class ResizeItemCommand(QUndoCommand):
    """Команда изменения геометрии прямоугольных/эллиптических элементов."""

    def __init__(self, item, old_rect, new_rect):
        super().__init__("Изменить размер")
        self.item = item
        self.old_rect = old_rect
        self.new_rect = new_rect

    def redo(self):
        self.item.setRect(self.new_rect)

    def undo(self):
        self.item.setRect(self.old_rect)


class ChangePenCommand(QUndoCommand):
    """Команда изменения пера (цвет/толщина/стиль)."""

    def __init__(self, item, old_pen, new_pen):
        super().__init__("Изменить стиль")
        self.item = item
        self.old_pen = old_pen
        self.new_pen = new_pen

    def redo(self):
        self.item.setPen(self.new_pen)

    def undo(self):
        self.item.setPen(self.old_pen)


class ChangeTextCommand(QUndoCommand):
    """Команда изменения текста."""

    def __init__(self, item, old_text, new_text):
        super().__init__("Изменить текст")
        self.item = item
        self.old_text = old_text
        self.new_text = new_text

    def redo(self):
        self.item.setPlainText(self.new_text)

    def undo(self):
        self.item.setPlainText(self.old_text)