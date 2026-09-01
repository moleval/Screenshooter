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
from PyQt5.QtCore import Qt, QPointF, QEvent, QRectF
from PyQt5.QtGui import QMouseEvent, QPixmap, QColor
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsRectItem

from screenshooter.view import EditorView


@pytest.fixture
def view_and_scene(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)
    view.resize(300, 300)  # фиксируем размер для предсказуемых координат

    pm = QPixmap(200, 200)
    pm.fill(QColor("white"))
    view.set_background_from_pixmap(pm)

    return view, scene


def make_mouse_event(view, event_type, pos=None, button=Qt.LeftButton, modifiers=Qt.NoModifier):
    """Создаёт QMouseEvent с координатами в системе viewport."""
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


class MockTool:
    """Заглушка инструмента рисования для тестов."""

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


# ---------- Short-circuit тесты ----------

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
    text_item.setPos(100, 100)  # центр подложки
    scene.addItem(text_item)
    text_item.setEditable(True)
    view.active_text_item = text_item

    manip_pressed = False

    def fake_manip_press(e):
        nonlocal manip_pressed
        manip_pressed = True
        return False

    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_press', fake_manip_press)

    # Используем координаты viewport, а не EditorView
    pos = view.mapFromScene(text_item.sceneBoundingRect().center())
    event = make_mouse_event(view, QEvent.MouseButtonPress, pos=pos)
    view.mousePressEvent(event)

    assert manip_pressed
    assert view.temp_item is None


# ---------- Полный цикл press/move/release ----------

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


def test_blur_outside_has_priority_over_manipulation(view_and_scene, monkeypatch):
    view, _ = view_and_scene
    blur_outside_called = False
    manipulation_called = False

    def fake_blur_outside(e):
        nonlocal blur_outside_called
        blur_outside_called = True
        return True   # перехватываем событие, манипуляция не должна вызываться

    def fake_manip_move(e):
        nonlocal manipulation_called
        manipulation_called = True
        return True

    monkeypatch.setattr(view.blur_controller, 'handle_blur_region_move_outside', fake_blur_outside)
    monkeypatch.setattr(view.manipulation_controller, 'handle_mouse_move', fake_manip_move)
    # Убеждаемся, что нет перетаскивания и режимов
    view.manipulation_controller._drag_items = []
    view.blur_controller.blur_mode = False
    view.image_editor.crop_mode = False

    event = make_mouse_event(view, QEvent.MouseMove)
    view.mouseMoveEvent(event)

    assert blur_outside_called
    assert not manipulation_called

def test_pe004_diagnostic_blur_in_group(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)
    view.resize(300, 300)
    pm = QPixmap(200, 200)
    pm.fill(QColor("white"))
    view.set_background_from_pixmap(pm)

    from screenshooter.items.shape_items import RectangleItem
    from screenshooter.items.blur_region_item import BlurRegionItem
    from PyQt5.QtGui import QPen

    rect_item = RectangleItem(QRectF(10, 10, 50, 30), QPen(QColor("red"), 2))
    scene.addItem(rect_item)
    rect_item.setSelected(True)

    blur_item = BlurRegionItem(QRectF(70, 70, 40, 40), view, mode='inactive')
    scene.addItem(blur_item)
    blur_item.setSelected(True)

    # Клик по центру Blur
    pos = view.mapFromScene(blur_item.sceneBoundingRect().center())
    event = make_mouse_event(view, QEvent.MouseButtonPress, pos=pos)

    # Вызываем обработчик вручную (чтобы избежать влияния MouseInteractionManager)
    manager = view.manipulation_controller
    sp = view.mapToScene(event.pos())
    item = scene.itemAt(sp, view.transform())
    li = view._item_for_manipulation(item) if item else None

    # Диагностика
    print(f"item: {type(item)}, li: {type(li)}, li_is_selected: {li.isSelected() if li else None}")
    selected = scene.selectedItems()
    non_bg = [it for it in selected if not view._is_background_item(it)]
    print(f"selected: {len(selected)}, non_bg: {len(non_bg)}")

    # Проверяем, что li — BlurRegionItem
    assert isinstance(li, BlurRegionItem)
    # Проверяем, что оба выделены
    assert rect_item.isSelected()
    assert blur_item.isSelected()    

def test_pe004_blur_group_reaches_manipulation(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)
    view.resize(300, 300)
    pm = QPixmap(200, 200)
    pm.fill(QColor("white"))
    view.set_background_from_pixmap(pm)

    from screenshooter.items.shape_items import RectangleItem
    from screenshooter.items.blur_region_item import BlurRegionItem
    from PyQt5.QtGui import QPen

    rect_item = RectangleItem(QRectF(10, 10, 50, 30), QPen(QColor("red"), 2))
    scene.addItem(rect_item)

    blur_item = BlurRegionItem(QRectF(70, 70, 40, 40), view, mode='inactive')
    scene.addItem(blur_item)

    rect_item.setSelected(True)
    blur_item.setSelected(True)

    pos = view.mapFromScene(blur_item.sceneBoundingRect().center())
    event = make_mouse_event(view, QEvent.MouseButtonPress, pos=pos)

    result = view.manipulation_controller.handle_mouse_press(event)

    print(f"handle_mouse_press result: {result}")
    print(f"_drag_items: {view.manipulation_controller._drag_items}")
    print(f"rect selected: {rect_item.isSelected()}")
    print(f"blur selected: {blur_item.isSelected()}")

    assert result is True
    assert rect_item.isSelected()
    assert blur_item.isSelected()
    assert rect_item in view.manipulation_controller._drag_items
    assert blur_item in view.manipulation_controller._drag_items

def test_pe004_full_scenario_with_pasted_image(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)
    view.resize(300, 300)
    pm = QPixmap(200, 200)
    pm.fill(QColor("white"))
    view.set_background_from_pixmap(pm)

    from screenshooter.items.shape_items import RectangleItem
    from screenshooter.items.blur_region_item import BlurRegionItem
    from screenshooter.items.pasted_image_item import PastedImageItem
    from PyQt5.QtGui import QPen

    # Прямоугольник
    rect_item = RectangleItem(QRectF(10, 10, 50, 30), QPen(QColor("red"), 2))
    scene.addItem(rect_item)
    rect_item.setSelected(True)

    # Вставленное изображение (например, маленький квадрат)
    pasted_pm = QPixmap(20, 20)
    pasted_pm.fill(QColor("blue"))
    pasted_item = PastedImageItem(pasted_pm, view)
    pasted_item.setPos(40, 50)
    scene.addItem(pasted_item)
    view.pasted_images.append(pasted_item)
    pasted_item.setSelected(True)

    # Зона размытия
    blur_item = BlurRegionItem(QRectF(70, 70, 40, 40), view, mode='inactive')
    scene.addItem(blur_item)
    blur_item.setSelected(True)

    # Клик по Blur через полный dispatch
    pos = view.mapFromScene(blur_item.sceneBoundingRect().center())
    press_event = make_mouse_event(view, QEvent.MouseButtonPress, pos=pos)
    view.mousePressEvent(press_event)

    print("selected after press:", [type(it).__name__ for it in scene.selectedItems()])
    print("_drag_items:", view.manipulation_controller._drag_items)

    assert rect_item.isSelected()
    assert pasted_item.isSelected()
    assert blur_item.isSelected()
    assert rect_item in view.manipulation_controller._drag_items
    assert pasted_item in view.manipulation_controller._drag_items
    assert blur_item in view.manipulation_controller._drag_items

def test_pe004_after_copy_paste(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)
    view.resize(300, 300)
    pm = QPixmap(200, 200)
    pm.fill(QColor("white"))
    view.set_background_from_pixmap(pm)

    from screenshooter.items.shape_items import RectangleItem
    from screenshooter.items.blur_region_item import BlurRegionItem
    from screenshooter.items.pasted_image_item import PastedImageItem
    from PyQt5.QtGui import QPen

    # Создаём три исходных объекта
    rect_item = RectangleItem(QRectF(10, 10, 50, 30), QPen(QColor("red"), 2))
    scene.addItem(rect_item)

    pasted_pm = QPixmap(20, 20)
    pasted_pm.fill(QColor("blue"))
    pasted_item = PastedImageItem(pasted_pm, view)
    pasted_item.setPos(40, 50)
    scene.addItem(pasted_item)
    view.pasted_images.append(pasted_item)

    blur_item = BlurRegionItem(QRectF(70, 70, 40, 40), view, mode='inactive')
    scene.addItem(blur_item)

    original_items = {rect_item, pasted_item, blur_item}
    for it in original_items:
        it.setSelected(True)

    # Копируем и вставляем
    assert view.clipboard_controller.copy_selected() is True
    view.clipboard_controller.paste()

    # После вставки старые объекты не должны быть выделены,
    # а новые три копии — должны.
    selected = scene.selectedItems()
    new_selected = [it for it in selected if it not in original_items]
    assert len(new_selected) == 3
    assert sum(isinstance(it, RectangleItem) for it in new_selected) == 1
    assert sum(isinstance(it, PastedImageItem) for it in new_selected) == 1
    assert sum(isinstance(it, BlurRegionItem) for it in new_selected) == 1

    # Клик по вставленной зоне размытия
    inserted_blur = next(it for it in new_selected if isinstance(it, BlurRegionItem))
    pos = view.mapFromScene(inserted_blur.sceneBoundingRect().center())
    press_event = make_mouse_event(view, QEvent.MouseButtonPress, pos=pos)
    view.mousePressEvent(press_event)

    # Группа должна включать все три новых объекта
    drag_items = view.manipulation_controller._drag_items
    assert len(drag_items) == 3
    assert inserted_blur in drag_items

def test_blur_alone_still_moves_alone(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)
    view.resize(300, 300)
    pm = QPixmap(200, 200)
    pm.fill(QColor("white"))
    view.set_background_from_pixmap(pm)

    from screenshooter.items.blur_region_item import BlurRegionItem
    blur_item = BlurRegionItem(QRectF(50, 50, 40, 40), view, mode='inactive')
    scene.addItem(blur_item)
    blur_item.setSelected(True)

    pos = view.mapFromScene(blur_item.sceneBoundingRect().center())
    press_event = make_mouse_event(view, QEvent.MouseButtonPress, pos=pos)
    view.mousePressEvent(press_event)

    drag_items = view.manipulation_controller._drag_items
    assert len(drag_items) == 1
    assert drag_items[0] is blur_item    