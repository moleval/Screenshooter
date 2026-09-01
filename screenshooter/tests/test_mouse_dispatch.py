"""
Интеграционные тесты маршрутизации событий мыши (baseline).

Матрица dispatch (эталон):

| Состояние    | Press        | Move         | Release      |
| ------------ | ------------ | ------------ | ------------ |
| Blur         | Blur         | Blur         | Blur         |
| Crop         | Crop         | Crop         | Crop         |
| Manipulation | Manipulation | Manipulation | Manipulation |
| Text editing | Qt           | Qt           | Qt           |
| Drawing      | Tool         | Tool         | Tool         |
| Nothing      | Qt           | Qt           | Qt           |

Ключевой контракт: если обработчик вернул True, цепочка немедленно прекращается.
"""

import pytest
from PyQt5.QtCore import Qt, QPointF, QEvent
from PyQt5.QtGui import QMouseEvent, QPixmap, QColor
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsRectItem

from screenshooter.view import EditorView


@pytest.fixture
def view_and_scene(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)

    pm = QPixmap(200, 200)
    pm.fill(QColor("white"))
    view.set_background_from_pixmap(pm)

    return view, scene


def make_mouse_event(view, event_type, pos=None, button=Qt.LeftButton, modifiers=Qt.NoModifier):
    if pos is None:
        pos = view.viewport().rect().center()
    return QMouseEvent(
        event_type,
        QPointF(pos),
        Qt.LeftButton,
        button,
        modifiers,
    )


# ---------- Short-circuit тесты для Press ----------

def test_blur_short_circuits_crop_and_manipulation(view_and_scene, monkeypatch):
    view, _ = view_and_scene
    view.blur_controller.blur_mode = True

    blur_pressed = False
    manip_pressed = False
    crop_pressed = False

    def fake_blur_press(e):
        nonlocal blur_pressed
        blur_pressed = True
        return True
    def fake_manip_press(e):
        nonlocal manip_pressed
        manip_pressed = True
        return True
    def fake_crop_press(e):
        nonlocal crop_pressed
        crop_pressed = True
        return True

    monkeypatch.setattr(view.blur_controller, 'handle_mouse_press', fake_blur_press)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_press', fake_manip_press)
    monkeypatch.setattr(view.image_editor, 'handle_mouse_press', fake_crop_press)

    event = make_mouse_event(view, QEvent.MouseButtonPress)
    view.mousePressEvent(event)

    assert blur_pressed
    assert not crop_pressed
    assert not manip_pressed


def test_crop_short_circuits_manipulation(view_and_scene, monkeypatch):
    view, _ = view_and_scene
    view.image_editor.crop_mode = True

    crop_pressed = False
    manip_pressed = False

    def fake_crop_press(e):
        nonlocal crop_pressed
        crop_pressed = True
        return True
    def fake_manip_press(e):
        nonlocal manip_pressed
        manip_pressed = True
        return True

    monkeypatch.setattr(view.image_editor, 'handle_mouse_press', fake_crop_press)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_press', fake_manip_press)

    event = make_mouse_event(view, QEvent.MouseButtonPress)
    view.mousePressEvent(event)

    assert crop_pressed
    assert not manip_pressed


def test_manipulation_short_circuits_drawing(view_and_scene, monkeypatch):
    view, _ = view_and_scene
    view.current_tool = 'rect'
    mock_tool = MockTool()
    view._tool = mock_tool

    manip_pressed = False

    def fake_manip_press(e):
        nonlocal manip_pressed
        manip_pressed = True
        return True

    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_press', fake_manip_press)

    event = make_mouse_event(view, QEvent.MouseButtonPress)
    view.mousePressEvent(event)

    assert manip_pressed
    assert not mock_tool.start_called


def test_drawing_when_manipulation_returns_false(view_and_scene, monkeypatch):
    view, _ = view_and_scene
    view.current_tool = 'rect'
    mock_tool = MockTool()
    view._tool = mock_tool

    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_press', lambda e: False)

    event = make_mouse_event(view, QEvent.MouseButtonPress)
    view.mousePressEvent(event)

    assert mock_tool.start_called
    assert view.temp_item is not None


def test_editable_text_is_dispatched_to_manipulation_then_qt(view_and_scene, monkeypatch):
    view, scene = view_and_scene
    view.current_tool = 'text'

    from screenshooter.items.text_item import TextItem
    text_item = TextItem(view, bg_color=None)
    text_item.setPlainText("Test")
    text_item.setPos(10, 10)
    scene.addItem(text_item)
    text_item.setEditable(True)
    view.active_text_item = text_item

    manip_pressed = False

    def fake_manip_press(e):
        nonlocal manip_pressed
        manip_pressed = True
        return False

    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_press', fake_manip_press)

    pos = view.mapFromScene(text_item.sceneBoundingRect().center())
    event = make_mouse_event(view, QEvent.MouseButtonPress, pos=pos)
    view.mousePressEvent(event)

    assert manip_pressed
    assert view.temp_item is None


# ---------- Полный цикл press/move/release для каждого состояния ----------

def test_blur_press_move_release_cycle(view_and_scene, monkeypatch):
    view, _ = view_and_scene
    view.blur_controller.blur_mode = True

    blur_pressed = False
    blur_moved = False
    blur_released = False
    manip_any = False

    def fake_blur_press(e):
        nonlocal blur_pressed
        blur_pressed = True
        return True
    def fake_blur_move(e):
        nonlocal blur_moved
        blur_moved = True
        return True
    def fake_blur_release(e):
        nonlocal blur_released
        blur_released = True
        return True
    def fake_manip_any(e):
        nonlocal manip_any
        manip_any = True
        return True

    monkeypatch.setattr(view.blur_controller, 'handle_mouse_press', fake_blur_press)
    monkeypatch.setattr(view.blur_controller, 'handle_mouse_move', fake_blur_move)
    monkeypatch.setattr(view.blur_controller, 'handle_mouse_release', fake_blur_release)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_press', fake_manip_any)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_move', fake_manip_any)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_release', fake_manip_any)

    view.mousePressEvent(make_mouse_event(view, QEvent.MouseButtonPress))
    view.mouseMoveEvent(make_mouse_event(view, QEvent.MouseMove))
    view.mouseReleaseEvent(make_mouse_event(view, QEvent.MouseButtonRelease))

    assert blur_pressed
    assert blur_moved
    assert blur_released
    assert not manip_any


def test_crop_press_move_release_cycle(view_and_scene, monkeypatch):
    view, _ = view_and_scene
    view.image_editor.crop_mode = True

    crop_pressed = False
    crop_moved = False
    crop_released = False
    manip_any = False

    def fake_crop_press(e):
        nonlocal crop_pressed
        crop_pressed = True
        return True
    def fake_crop_move(e):
        nonlocal crop_moved
        crop_moved = True
        return True
    def fake_crop_release(e):
        nonlocal crop_released
        crop_released = True
        return True
    def fake_manip_any(e):
        nonlocal manip_any
        manip_any = True
        return True

    monkeypatch.setattr(view.image_editor, 'handle_mouse_press', fake_crop_press)
    monkeypatch.setattr(view.image_editor, 'handle_mouse_move', fake_crop_move)
    monkeypatch.setattr(view.image_editor, 'handle_mouse_release', fake_crop_release)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_press', fake_manip_any)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_move', fake_manip_any)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_release', fake_manip_any)

    view.mousePressEvent(make_mouse_event(view, QEvent.MouseButtonPress))
    view.mouseMoveEvent(make_mouse_event(view, QEvent.MouseMove))
    view.mouseReleaseEvent(make_mouse_event(view, QEvent.MouseButtonRelease))

    assert crop_pressed
    assert crop_moved
    assert crop_released
    assert not manip_any


def test_manipulation_press_move_release_cycle(view_and_scene, monkeypatch):
    view, _ = view_and_scene
    manip_pressed = False
    manip_moved = False
    manip_released = False
    drawing_any = False

    def fake_manip_press(e):
        nonlocal manip_pressed
        manip_pressed = True
        return True
    def fake_manip_move(e):
        nonlocal manip_moved
        manip_moved = True
        return True
    def fake_manip_release(e):
        nonlocal manip_released
        manip_released = True
        return True
    def fake_tool_start(e):
        nonlocal drawing_any
        drawing_any = True
        return None

    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_press', fake_manip_press)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_move', fake_manip_move)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_release', fake_manip_release)
    view._tool = MockTool()
    monkeypatch.setattr(view._tool, 'start_draw', fake_tool_start)

    view.mousePressEvent(make_mouse_event(view, QEvent.MouseButtonPress))
    view.mouseMoveEvent(make_mouse_event(view, QEvent.MouseMove))
    view.mouseReleaseEvent(make_mouse_event(view, QEvent.MouseButtonRelease))

    assert manip_pressed
    assert manip_moved
    assert manip_released
    assert not drawing_any


def test_drawing_press_move_release_creates_item(view_and_scene, monkeypatch):
    view, _ = view_and_scene
    view.current_tool = 'rect'
    mock_tool = MockTool()
    view._tool = mock_tool

    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_press', lambda e: False)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_move', lambda e: False)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_release', lambda e: False)

    view.mousePressEvent(make_mouse_event(view, QEvent.MouseButtonPress))
    assert mock_tool.start_called

    view.mouseMoveEvent(make_mouse_event(view, QEvent.MouseMove))
    assert mock_tool.update_called

    view.mouseReleaseEvent(make_mouse_event(view, QEvent.MouseButtonRelease))
    assert mock_tool.finish_called
    assert view.temp_item is None


def test_drawing_release_removes_temp_item_on_false(view_and_scene, monkeypatch):
    view, _ = view_and_scene
    view.current_tool = 'rect'
    mock_tool = MockTool()
    mock_tool.finish_result = False
    view._tool = mock_tool

    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_press', lambda e: False)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_move', lambda e: False)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_release', lambda e: False)

    view.mousePressEvent(make_mouse_event(view, QEvent.MouseButtonPress))
    assert view.temp_item is not None

    view.mouseMoveEvent(make_mouse_event(view, QEvent.MouseMove))
    view.mouseReleaseEvent(make_mouse_event(view, QEvent.MouseButtonRelease))

    assert mock_tool.finish_called
    assert view.temp_item is None


# Заглушка инструмента рисования
class MockTool:
    def __init__(self):
        self.start_called = False
        self.update_called = False
        self.finish_called = False
        self.finish_result = True

    def start_draw(self, scene_pos):
        self.start_called = True
        return QGraphicsRectItem(0, 0, 10, 10)

    def update_draw(self, temp_item, scene_pos, modifiers):
        self.update_called = True

    def finish_draw(self, temp_item):
        self.finish_called = True
        return self.finish_result