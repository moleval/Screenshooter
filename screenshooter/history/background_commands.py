"""
Модуль: history/background_commands.py
Описание: Команды для редактирования фонового изображения.
          Обрезка, поворот, размытие фона.
"""

from PyQt5.QtCore import QRectF, QPointF
from PyQt5.QtWidgets import QUndoCommand


class CropCommand(QUndoCommand):
    """
    Команда обрезки фонового изображения.
    Сохраняет состояние зон размытия, чтобы откат мог их восстановить.
    Также сдвигает оставшиеся элементы, чтобы они соответствовали новой системе координат.
    """

    def __init__(self, scene, background_item, old_pixmap, new_pixmap, items_to_remove,
                 blur_controller=None, crop_rect=None,
                 items_to_shift=None, old_positions=None, new_positions=None):
        super().__init__("Обрезка")
        self.scene = scene
        self.background_item = background_item
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap
        self.items_to_remove = items_to_remove
        self.removed_items = []
        self.blur_controller = blur_controller
        self.crop_rect = crop_rect

        self.items_to_shift = items_to_shift or []
        self.old_positions = old_positions or []
        self.new_positions = new_positions or []

        if self.blur_controller is not None:
            self.blur_state = self.blur_controller._get_blur_state()
        else:
            self.blur_state = None

    def redo(self):
        for item in self.items_to_remove:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
                self.removed_items.append(item)

        for item, new_pos in zip(self.items_to_shift, self.new_positions):
            item.setPos(new_pos)

        self.background_item.setPixmap(self.new_pixmap)
        self.background_item.update()

        if self.blur_controller is not None and self.crop_rect is not None:
            self.blur_controller._apply_crop_to_blur_regions(self.crop_rect)
            self.blur_controller.view.setSceneRect(QRectF(self.new_pixmap.rect()))
            self.blur_controller.view.update_resolution_from_background()
            self.blur_controller.view.fit_background_to_view()

    def undo(self):
        self.background_item.setPixmap(self.old_pixmap)
        self.background_item.update()

        for item, old_pos in zip(self.items_to_shift, self.old_positions):
            item.setPos(old_pos)

        for item in self.removed_items:
            if item.scene() is not self.scene:
                self.scene.addItem(item)
        self.removed_items.clear()

        if self.blur_controller is not None and self.blur_state is not None:
            self.blur_controller._restore_blur_state(self.blur_state)
            self.blur_controller.view.setSceneRect(QRectF(self.old_pixmap.rect()))
            self.blur_controller.view.update_resolution_from_background()
            self.blur_controller.view.fit_background_to_view()


class RotateCommand(QUndoCommand):
    """
    Команда поворота фонового изображения.
    Растеризует аннотации, но сохраняет зоны размытия для undo.
    """

    def __init__(self, scene, background_item, old_pixmap, new_pixmap, items_to_remove,
                 blur_controller=None):
        super().__init__("Поворот")
        self.scene = scene
        self.background_item = background_item
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap
        self.items_to_remove = items_to_remove
        self.removed_items = []
        self.blur_controller = blur_controller

        if self.blur_controller is not None:
            self.blur_state = self.blur_controller._get_blur_state()
        else:
            self.blur_state = None

    def redo(self):
        for item in self.items_to_remove:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
                self.removed_items.append(item)

        self.background_item.setPixmap(self.new_pixmap)
        self.background_item.update()

        if self.blur_controller is not None:
            self.blur_controller._clear_blur_regions()
            self.blur_controller.view.setSceneRect(QRectF(self.new_pixmap.rect()))
            self.blur_controller.view.update_resolution_from_background()
            self.blur_controller.view.fit_background_to_view()

    def undo(self):
        self.background_item.setPixmap(self.old_pixmap)
        self.background_item.update()

        for item in self.removed_items:
            if item.scene() is not self.scene:
                self.scene.addItem(item)
        self.removed_items.clear()

        if self.blur_controller is not None and self.blur_state is not None:
            self.blur_controller._restore_blur_state(self.blur_state)
            self.blur_controller.view.setSceneRect(QRectF(self.old_pixmap.rect()))
            self.blur_controller.view.update_resolution_from_background()
            self.blur_controller.view.fit_background_to_view()


class BlurCommand(QUndoCommand):
    """Команда размытия области фонового изображения."""

    def __init__(self, background_item, old_pixmap, new_pixmap):
        super().__init__("Размытие")
        self.background_item = background_item
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap

    def redo(self):
        self.background_item.setPixmap(self.new_pixmap)
        self.background_item.update()

    def undo(self):
        self.background_item.setPixmap(self.old_pixmap)
        self.background_item.update()