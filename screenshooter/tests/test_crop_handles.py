"""
Тесты универсальной инфраструктуры CropHandles.
"""

import pytest
from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView

from screenshooter.items.crop_handles import CropHandles
from screenshooter.theme import ThemeManager


@pytest.fixture
def graphics_view(qapp):
    scene = QGraphicsScene()
    view = QGraphicsView(scene)
    view.resize(400, 300)
    view.show()
    qapp.processEvents()
    yield view
    view.close()


def test_create_handles_accepts_arbitrary_points(graphics_view):
    handles = CropHandles(graphics_view)
    points = {
        "start": QPointF(10, 20),
        "end": QPointF(100, 80),
        "ctrl": QPointF(55, 35),
    }

    handles.create_handles(points)

    assert set(handles.handle_items) == set(points)
    assert handles.positions == points
    assert all(item.scene() is graphics_view.scene()
               for item in handles.handle_items.values())

    handles.remove_handles()
    assert handles.handle_items == {}
    assert handles.positions == {}


def test_update_handles_accepts_arbitrary_points(graphics_view):
    handles = CropHandles(graphics_view)
    handles.create_handles({
        "start": QPointF(10, 20),
        "end": QPointF(100, 80),
    })

    updated = {
        "start": QPointF(20, 30),
        "end": QPointF(120, 90),
    }
    handles.update_handles(updated)

    assert handles.positions == updated
    assert handles.handle_items["start"].pos() == updated["start"]
    assert handles.handle_items["end"].pos() == updated["end"]


def test_legacy_rect_api_still_creates_eight_handles(graphics_view):
    handles = CropHandles(graphics_view)
    rect = QRectF(10, 20, 100, 80)

    handles.create_handles(rect)

    assert set(handles.handle_items) == {
        "tl", "tm", "tr", "lm", "rm", "bl", "bm", "br"
    }
    assert handles.positions["tl"] == rect.topLeft()
    assert handles.positions["tm"] == QPointF(rect.center().x(), rect.top())
    assert handles.positions["rm"] == QPointF(rect.right(), rect.center().y())


def test_rect_wrapper_can_hide_midpoints(graphics_view):
    handles = CropHandles(graphics_view, show_midpoints=False)
    handles.create_rect_handles(QRectF(10, 20, 100, 80))

    assert set(handles.handle_items) == {"tl", "tr", "bl", "br"}


def test_annotation_handle_theme_colors_are_defined():
    light = ThemeManager("light").get_color("annotation_handle")
    dark = ThemeManager("dark").get_color("annotation_handle")

    assert isinstance(light, QColor)
    assert isinstance(dark, QColor)
    assert light.isValid()
    assert dark.isValid()
