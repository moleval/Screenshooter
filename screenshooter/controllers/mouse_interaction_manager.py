"""
Модуль: controllers/mouse_interaction_manager.py
Описание: Диспетчер событий мыши для EditorView.
"""


class MouseInteractionManager:
    """Отвечает только за маршрутизацию событий мыши между обработчиками."""

    def __init__(self, view, blur_controller, image_editor, manipulation_controller):
        self.view = view
        self.blur_controller = blur_controller
        self.image_editor = image_editor
        self.manipulation_controller = manipulation_controller

    def handle_press(self, event) -> bool:
        return False

    def handle_move(self, event) -> bool:
        return False

    def handle_release(self, event) -> bool:
        return False

    def handle_cancel(self):
        pass