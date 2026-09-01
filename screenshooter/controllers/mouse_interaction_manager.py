"""
Модуль: controllers/mouse_interaction_manager.py
Описание: Диспетчер событий мыши для EditorView.

На текущем этапе реализована маршрутизация только для режима размытия (blur).
Остальные режимы будут добавлены на следующих шагах.
"""

from PyQt5.QtCore import Qt, QPointF

from ..items.blur_region_item import BlurRegionItem


class MouseInteractionManager:
    """Отвечает только за маршрутизацию событий мыши между обработчиками."""

    def __init__(self, view, blur_controller, image_editor, manipulation_controller):
        """
        :param view: EditorView, для которого выполняется диспетчеризация.
        :param blur_controller: Контроллер режима размытия.
        :param image_editor: Контроллер режима обрезки (ImageEditController).
                             Используется начиная с Шага 3 (перенос crop).
        :param manipulation_controller: Контроллер манипуляций объектами.
        """
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

        return False

    def handle_move(self, event) -> bool:
        """Обрабатывает перемещение мыши. Возвращает True, если событие поглощено."""
        if not self.manipulation_controller._drag_items:
            if self.blur_controller.blur_mode:
                if self.blur_controller.handle_mouse_move(event):
                    return True
        return False

    def handle_release(self, event) -> bool:
        """Обрабатывает отпускание мыши. Возвращает True, если событие поглощено."""
        if not self.manipulation_controller._drag_items:
            if self.blur_controller.blur_mode:
                if self.blur_controller.handle_mouse_release(event):
                    return True
        return False

    def handle_cancel(self):
        """Прерывает текущую операцию. Пока заглушка."""
        pass