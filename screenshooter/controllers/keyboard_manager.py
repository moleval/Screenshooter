"""
Модуль: controllers/keyboard_manager.py
Описание: Контроллер обработки клавиатуры.
"""

from PyQt5.QtCore import Qt, QPointF, QRectF

from ..items.blur_region_item import BlurRegionItem
from ..history import MoveItemsCommand, MoveBlurRegionCommand


class KeyboardManager:
    """
    Обрабатывает нажатия клавиш в редакторе.
    Делегирует их соответствующим контроллерам.
    """

    def __init__(self, view):
        self.view = view

    # ==============================================================
    # Два главных метода — вызываются из view.py
    # ==============================================================

    def handle_key_press(self, event) -> bool:
        """Обрабатывает нажатие клавиши. Возвращает True, если обработано."""

        # 1. Ctrl+A — выделить все элементы
        if event.key() == Qt.Key_A and event.modifiers() & Qt.ControlModifier:
            if self.view.active_text_item and self.view.active_text_item._editable:
                return False
            self.view.select_all_items()
            return True

        # 2. Ctrl+C — копировать
        if event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
            if self.view.active_text_item and self.view.active_text_item._editable:
                return False
            self.view.clipboard_controller.copy_selected()
            return True

        # 3. Ctrl+V — вставить
        if event.key() == Qt.Key_V and event.modifiers() & Qt.ControlModifier:
            if self.view.active_text_item and self.view.active_text_item._editable:
                return False
            self.view.clipboard_controller.paste()
            return True

        # 4. Ctrl+X — вырезать
        if event.key() == Qt.Key_X and event.modifiers() & Qt.ControlModifier:
            if self.view.active_text_item and self.view.active_text_item._editable:
                return False
            self.view.clipboard_controller.cut_selected()
            return True

        # 5. Delete — удалить выделенное
        if event.key() == Qt.Key_Delete:
            self.view.delete_selected()
            return True

        # 6. Escape — отмена режимов, снятие выделения
        if event.key() == Qt.Key_Escape:
            if self.view.image_editor.crop_mode:
                self.view.image_editor.cancel_crop_mode()
                return True
            if self.view.blur_controller.blur_mode:
                self.view.blur_controller.handle_blur_escape()
                return True
            self.view.scene().clearSelection()
            self.view._deactivate_active_text()
            self.view.manipulation_controller._restore_tool_if_needed()
            return True

        # 7. Ctrl (зажатие) — временный указатель
        if event.key() == Qt.Key_Control:
            self.view.manipulation_controller.ctrl_pressed = True
            if self.view.current_tool:
                self.view.manipulation_controller._activate_temp_pointer('modifier')
            return True

        # 8. Стрелки — перемещение элементов
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            if self.view.active_text_item and self.view.active_text_item._editable:
                return False
            return self._handle_arrow_keys(event)

        return False

    def handle_key_release(self, event) -> bool:
        """Обрабатывает отпускание клавиши. Возвращает True, если обработано."""

        # Отпускание Ctrl — восстановление инструмента
        if event.key() == Qt.Key_Control:
            self.view.manipulation_controller.ctrl_pressed = False
            if not self.view.manipulation_controller.ctrl_pressed:
                self.view.manipulation_controller._restore_tool_if_needed()
            return True

        return False

    # ==============================================================
    # Внутренние методы
    # ==============================================================

    def _handle_arrow_keys(self, event) -> bool:
        """Перемещение выделенных элементов стрелками."""
        view = self.view

        # Активная зона размытия — двигаем её
        if view.blur_controller.active_blur_index is not None:
            idx = view.blur_controller.active_blur_index
            old_rect = view.blur_controller.blur_regions[idx]
            dx = dy = 0
            step = 10 if (event.modifiers() & Qt.ShiftModifier) else 1
            if event.key() == Qt.Key_Left: dx = -step
            elif event.key() == Qt.Key_Right: dx = step
            elif event.key() == Qt.Key_Up: dy = -step
            elif event.key() == Qt.Key_Down: dy = step

            new_rect = view.blur_controller._constrain_move(old_rect, QPointF(dx, dy))
            if new_rect != old_rect:
                view.blur_controller.blur_regions[idx] = new_rect
                view.blur_controller.blur_region_items[idx].update_rect(new_rect)
                view.blur_controller._force_blur_recompute()
                view.history.push(MoveBlurRegionCommand(
                    view.blur_controller, idx, old_rect, new_rect))
            return True

        # Выделенные элементы — двигаем их
        selected = view.scene().selectedItems()
        items = [it for it in selected if not view._is_background_item(it)]
        if items:
            dx = dy = 0
            step = 10 if (event.modifiers() & Qt.ShiftModifier) else 1
            if event.key() == Qt.Key_Left: dx = -step
            elif event.key() == Qt.Key_Right: dx = step
            elif event.key() == Qt.Key_Up: dy = -step
            elif event.key() == Qt.Key_Down: dy = step

            normal_items = []
            normal_old = []
            normal_new = []

            for it in items:
                old_pos = it.pos()
                new_pos = old_pos + QPointF(dx, dy)
                if view.image_editor.background_item is not None:
                    image_rect = QRectF(
                        view.image_editor.background_item.pixmap().rect())
                    item_rect = it.boundingRect()
                    proposed = QRectF(new_pos + item_rect.topLeft(),
                                      new_pos + item_rect.bottomRight())
                    if proposed.left() < image_rect.left():
                        new_pos.setX(new_pos.x() + (
                            image_rect.left() - proposed.left()))
                    elif proposed.right() > image_rect.right():
                        new_pos.setX(new_pos.x() - (
                            proposed.right() - image_rect.right()))
                    proposed = QRectF(new_pos + item_rect.topLeft(),
                                      new_pos + item_rect.bottomRight())
                    if proposed.top() < image_rect.top():
                        new_pos.setY(new_pos.y() + (
                            image_rect.top() - proposed.top()))
                    elif proposed.bottom() > image_rect.bottom():
                        new_pos.setY(new_pos.y() - (
                            proposed.bottom() - image_rect.bottom()))

                if isinstance(it, BlurRegionItem):
                    old_rect = it.rect()
                    new_rect = old_rect.translated(dx, dy)
                    if old_rect != new_rect:
                        try:
                            idx_blur = view.blur_controller.blur_region_items.index(it)
                            view.history.push(MoveBlurRegionCommand(
                                view.blur_controller, idx_blur, old_rect, new_rect))
                        except ValueError:
                            pass
                else:
                    normal_items.append(it)
                    normal_old.append(old_pos)
                    normal_new.append(new_pos)

            if normal_items:
                for i_n, nit in enumerate(normal_items):
                    nit.setPos(normal_new[i_n])
                view.history.push(
                    MoveItemsCommand(normal_items, normal_old, normal_new))

            view._update_pasted_image_handles()
            view._update_blur_region_handles()
            return True

        return False