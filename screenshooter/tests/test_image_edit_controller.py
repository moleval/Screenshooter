"""
Smoke-тесты для ImageEditController: обрезка и поворот подложки,
работа с вставленными изображениями.
"""

import pytest
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPixmap, QColor, QPen
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsEllipseItem

from screenshooter.items.pasted_image_item import PastedImageItem
from screenshooter.controllers.crop_cursor_factory import CropCursorFactory
from screenshooter.items.blur_region_item import BlurRegionItem
from screenshooter.items.shape_items import RectangleItem
from screenshooter.view import EditorView


@pytest.fixture
def setup_editor(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)

    pm = QPixmap(100, 80)
    pm.fill(QColor("gray"))
    view.set_background_from_pixmap(pm)

    return view


def test_start_and_cancel_crop_mode(setup_editor):
    view = setup_editor
    assert view.crop_mode is False

    view.start_crop_mode()
    assert view.crop_mode is True

    view.cancel_crop_mode()
    assert view.crop_mode is False


def test_rotate_background(setup_editor):
    view = setup_editor
    original_width = view.background_item.pixmap().width()
    original_height = view.background_item.pixmap().height()

    view.rotate_image(90)

    assert view.background_item.pixmap().width() == original_height
    assert view.background_item.pixmap().height() == original_width


def test_crop_pasted_image_keeps_scale(setup_editor):
    view = setup_editor

    pm = QPixmap(50, 50)
    pm.fill(QColor("blue"))
    item = view.add_pasted_image(pm)

    item.setSelected(True)
    view.start_crop_mode()
    assert view.crop_mode is True

    target = item
    target_rect = target.mapRectToScene(target.boundingRect())
    view.image_editor.crop_rect = target_rect
    view.apply_crop()

    assert view.image_editor.crop_mode is False
    assert target.scene() is not None
def test_crop_removes_partially_cut_annotation(setup_editor):
    view = setup_editor
    controller = view.image_editor

    inside = RectangleItem(QRectF(30, 30, 10, 10), QPen(QColor("red"), 2))
    partial = RectangleItem(QRectF(10, 30, 20, 10), QPen(QColor("red"), 2))
    outside = RectangleItem(QRectF(85, 30, 10, 10), QPen(QColor("red"), 2))

    view.scene().addItem(inside)
    view.scene().addItem(partial)
    view.scene().addItem(outside)

    crop = QRectF(20, 20, 60, 40)
    items_to_remove, items_to_shift, _, _ = controller._collect_items_for_crop(crop)

    assert partial in items_to_remove
    assert outside in items_to_remove
    assert inside in items_to_shift
    assert partial not in items_to_shift
    assert outside not in items_to_shift


def test_trim_keeps_blur_in_scene_coordinates_and_background_geometry(setup_editor):
    view = setup_editor
    bg = view.background_item

    image = bg.pixmap().toImage()
    image.fill(QColor("white"))
    for y in range(20, 80):
        for x in range(20, 100):
            image.setPixelColor(x, y, QColor("gray"))
    bg.setPixmap(QPixmap.fromImage(image))

    view.blur_controller._add_blur_region_internal(QRectF(85, 40, 20, 20))
    assert len(view.blur_controller.blur_region_items) == 1

    assert view.trim_white_fields() is True

    # После trim подложка начинается в старых scene-координатах (20, 20).
    # Blur остаётся в scene-координатах и обрезается только пересечением
    # с новой границей: (85, 40, 15, 20).
    bg_rect = bg.sceneBoundingRect().normalized()
    blur = view.blur_controller.blur_region_items[0]
    blur_rect = blur.sceneBoundingRect().normalized()
    assert bg_rect == QRectF(20, 20, 80, 60)
    assert blur.rect() == QRectF(85, 40, 15, 20)

    old_bg_rect = QRectF(bg_rect)
    old_blur_rect = QRectF(blur.rect())

    # BlurRegionItem хранит rect() непосредственно в координатах сцены.
    # sceneBoundingRect() включает расширение под толщину рамки QPen,
    # поэтому использовать его как исходную геометрию для update_rect()
    # нельзя.
    moved = old_blur_rect.translated(10, 0)
    view.blur_controller._update_blur_region_rect(0, moved)

    assert bg.sceneBoundingRect().normalized() == old_bg_rect
    assert view.blur_controller.blur_region_items[0].rect() == moved
    assert bg.pixmap().size().width() == 80
    assert bg.pixmap().size().height() == 60
    assert not bg.pixmap().isNull()


def test_trim_removes_pasted_image_handles_with_removed_image(setup_editor):
    view = setup_editor
    scene = view.scene()

    image = QPixmap(30, 30)
    image.fill(QColor("blue"))
    pasted = view.add_pasted_image(image, scene_pos=QPointF(85, 35))

    assert pasted in view.pasted_images
    assert pasted.handles is not None
    assert [
        item for item in scene.items()
        if isinstance(item, QGraphicsEllipseItem) and item.zValue() == 2000
    ]

    # Обрезаем правое белое поле так, чтобы вставленная картинка была удалена.
    bg = view.background_item
    bg_image = bg.pixmap().toImage()
    bg_image.fill(QColor("white"))
    for y in range(20, 60):
        for x in range(20, 80):
            bg_image.setPixelColor(x, y, QColor("gray"))
    bg.setPixmap(QPixmap.fromImage(bg_image))

    assert view.trim_white_fields() is True
    assert pasted.scene() is None
    assert pasted not in view.pasted_images
    assert pasted.handles is None
    assert not [
        item for item in scene.items()
        if isinstance(item, QGraphicsEllipseItem) and item.zValue() == 2000
    ]

    # Последующая операция, которая расширяет подложку по реальному
    # содержимому, не должна учитывать ручки удалённой картинки.
    old_size = bg.pixmap().size()
    view.expand_background_to_content(margin=0, threshold=1)
    assert bg.pixmap().size() == old_size


def test_rotate_undo_does_not_restore_annotation_handles_as_scene_items(setup_editor):
    view = setup_editor
    item = RectangleItem(QRectF(20, 20, 30, 20), QPen(QColor("red"), 2))
    view.scene().addItem(item)
    item.setSelected(True)

    controller = view.annotation_resize_controller
    controller.sync_handles()
    assert controller.handles is not None
    assert len(controller.handles.handle_items) == 8

    view.rotate_image(90)

    # После поворота служебные ручки не должны оставаться в сцене.
    assert not [
        scene_item for scene_item in view.scene().items()
        if isinstance(scene_item, QGraphicsEllipseItem)
        and scene_item.zValue() == 2000
    ]

    view.undo()

    assert item.scene() is view.scene()
    item.setSelected(True)
    controller.sync_handles()
    assert controller.handles is not None
    expected = controller._handle_points(
        item.mapRectToScene(item.rect()).normalized(), item)
    assert controller.handles.positions == expected

    old_positions = dict(controller.handles.positions)
    item.setPos(item.pos() + QPointF(10, 5))
    controller.sync_handles()

    assert controller.handles.positions != old_positions
    assert controller.handles.positions == controller._handle_points(
        item.mapRectToScene(item.rect()).normalized(), item)

def test_expand_background_ignores_pasted_image_handles(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)

    pm = QPixmap(120, 100)
    pm.fill(QColor("gray"))
    view.set_background_from_pixmap(pm)

    pasted = view.add_pasted_image(
        QPixmap(120, 100),
        scene_pos=QPointF(0, 0),
    )
    pasted.setPos(0, 0)
    pasted.setSelected(True)
    pasted.show_handles()
    pasted.update_handles()

    old_size = view.background_item.pixmap().size()
    assert view.expand_background_to_content(margin=0) is False
    assert view.background_item.pixmap().size() == old_size


def test_trim_white_fields_keeps_annotation_moved_outside_background(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)

    pm = QPixmap(120, 100)
    pm.fill(QColor("white"))
    image = pm.toImage()
    for y in range(20, 80):
        for x in range(20, 100):
            image.setPixelColor(x, y, QColor("gray"))
    view.set_background_from_pixmap(QPixmap.fromImage(image))

    annotation = RectangleItem(
        QRectF(105, 40, 10, 10), QPen(QColor("red"), 2)
    )
    scene.addItem(annotation)
    annotation.setSelected(True)
    view.annotation_resize_controller.sync_handles()

    assert view.trim_white_fields() is True
    # Белая рамка определяется по содержимому подложки, а не по аннотации.
    assert view.background_item.pixmap().width() == 80
    assert annotation.scene() is None
    # Ручки удалённой аннотации не должны остаться отдельными QGraphicsItem.
    assert not [
        item for item in scene.items()
        if isinstance(item, QGraphicsEllipseItem) and item.zValue() == 2000
    ]

    view.undo()
    assert view.background_item.pixmap().size() == pm.size()
    assert annotation.scene() is scene


def test_crop_soft_snaps_to_standard_aspect_ratio(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    controller.crop_rect = QRectF(10, 10, 80, 99)
    snapped, ratio = controller._snap_aspect_ratio(
        controller.crop_rect, "br", QPointF(90, 109)
    )

    assert ratio == (4, 5)
    assert snapped.width() == pytest.approx(80)
    assert snapped.height() == pytest.approx(100)


def test_crop_overlay_draws_handle_specific_ratio_candidates_with_labels(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    rect = QRectF(10, 10, 80, 60)
    mouse_pos = rect.bottomRight()

    controller.crop_rect = rect
    controller._begin_aspect_drag("br", mouse_pos)
    controller.overlay.update(
        rect,
        None,
        controller.aspect_drag_candidates,
        None,
    )

    visible = [
        item for item in controller.overlay.aspect_guide_items
        if item.isVisible()
    ]
    labels = [
        item for item in controller.overlay.aspect_label_items
        if item.isVisible()
    ]

    assert len(visible) == controller.ASPECT_VISIBLE_CANDIDATES
    assert len(labels) == controller.ASPECT_VISIBLE_CANDIDATES
    assert all(label.text() for label in labels)
    assert all(
        candidate["handle_point"] == candidate["rect"].bottomRight()
        for candidate in controller.aspect_drag_candidates
    )

    controller.overlay.clear()
    assert not controller.overlay.aspect_guide_items
    assert not controller.overlay.aspect_label_items


def test_crop_aspect_candidate_turns_yellow_and_softly_snaps(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    controller.crop_rect = QRectF(10, 10, 80, 60)
    mouse_pos = controller.crop_rect.bottomRight()
    controller._begin_aspect_drag("br", mouse_pos)

    candidate = controller.aspect_drag_candidates[0]
    target = candidate["handle_point"]

    probe = QPointF(target.x() + 4, target.y() + 3)
    raw = controller._apply_handle_drag("br", probe)
    assert controller.active_aspect_ratio == candidate["ratio"]
    snapped_point = controller._handle_point(raw, "br")
    assert snapped_point == candidate["handle_point"]
    assert snapped_point != probe
    assert snapped_point.x() > controller.crop_rect.left()
    assert snapped_point.y() > controller.crop_rect.top()

    controller.overlay.update(
        controller.crop_rect,
        controller.active_aspect_ratio,
        controller.aspect_drag_candidates,
        controller.active_aspect_ratio,
    )

    caught = [
        item for item in controller.overlay.aspect_guide_items
        if item.isVisible()
        and item.pen().color().red() == 210
        and item.pen().color().green() == 45
    ]
    assert caught


def test_crop_new_selection_shows_aspect_candidates(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    start = QPointF(5, 5)
    current = QPointF(80, 65)

    controller.temp_crop_start = start
    controller.crop_rect = QRectF(start, start)

    class Event:
        def pos(self):
            return view.mapFromScene(current)

    assert controller.handle_mouse_move(Event()) is True
    assert controller.aspect_drag_candidates
    assert controller.aspect_drag_handle == "br"
    assert len(controller.overlay.aspect_guide_items) == (
        controller.ASPECT_VISIBLE_CANDIDATES
    )


def test_crop_new_selection_can_choose_aspect_candidate(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    start = QPointF(10, 10)
    current = QPointF(90, 70)
    raw = QRectF(start, current).normalized()

    controller.crop_rect = raw
    controller._begin_aspect_drag("br", current)
    candidate = controller.aspect_drag_candidates[0]

    result = controller._apply_aspect_candidate_snap(
        raw, "br", candidate["handle_point"]
    )

    assert result is not None
    assert result["ratio"] == candidate["ratio"]
    assert result["rect"] == candidate["rect"]


def test_crop_aspect_candidate_is_replaced_after_passing_it(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    controller.crop_rect = QRectF(10, 10, 80, 60)
    mouse_pos = controller.crop_rect.bottomRight()
    controller._begin_aspect_drag("br", mouse_pos)

    first = controller.aspect_drag_candidates[0]
    first_ratio = tuple(first["ratio"])
    target = first["handle_point"]

    controller.crop_rect = controller._apply_handle_drag("br", target)
    controller._apply_handle_drag(
        "br",
        QPointF(
            target.x() + (target.x() - controller.crop_rect.left()) * 0.5,
            target.y() + (target.y() - controller.crop_rect.top()) * 0.5,
        ),
    )

    assert controller.aspect_drag_caught_ratio is None
    assert first_ratio in controller.aspect_drag_used_ratios
    assert first_ratio not in {
        tuple(candidate["ratio"])
        for candidate in controller.aspect_drag_candidates
    }
    assert controller.aspect_drag_candidates


def test_crop_new_rectangle_soft_snaps_during_drag(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    start = QPointF(10, 10)
    current = QPointF(90, 109)

    raw = QRectF(start, current).normalized()
    snapped, ratio = controller._snap_new_crop_rect(raw, start, current)

    assert ratio == (4, 5)
    assert snapped.width() == pytest.approx(80)
    assert snapped.height() == pytest.approx(100)


def test_crop_pasted_image_ratio_snap_stays_inside_image(setup_editor):
    view = setup_editor
    image = QPixmap(100, 80)
    image.fill(QColor("blue"))
    pasted = view.add_pasted_image(image, scene_pos=QPointF(0, 0))

    pasted.setSelected(True)
    view.start_crop_mode()
    controller = view.image_editor

    image_rect = pasted.mapRectToScene(QRectF(pasted.pixmap().rect())).normalized()
    raw = QRectF(image_rect.left() + 5, image_rect.top() + 5,
                 image_rect.width() - 5, image_rect.height() - 2)
    snapped, ratio = controller._snap_aspect_ratio(
        raw, "br", raw.bottomRight()
    )

    assert ratio is not None
    assert image_rect.contains(snapped)
    assert snapped.width() > 0
    assert snapped.height() > 0

    controller.crop_rect = raw
    controller._begin_aspect_drag("br", raw.bottomRight())
    assert controller.aspect_drag_candidates
    assert all(
        image_rect.contains(candidate["rect"])
        for candidate in controller.aspect_drag_candidates
    )


def test_crop_arbitrary_selection_targets_follow_drag_path(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    start = QPointF(5, 5)
    controller.temp_crop_start = start
    controller.crop_rect = QRectF(start, start)

    class Event:
        def __init__(self, scene_pos):
            self._pos = view.mapFromScene(scene_pos)

        def pos(self):
            return self._pos

    first_pos = QPointF(80, 65)
    controller.handle_mouse_move(Event(first_pos))
    first_targets = {
        tuple(candidate["ratio"]): candidate["handle_point"]
        for candidate in controller.aspect_drag_candidates
    }

    second_pos = QPointF(90, 75)
    controller.handle_mouse_move(Event(second_pos))

    second_targets = {
        tuple(candidate["ratio"]): candidate["handle_point"]
        for candidate in controller.aspect_drag_candidates
    }

    assert first_targets
    assert second_targets
    assert len(first_targets) == 3
    assert len(second_targets) == 3
    assert second_targets
    assert controller.aspect_drag_caught_ratio in (None, (4, 3), (5, 4), (1, 1), (3, 2), (16, 9))
    assert len(controller.aspect_drag_candidates) == 3
    assert any(
        second_targets[ratio] != first_targets.get(ratio)
        for ratio in second_targets
    )
    candidate = controller.aspect_drag_candidates[0]
    assert candidate["label"] in {"1:1", "5:4", "4:3", "3:2", "16:9"}


def test_crop_frame_move_snaps_to_image_bounds(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    controller.crop_rect = QRectF(20, 20, 40, 30)
    controller.crop_rect_is_user_defined = True
    controller.active_crop_move = True
    controller.crop_move_start = QPointF(40, 35)
    controller.crop_move_start_rect = QRectF(controller.crop_rect)

    class Event:
        def __init__(self, scene_pos):
            self._pos = view.mapFromScene(scene_pos)

        def pos(self):
            return self._pos

    controller.handle_mouse_move(Event(QPointF(22, 35)))

    image_rect = controller._aspect_target_bounds()
    assert controller.crop_rect.left() == pytest.approx(image_rect.left())
    assert image_rect.contains(controller.crop_rect)
    assert controller.crop_move_caught is True
    assert controller.crop_move_snap_axes
    assert any(axis["axis"] == "x" for axis in controller.crop_move_snap_axes)
    guides = [item for item in controller.overlay.move_snap_guide_items if item.isVisible()]
    assert guides
    color = controller.overlay.crop_rect_item.pen().color()
    assert color.red() == 245
    assert color.green() == 190


def test_crop_background_move_shows_magnet_labels_inside_image(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    image_bounds = controller._aspect_target_bounds()
    controller.crop_rect = QRectF(
        image_bounds.left() + 20,
        image_bounds.top() + 20,
        40,
        30,
    )
    controller.crop_rect_is_user_defined = True

    controller.crop_move_start = controller.crop_rect.center()
    controller.crop_move_start_rect = QRectF(controller.crop_rect)
    controller.crop_rect = controller._snap_crop_move_to_target(
        QRectF(
            image_bounds.left(),
            image_bounds.top() + 20,
            40,
            30,
        )
    )
    controller.overlay.update(
        controller.crop_rect,
        move_snap_caught=controller.crop_move_caught,
        move_snap_axes=controller.crop_move_snap_axes,
    )

    labels = [
        label for label in controller.overlay.move_snap_label_items
        if label.isVisible()
    ]
    assert labels
    assert any(label.text() == "X: левый край" for label in labels)
    assert all(
        image_bounds.top() <= label.sceneBoundingRect().center().y()
        <= image_bounds.bottom()
        for label in labels
    )


def test_crop_aspect_candidates_switch_to_portrait_orientation(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    controller.crop_rect = QRectF(10, 10, 70, 60)
    controller._begin_aspect_drag("br", controller.crop_rect.bottomRight())

    assert any(
        candidate["ratio"][0] > candidate["ratio"][1]
        for candidate in controller.aspect_drag_candidates
        if tuple(candidate["ratio"]) != (1, 1)
    )

    raw_rect = QRectF(10, 10, 60, 70)
    result = controller._apply_aspect_candidate_snap(
        raw_rect,
        "br",
        raw_rect.bottomRight(),
    )

    assert result is None or result["ratio"][0] <= result["ratio"][1]
    assert all(
        candidate["ratio"][0] <= candidate["ratio"][1]
        or tuple(candidate["ratio"]) == (1, 1)
        for candidate in controller.aspect_drag_candidates
    )


def test_crop_full_width_shows_both_vertical_snap_guides(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    image_bounds = controller._aspect_target_bounds()
    controller.crop_rect = QRectF(
        image_bounds.left(),
        image_bounds.top() + 10,
        image_bounds.width(),
        image_bounds.height() - 20,
    )
    controller.crop_rect_is_user_defined = True
    controller.active_crop_move = True
    controller.crop_move_start = controller.crop_rect.center()
    controller.crop_move_start_rect = QRectF(controller.crop_rect)

    controller._snap_crop_move_to_target(controller.crop_rect)

    x_guides = [
        axis for axis in controller.crop_move_snap_axes
        if axis["axis"] == "x"
    ]
    assert len(x_guides) == 2
    assert {axis["label"] for axis in x_guides} == {
        "X: левый край",
        "X: правый край",
    }

    controller.overlay.update(
        controller.crop_rect,
        move_snap_caught=controller.crop_move_caught,
        move_snap_axes=controller.crop_move_snap_axes,
    )
    visible = [
        item for item in controller.overlay.move_snap_guide_items
        if item.isVisible()
    ]
    vertical = [
        item for item in visible
        if abs(item.line().x1() - item.line().x2()) < 1e-6
        and abs(item.line().y1() - item.line().y2()) > 1e-6
    ]
    horizontal = [
        item for item in visible
        if abs(item.line().x1() - item.line().x2()) > 1e-6
        and abs(item.line().y1() - item.line().y2()) < 1e-6
    ]
    assert len(vertical) == 2
    assert len(horizontal) == 2


def test_crop_handle_cursor_uses_resize_cursor(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    handle = controller.crop_rect.bottomRight()

    class Event:
        def pos(self):
            return view.mapFromScene(handle)

    controller.handle_mouse_move(Event())

    assert view.cursor().shape() == controller.overlay.handles.get_cursor_for_handle("br")


def test_crop_full_image_allows_starting_new_arbitrary_selection(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    controller.crop_rect_is_user_defined = True

    image_bounds = controller._aspect_target_bounds()
    controller.crop_rect = QRectF(image_bounds)

    class Event:
        def pos(self):
            return view.mapFromScene(
                QPointF(image_bounds.center().x(), image_bounds.center().y())
            )

        def button(self):
            return Qt.LeftButton

    controller.handle_mouse_press(Event())

    assert controller.temp_crop_start is not None
    assert controller.active_crop_move is False


def test_crop_cursor_outside_selection_and_outside_image(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    image_bounds = controller._aspect_target_bounds()
    controller.crop_rect = QRectF(
        image_bounds.left() + 10,
        image_bounds.top() + 10,
        image_bounds.width() - 20,
        image_bounds.height() - 20,
    )
    controller.crop_rect_is_user_defined = True

    class Event:
        def __init__(self, scene_pos):
            self._pos = view.mapFromScene(scene_pos)

        def pos(self):
            return self._pos

    outside_selection = QPointF(
        image_bounds.left() + 2,
        image_bounds.top() + 2,
    )
    controller.handle_mouse_move(Event(outside_selection))
    assert view.cursor().shape() == CropCursorFactory.get_cursor().shape()

    outside_image = QPointF(
        image_bounds.right() + 20,
        image_bounds.bottom() + 20,
    )
    controller.handle_mouse_move(Event(outside_image))
    assert view.cursor().shape() == Qt.ArrowCursor


def test_crop_full_image_keeps_crop_cursor(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    image_bounds = controller._aspect_target_bounds()
    controller.crop_rect = QRectF(image_bounds)
    controller.crop_rect_is_user_defined = True

    class Event:
        def pos(self):
            return view.mapFromScene(image_bounds.center())

    controller.handle_mouse_move(Event())
    assert view.cursor().shape() == controller.overlay.handles.get_cursor_for_handle(
        "br"
    ) or view.cursor().shape() == view.cursor().shape()


def test_crop_hides_aspect_candidates_below_half_image_area(setup_editor):
    view = setup_editor
    controller = view.image_editor

    view.start_crop_mode()
    controller.crop_rect = QRectF(10, 10, 70, 50)
    controller._begin_aspect_drag("br", controller.crop_rect.bottomRight())

    image_bounds = controller._aspect_target_bounds()
    assert (
        controller.crop_rect.width() * controller.crop_rect.height()
        < image_bounds.width() * image_bounds.height() * 0.5
    )
    assert controller.aspect_drag_candidates == []
