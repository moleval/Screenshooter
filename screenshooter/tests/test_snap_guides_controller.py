"""
Тесты Smart Snapping / Guides.
"""

import pytest

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

from screenshooter.controllers.snap_guides_controller import SnapGuidesController


class FakeImageEditor:
    def __init__(self, background_item):
        self.background_item = background_item


class FakeView(QGraphicsView):
    def __init__(self, scene, background_item):
        super().__init__(scene)
        self.image_editor = FakeImageEditor(background_item)
        self.resize(500, 400)


@pytest.fixture
def qapp():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def make_fixture(qapp):
    scene = QGraphicsScene()
    background = QGraphicsPixmapItem(QPixmap(300, 200))
    scene.addItem(background)

    view = FakeView(scene, background)
    view.show()
    qapp.processEvents()
    return view, background


def test_snap_to_background_center_shows_vertical_guide(qapp):
    view, background = make_fixture(qapp)
    item = QGraphicsRectItem(0, 0, 20, 20)
    item.setPos(50, 40)
    scene = view.scene()
    scene.addItem(item)

    controller = SnapGuidesController(view)
    controller.begin_drag([item], background)

    # Левая грань после delta=98 находится в 148, рядом с центром фона 150.
    snapped = controller.snap_delta(QPointF(98, 0))

    assert snapped.x() == pytest.approx(100)
    assert snapped.y() == pytest.approx(0)
    assert len(controller.guides) == 1

    controller.clear_guides()
    assert not controller.guides
    view.close()


def test_snap_to_other_object_center(qapp):
    view, background = make_fixture(qapp)
    item = QGraphicsRectItem(0, 0, 20, 20)
    item.setPos(50, 40)
    target = QGraphicsRectItem(0, 0, 40, 40)
    target.setPos(150, 30)
    scene = view.scene()
    scene.addItem(item)
    scene.addItem(target)

    controller = SnapGuidesController(view)
    controller.begin_drag([item], background)

    # Центр item после delta=88 равен 148, рядом с центром target=170? 
    # Здесь проверяем левую грань item: 138 рядом с target.left=150 при delta=100.
    snapped = controller.snap_delta(QPointF(98, 0))

    assert snapped.x() == pytest.approx(100)
    assert len(controller.guides) == 1

    controller.clear_guides()
    view.close()


def test_no_snap_when_outside_threshold(qapp):
    view, background = make_fixture(qapp)
    item = QGraphicsRectItem(0, 0, 20, 20)
    item.setPos(50, 40)
    view.scene().addItem(item)

    controller = SnapGuidesController(view)
    controller.begin_drag([item], background)

    snapped = controller.snap_delta(QPointF(90, 0))

    assert snapped == QPointF(90, 0)
    assert not controller.guides

    controller.clear_guides()
    view.close()
