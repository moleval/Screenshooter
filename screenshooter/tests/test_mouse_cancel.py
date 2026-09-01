"""
Тесты отмены операций в MouseInteractionManager.
"""

import pytest
from PyQt5.QtCore import Qt, QPointF, QEvent, QPoint
from PyQt5.QtGui import QMouseEvent, QPixmap, QColor
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsRectItem

from screenshooter.view import EditorView


@pytest.fixture
def view_and_scene(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)
    view.resize(300, 300)
    pm = QPixmap(200, 200)
    pm.fill(QColor("white"))
    view.set_background_from_pixmap(pm)
    return view, scene


def make_mouse_event(view, event_type, pos=None, button=Qt.LeftButton, modifiers=Qt.NoModifier):
    if pos is None:
        pos = view.viewport().rect().center()
    local = QPointF(pos)
    global_pos = view.viewport().mapToGlobal(pos)
    return QMouseEvent(
        event_type,
        local,
        QPointF(global_pos),
        button,
        button,
        modifiers,
    )


def test_cancel_drawing_removes_temp_item(view_and_scene):
    view, scene = view_and_scene
    view.current_tool = 'rect'
    from screenshooter.tools.rect_tool import RectTool
    view._tool = RectTool(view)

    event = make_mouse_event(view, QEvent.MouseButtonPress)
    view.mousePressEvent(event)
    assert view.temp_item is not None

    manager = view.mouse_manager
    assert manager.handle_cancel() is True
    assert view.temp_item is None
    assert view.start_point is None
    assert view.temp_item not in scene.items()


def test_cancel_crop_calls_api(view_and_scene, monkeypatch):
    view, _ = view_and_scene
    cancel_called = False

    def fake_cancel():
        nonlocal cancel_called
        cancel_called = True
        view.image_editor.crop_mode = False

    monkeypatch.setattr(view.image_editor, 'cancel_crop_mode', fake_cancel)
    view.image_editor.crop_mode = True

    assert view.mouse_manager.handle_cancel() is True
    assert cancel_called
    assert not view.image_editor.crop_mode


def test_cancel_blur_calls_api(view_and_scene, monkeypatch):
    view, _ = view_and_scene
    blur_called = False

    def fake_blur_escape():
        nonlocal blur_called
        blur_called = True
        view.blur_controller.blur_mode = False

    monkeypatch.setattr(view.blur_controller, 'handle_blur_escape', fake_blur_escape)
    view.blur_controller.blur_mode = True

    assert view.mouse_manager.handle_cancel() is True
    assert blur_called
    assert not view.blur_controller.blur_mode


def test_cancel_active_text_deactivates(view_and_scene):
    view, scene = view_and_scene
    from screenshooter.items.text_item import TextItem
    text_item = TextItem(view, bg_color=None)
    text_item.setPlainText("Test")
    text_item.setPos(100, 100)
    scene.addItem(text_item)
    text_item.setEditable(True)
    view.active_text_item = text_item

    assert view.mouse_manager.handle_cancel() is True
    assert not text_item._editable
    assert view.active_text_item is None


def test_cancel_selection_clears_and_restores(view_and_scene, monkeypatch):
    view, scene = view_and_scene
    restore_called = False

    def fake_restore():
        nonlocal restore_called
        restore_called = True

    monkeypatch.setattr(view.manipulation_controller, '_restore_tool_if_needed', fake_restore)

    item = QGraphicsRectItem(0, 0, 10, 10)
    item.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
    scene.addItem(item)
    item.setSelected(True)

    assert view.mouse_manager.handle_cancel() is True
    assert not scene.selectedItems()
    assert restore_called


def test_handle_cancel_idempotent(view_and_scene):
    view, _ = view_and_scene
    manager = view.mouse_manager

    # Ничего не активно
    assert manager.handle_cancel() is False

    # Создаём temp_item через реальное рисование
    view.current_tool = 'rect'
    from screenshooter.tools.rect_tool import RectTool
    view._tool = RectTool(view)
    event = make_mouse_event(view, QEvent.MouseButtonPress)
    view.mousePressEvent(event)
    assert view.temp_item is not None

    assert manager.handle_cancel() is True
    assert manager.handle_cancel() is False   # уже нечего отменять


def test_cancel_priority_drawing_over_crop_blur(view_and_scene, monkeypatch):
    view, scene = view_and_scene
    cancel_crop_called = False
    blur_called = False

    def fake_cancel_crop():
        nonlocal cancel_crop_called
        cancel_crop_called = True
        view.image_editor.crop_mode = False

    def fake_blur_escape():
        nonlocal blur_called
        blur_called = True
        view.blur_controller.blur_mode = False

    monkeypatch.setattr(view.image_editor, 'cancel_crop_mode', fake_cancel_crop)
    monkeypatch.setattr(view.blur_controller, 'handle_blur_escape', fake_blur_escape)

    view.image_editor.crop_mode = True
    view.blur_controller.blur_mode = True

    # Создаём temp_item напрямую, минуя dispatch
    temp = QGraphicsRectItem(0, 0, 10, 10)
    scene.addItem(temp)
    view.temp_item = temp
    view.start_point = QPointF(10, 10)

    manager = view.mouse_manager

    # Первый вызов отменяет только drawing
    assert manager.handle_cancel() is True
    assert not cancel_crop_called
    assert not blur_called
    assert view.temp_item is None

    # Второй вызов отменяет crop
    assert manager.handle_cancel() is True
    assert cancel_crop_called
    assert not blur_called

    # Третий вызов отменяет blur
    assert manager.handle_cancel() is True
    assert blur_called


def test_handle_cancel_full_drain(view_and_scene):
    """Последовательные вызовы handle_cancel() возвращают True,
    пока есть что отменять, затем стабильно возвращают False."""
    view, scene = view_and_scene
    manager = view.mouse_manager

    # Создаём редактируемый текст и выделение, чтобы было несколько состояний.
    from screenshooter.items.text_item import TextItem
    text_item = TextItem(view, bg_color=None)
    text_item.setPlainText("Test")
    text_item.setPos(100, 100)
    scene.addItem(text_item)
    text_item.setEditable(True)
    view.active_text_item = text_item

    # Добавляем выделяемый элемент
    selectable = QGraphicsRectItem(0, 0, 10, 10)
    selectable.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
    scene.addItem(selectable)
    selectable.setSelected(True)

    results = []
    for _ in range(10):
        result = manager.handle_cancel()
        results.append(result)
        if not result:
            break

    # После полного drain последний вызов должен вернуть False
    assert results[-1] is False
    # И повторный вызов тоже False (идемпотентность)
    assert manager.handle_cancel() is False