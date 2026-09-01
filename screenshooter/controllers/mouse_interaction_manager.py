"""
Модуль: controllers/mouse_interaction_manager.py
Описание: Диспетчер событий мыши для EditorView.

Реализована маршрутизация:
  blur → crop → blur_outside → manipulation → text → drawing
  и централизованная отмена (handle_cancel).
"""

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QFont

from ..items import TextItem
from ..items.blur_region_item import BlurRegionItem
from ..history import AddItemCommand


class MouseInteractionManager:
    """Отвечает только за маршрутизацию событий мыши между обработчиками."""

    def __init__(self, view, blur_controller, image_editor, manipulation_controller):
        self.view = view
        self.blur_controller = blur_controller
        self.image_editor = image_editor
        self.manipulation_controller = manipulation_controller

    def handle_press(self, event) -> bool:
        """Обрабатывает нажатие мыши. Возвращает True, если событие поглощено."""
        if self.blur_controller.blur_mode:
            sp = self.view.mapToScene(event.pos())
            item = self.view.scene().itemAt(sp, self.view.transform())
            li = self.view._item_for_manipulation(item) if item else None

            is_blur_handle = False
            active_index = self.blur_controller.active_blur_index
            if active_index is not None and active_index < len(
                self.blur_controller.blur_region_items
            ):
                active_blur = self.blur_controller.blur_region_items[active_index]
                if active_blur.handles:
                    handle_id = active_blur.handles.hit_test(QPointF(event.pos()))
                    if handle_id:
                        is_blur_handle = True

            delegate_to_manipulation = False

            if is_blur_handle:
                pass
            elif li is not None and not self.view._is_background_item(li):
                if isinstance(li, BlurRegionItem):
                    modifiers = event.modifiers()
                    is_ctrl = bool(modifiers & Qt.ControlModifier)
                    is_shift = bool(modifiers & Qt.ShiftModifier)

                    if is_ctrl or is_shift:
                        delegate_to_manipulation = True
                    else:
                        selected = self.view.scene().selectedItems()
                        non_bg_selected = [
                            it for it in selected
                            if not self.view._is_background_item(it)
                        ]
                        if len(non_bg_selected) > 1 and li.isSelected():
                            delegate_to_manipulation = True
                else:
                    delegate_to_manipulation = True

            if delegate_to_manipulation:
                if self.manipulation_controller.handle_mouse_press(event):
                    return True

            if self.blur_controller.handle_mouse_press(event):
                return True

        elif self.image_editor.crop_mode:
            if self.image_editor.handle_mouse_press(event):
                return True

        if self.manipulation_controller.handle_mouse_press(event):
            return True

        # Text tool
        if self.view.current_tool == 'text':
            sp = self.view.mapToScene(event.pos())
            item = self.view.scene().itemAt(sp, self.view.transform())
            li = self.view._item_for_manipulation(item) if item else None

            if isinstance(item, TextItem) and item._editable:
                return False

            if isinstance(li, TextItem):
                if (self.view.active_text_item is not None and
                        self.view.active_text_item is not li):
                    self.view._deactivate_active_text()
                return False
            else:
                if self.view.active_text_item and self.view.active_text_item._editable:
                    self.view._deactivate_active_text()
                if li is None or self.view._is_background_item(li):
                    if not self.view._is_point_inside_background(sp):
                        return True
                    if self.view._first_click_after_activation:
                        ti = TextItem(self.view, bg_color=self.view.current_text_bg)
                        ti.setDefaultTextColor(QColor("#F9D556"))
                        font = QFont()
                        font.setPointSize(self.view.text_size * 4)
                        ti.setFont(font)
                        ti.setPos(sp)
                        self.view.scene().addItem(ti)
                        self.view.active_text_item = ti
                        ti.setSelected(True)
                        ti.setEditable(True)
                        self.view._first_click_after_activation = False
                        self.view.history.push(AddItemCommand(self.view.scene(), ti))
                        return True
                return False

        # Drawing tools
        if self.view.current_tool in ('rect', 'ellipse', 'arrow', 'line'):
            if self.view._tool is not None:
                sp = self.view.mapToScene(event.pos())
                if not self.view._is_point_inside_background(sp):
                    return True
                self.view.start_point = sp
                self.view.temp_item = self.view._tool.start_draw(sp)
                if self.view.temp_item:
                    self.view.scene().addItem(self.view.temp_item)
            return True

        return False

    def handle_move(self, event) -> bool:
        """Обрабатывает перемещение мыши. Возвращает True, если событие поглощено."""
        if not self.manipulation_controller._drag_items:
            if self.blur_controller.blur_mode:
                if self.blur_controller.handle_mouse_move(event):
                    return True
            elif self.image_editor.crop_mode:
                if self.image_editor.handle_mouse_move(event):
                    return True

            if not self.image_editor.crop_mode and not self.blur_controller.blur_mode:
                if self.blur_controller.handle_blur_region_move_outside(event):
                    return True

        if self.manipulation_controller.handle_mouse_move(event):
            return True

        # Drawing tools
        if (self.view.temp_item and self.view._tool is not None and
                self.view.current_tool not in ('text',)):
            self.view._update_cursor(event.pos())
            sp = self.view.mapToScene(event.pos())
            if self.view.image_editor.background_item is not None:
                bg_rect = self.view.image_editor.background_item.mapRectToScene(
                    QRectF(self.view.image_editor.background_item.pixmap().rect()))
                if not bg_rect.contains(sp):
                    sp.setX(max(bg_rect.left(), min(bg_rect.right(), sp.x())))
                    sp.setY(max(bg_rect.top(), min(bg_rect.bottom(), sp.y())))
            self.view._tool.update_draw(self.view.temp_item, sp, event.modifiers())
            return True

        return False

    def handle_release(self, event) -> bool:
        """Обрабатывает отпускание мыши. Возвращает True, если событие поглощено."""
        if not self.manipulation_controller._drag_items:
            if self.blur_controller.blur_mode:
                if self.blur_controller.handle_mouse_release(event):
                    return True
            elif self.image_editor.crop_mode:
                if self.image_editor.handle_mouse_release(event):
                    return True

            if (event.button() == Qt.LeftButton and
                    not self.image_editor.crop_mode and
                    not self.blur_controller.blur_mode):
                if self.blur_controller.handle_blur_region_release_outside(event):
                    return True

        if self.manipulation_controller.handle_mouse_release(event):
            return True

        # Drawing tools
        if (self.view.temp_item and event.button() == Qt.LeftButton and
                self.view._tool is not None and self.view.current_tool not in ('text',)):
            if self.view._tool.finish_draw(self.view.temp_item):
                self.view.scene().clearSelection()
                self.view.temp_item.setSelected(True)
                self.view.history.push(AddItemCommand(self.view.scene(), self.view.temp_item))
            else:
                self.view.scene().removeItem(self.view.temp_item)
            self.view.temp_item = None
            self.view.start_point = None
            return True

        return False

    def handle_cancel(self) -> bool:
        """
        Отменяет наиболее специфичную активную операцию.

        Возвращает True, если состояние было изменено или операция отменена;
        False, если отменять нечего.
        """
        # 1. Незавершённая drawing operation (temp_item) отменяется первой
        if self.view.temp_item is not None:
            if self.view.temp_item.scene() is self.view.scene():
                self.view.scene().removeItem(self.view.temp_item)
            self.view.temp_item = None
            self.view.start_point = None
            return True

        # 2. Отмена режима обрезки
        if self.view.image_editor.crop_mode:
            self.view.image_editor.cancel_crop_mode()
            return True

        # 3. Отмена режима размытия
        if self.view.blur_controller.blur_mode:
            self.view.blur_controller.handle_blur_escape()
            return True

        # 4. Деактивация редактируемого текста
        if self.view.active_text_item is not None and self.view.active_text_item._editable:
            self.view._deactivate_active_text()
            return True

        # 5. Снятие выделения с восстановлением временного инструмента
        selected = self.view.scene().selectedItems()
        if selected:
            self.view.scene().clearSelection()
            self.view.manipulation_controller._restore_tool_if_needed()
            return True

        return False