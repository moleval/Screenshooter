import pytest
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtWidgets import QApplication, QGraphicsScene
from screenshooter.view import EditorView
from screenshooter.items.text_item import TextItem

@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])

def make_text(view):
    item = TextItem(view)
    item.setPlainText("Rotation")
    item.setPos(100, 100)
    view.scene().addItem(item)
    item.setSelected(True)
    return item

def ev(pos=None):
    return type("Event", (), {
        "button": lambda self: Qt.LeftButton,
        "pos": lambda self: pos,
        "modifiers": lambda self: Qt.NoModifier,
    })()

def test_text_has_rotation_handle(qapp):
    view = EditorView(QGraphicsScene())
    item = make_text(view)
    controller = view.annotation_resize_controller
    controller.sync_handles()
    assert "rotate" in controller.handles.positions
    assert controller.handles.positions["rotate"].y() < item.mapToScene(item.rect().topLeft()).y()

def test_text_rotation_is_undoable(qapp):
    view = EditorView(QGraphicsScene())
    item = make_text(view)
    controller = view.annotation_resize_controller
    controller.sync_handles()
    handle = controller.handles.positions["rotate"]
    assert controller.handle_mouse_press(ev(view.mapFromScene(handle)))
    center = item.mapToScene(item.rect().center())
    assert controller.handle_mouse_move(ev(view.mapFromScene(center + QPointF(0, 80))))
    assert controller.handle_mouse_release(ev())
    assert abs(item.rotation()) > 1.0
    view.history.undo()
    assert abs(item.rotation()) < 1e-9
    view.history.redo()
    assert abs(item.rotation()) > 1.0


def test_text_rotation_handle_click_rotates_90_degrees_and_is_undoable(qapp):
    view = EditorView(QGraphicsScene())
    item = make_text(view)
    controller = view.annotation_resize_controller
    controller.sync_handles()
    handle = controller.handles.positions["rotate"]
    pos = view.mapFromScene(handle)
    assert controller.handle_mouse_press(ev(pos))
    assert controller.handle_mouse_release(ev(pos))
    assert item.rotation() == 90.0
    view.history.undo()
    assert item.rotation() == 0.0
    view.history.redo()
    assert item.rotation() == 90.0
