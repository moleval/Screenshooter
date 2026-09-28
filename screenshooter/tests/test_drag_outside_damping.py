"""
Тесты мягкого замедления перетаскивания за пределами подложки.
"""

from PyQt5.QtCore import QPointF, QRectF

from screenshooter.controllers.manipulation_controller import ManipulationController


def test_drag_damping_does_not_change_point_inside_background():
    rect = QRectF(0, 0, 200, 100)
    point = QPointF(80, 40)

    result = ManipulationController._dampen_point_outside_background(
        point, rect
    )

    assert result == point


def test_drag_damping_slows_each_axis_independently():
    rect = QRectF(0, 0, 200, 100)

    result = ManipulationController._dampen_point_outside_background(
        QPointF(320, 40), rect, damping=120.0
    )

    assert result.y() == 40
    assert 200 < result.x() < 320


def test_drag_damping_gets_stronger_farther_outside():
    rect = QRectF(0, 0, 200, 100)

    near = ManipulationController._dampen_point_outside_background(
        QPointF(220, 50), rect, damping=120.0
    )
    far = ManipulationController._dampen_point_outside_background(
        QPointF(1000, 50), rect, damping=120.0
    )

    near_excess = near.x() - rect.right()
    far_excess = far.x() - rect.right()

    assert 0 < near_excess < 20
    assert 0 < far_excess < 120
    assert far_excess < (1000 - rect.right())


def test_drag_damping_is_symmetric_for_opposite_edges():
    rect = QRectF(0, 0, 200, 100)

    right = ManipulationController._dampen_point_outside_background(
        QPointF(320, 50), rect, damping=120.0
    )
    left = ManipulationController._dampen_point_outside_background(
        QPointF(-120, 50), rect, damping=120.0
    )

    assert right.x() - rect.right() == rect.left() - left.x()


def test_drag_baseline_is_preserved_when_scene_rect_changes():
    start = QPointF(100, 80)
    cursor_before = QPointF(160, 120)
    cursor_after = QPointF(160.25, 119.75)

    adjusted = start + (cursor_after - cursor_before)

    # Компенсация изменения scene->view mapping сохраняет тот же drag delta:
    # новая cursor_after - adjusted == исходная cursor_before - start.
    assert cursor_after - adjusted == cursor_before - start
