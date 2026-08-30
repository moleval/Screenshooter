# tests/test_history.py
import pytest
from PyQt5.QtCore import QRectF, QPointF
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtWidgets import QGraphicsScene

from screenshooter.history import (
    AddItemCommand, MoveItemCommand, MoveItemsCommand,
    ChangePenCommand, ChangeTextCommand
)
from screenshooter.items.shape_items import RectangleItem
from screenshooter.items.text_item import TextItem


@pytest.fixture
def scene(qapp):
    return QGraphicsScene()


def test_add_item_command_undo_redo(qapp, scene):
    item = RectangleItem(QRectF(0, 0, 20, 20), QPen(QColor("red"), 2))
    cmd = AddItemCommand(scene, item)

    cmd.redo()
    assert item.scene() is scene

    cmd.undo()
    assert item.scene() is None

    cmd.redo()
    assert item.scene() is scene


def test_move_item_command_undo_redo(qapp, scene):
    item = RectangleItem(QRectF(0, 0, 20, 20), QPen(QColor("red"), 2))
    scene.addItem(item)

    old_pos = QPointF(0, 0)
    new_pos = QPointF(50, 30)
    cmd = MoveItemCommand(item, old_pos, new_pos)

    cmd.redo()
    assert item.pos() == new_pos

    cmd.undo()
    assert item.pos() == old_pos

    cmd.redo()
    assert item.pos() == new_pos


def test_change_pen_command_undo_redo(qapp, scene):
    item = RectangleItem(QRectF(0, 0, 20, 20), QPen(QColor("red"), 2))
    scene.addItem(item)

    old_pen = item.pen()
    new_pen = QPen(QColor("blue"), 4)
    cmd = ChangePenCommand(item, old_pen, new_pen)

    cmd.redo()
    assert item.pen().color() == QColor("blue")
    assert item.pen().width() == 4

    cmd.undo()
    assert item.pen().color() == QColor("red")
    assert item.pen().width() == 2


def test_change_text_command_undo_redo(qapp, scene):
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QFont
    # Создаём TextItem с минимальной зависимостью view=None, bg_color=None
    item = TextItem(None, bg_color=None)
    scene.addItem(item)
    item.setPlainText("Hello")

    old_text = item.toPlainText()
    new_text = "World"
    cmd = ChangeTextCommand(item, old_text, new_text)

    cmd.redo()
    assert item.toPlainText() == "World"

    cmd.undo()
    assert item.toPlainText() == "Hello"