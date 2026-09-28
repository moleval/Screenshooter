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
    view.resetTransform()
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

    snapped = controller.snap_delta(QPointF(98, 0))

    # Привязка должна попасть в ближайшую ось фона с учётом реального
    # boundingRect Qt (у QGraphicsRectItem граница включает перо).
    group = item.sceneBoundingRect().translated(98, 0)
    expected = 98 + (background.sceneBoundingRect().center().x() - group.left())
    assert snapped.x() == pytest.approx(expected)
    assert snapped.y() == pytest.approx(0)
    # Линия + два перекрестья по два луча каждое.
    assert len(controller.guides) == 5

    controller.clear_guides()
    assert not controller.guides
    view.close()


def test_snap_to_other_object_center(qapp):
    view, background = make_fixture(qapp)
    item = QGraphicsRectItem(0, 0, 20, 20)
    item.setPos(50, 40)
    target = QGraphicsRectItem(0, 0, 40, 40)
    target.setPos(150, 80)
    scene = view.scene()
    scene.addItem(item)
    scene.addItem(target)

    controller = SnapGuidesController(view)
    controller.begin_drag([item], background)

    snapped = controller.snap_delta(QPointF(98, 0))

    group = item.sceneBoundingRect().translated(98, 0)
    target = target.sceneBoundingRect()
    # При таком положении ближайшим совпадением является центр цели
    # с правой гранью перемещаемого объекта.
    expected = 98 + (target.center().x() - group.right())
    assert snapped.x() == pytest.approx(expected)
    assert len(controller.guides) == 5

    controller.clear_guides()
    view.close()


def test_no_snap_when_outside_threshold(qapp):
    view, background = make_fixture(qapp)
    item = QGraphicsRectItem(0, 0, 20, 20)
    item.setPos(50, 40)
    view.scene().addItem(item)

    controller = SnapGuidesController(view)
    controller.begin_drag([item], background)

    snapped = controller.snap_delta(QPointF(70, 0))

    # Ни одна грань или центр объекта не должна попасть в порог 8 px.
    assert snapped.x() == pytest.approx(70.0)
    assert snapped.y() == pytest.approx(0.0)
    assert not controller.guides

    controller.clear_guides()
    view.close()


def test_double_axis_snap_uses_yellow_guides(qapp):
    view, background = make_fixture(qapp)
    item = QGraphicsRectItem(0, 0, 20, 20)
    item.setPos(50, 40)
    view.scene().addItem(item)

    controller = SnapGuidesController(view)
    controller.begin_drag([item], background)

    snapped = controller.snap_delta(QPointF(98, 48))

    assert snapped.x() != 98
    assert snapped.y() != 48
    assert controller.guides
    assert all(
        guide.pen().color() == controller.MULTI_SNAP_COLOR
        for guide in controller.guides
    )

    controller.clear_guides()
    view.close()
