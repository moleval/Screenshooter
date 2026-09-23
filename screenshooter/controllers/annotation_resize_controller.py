"""
Модуль: controllers/annotation_resize_controller.py
Описание: Каркас контроллера изменения размера аннотаций.

Контроллер является единственной точкой входа для resize аннотаций.
Конкретная геометрия ручек и изменение элементов будут добавляться
на следующих этапах.
"""


class AnnotationResizeController:
    """Управляет изменением размера аннотаций через их ручки."""

    def __init__(self, view):
        self.view = view

    def _blocked_by_mode(self) -> bool:
        """Аннотации не должны изменяться в режимах blur и crop."""
        return bool(
            self.view.blur_controller.blur_mode
            or self.view.image_editor.crop_mode
        )

    def handle_mouse_press(self, event) -> bool:
        """Обрабатывает нажатие на ручку аннотации."""
        if self._blocked_by_mode():
            return False
        # Геометрия resize будет реализована на следующих шагах.
        return False

    def handle_mouse_move(self, event) -> bool:
        """Обрабатывает перемещение ручки аннотации."""
        if self._blocked_by_mode():
            return False
        return False

    def handle_mouse_release(self, event) -> bool:
        """Завершает изменение размера аннотации."""
        if self._blocked_by_mode():
            return False
        return False
