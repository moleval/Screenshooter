"""
Модуль: controllers/mouse_interaction_manager.py
Описание: Диспетчер событий мыши для EditorView.

На текущем этапе является скелетом: все методы возвращают False,
поэтому поведение EditorView не изменяется. В дальнейшем сюда будет
поэтапно перенесена логика маршрутизации из EditorView.
"""


class MouseInteractionManager:
    """Отвечает только за маршрутизацию событий мыши между обработчиками."""

    def __init__(self, view, blur_controller, image_editor, manipulation_controller):
        """
        :param view: EditorView, для которого выполняется диспетчеризация.
        :param blur_controller: Контроллер режима размытия.
        :param image_editor: Контроллер режима обрезки (ImageEditController).
        :param manipulation_controller: Контроллер манипуляций объектами.
        """
        self.view = view
        self.blur_controller = blur_controller
        self.image_editor = image_editor
        self.manipulation_controller = manipulation_controller

    def handle_press(self, event) -> bool:
        """Обрабатывает нажатие мыши. Возвращает True, если событие поглощено."""
        # Заглушка: пока ничего не обрабатываем
        return False

    def handle_move(self, event) -> bool:
        """Обрабатывает перемещение мыши. Возвращает True, если событие поглощено."""
        # Заглушка
        return False

    def handle_release(self, event) -> bool:
        """Обрабатывает отпускание мыши. Возвращает True, если событие поглощено."""
        # Заглушка
        return False

    def handle_cancel(self):
        """
        Прерывает текущую операцию (рисование, перетаскивание и т.п.).
        Пока заглушка.
        """
        pass