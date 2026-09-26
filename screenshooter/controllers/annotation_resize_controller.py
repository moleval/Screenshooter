"""
Модуль: controllers/annotation_resize_controller.py
Описание: изменение размера аннотаций через универсальные ручки.
"""

import math

from PyQt5 import sip
from PyQt5.QtCore import Qt, QPointF, QRectF

from ..constants import MIN_RECT_SIZE, MIN_ARROW_LENGTH, MIN_SCALE
from ..history import ResizeAnnotationCommand
from ..items import (
    EllipseItem, FilledRectItem, RectangleItem, CloudItem,
    LineItem, WavyLineItem, ArrowItem, CurvedArrowItem, DimensionItem, TextItem,
)
from ..items.crop_handles import CropHandles
from ..theme import theme_manager


class AnnotationResizeController:
    """Единственная точка входа для resize аннотаций."""

    RECT_HANDLES = ('tl', 'tm', 'tr', 'lm', 'rm', 'bl', 'bm', 'br')
    ELLIPSE_HANDLES = RECT_HANDLES
    LINE_HANDLES = ('start', 'end')
    CURVED_HANDLES = ('start', 'end', 'ctrl')
    TEXT_HANDLES = ('tl', 'tr', 'bl', 'br')
    RECT_ITEMS = (RectangleItem, FilledRectItem, CloudItem)
    LINE_ITEMS = (LineItem, WavyLineItem, ArrowItem, DimensionItem)

    def __init__(self, view):
        self.view = view
        self.handles = None
        self._item = None
        self._handle_id = None
        self._start_scene_rect = None
        self._start_local_rect = None
        self._start_anchor = None
        self._old_rect = None
        self._old_pos = None
        self._start_geometry = None
        self._start_scale = None
        self._text_anchor_local = None
        self._text_moving_local = None
        self._text_anchor_scene = None
        self._text_original_vector = None
        self._rotation_start = None
        self._rotation_start_angle = None
        self._rotation_press_pos = None

    def _blocked_by_mode(self) -> bool:
        return bool(
            self.view.blur_controller.blur_mode
            or self.view.image_editor.crop_mode
        )

    def _selected_annotation(self):
        selected = self.view.scene().selectedItems()
        annotations = [
            item for item in selected
            if isinstance(
                item,
                (
                    RectangleItem, FilledRectItem, CloudItem, EllipseItem,
                    LineItem, WavyLineItem, ArrowItem, CurvedArrowItem, DimensionItem, TextItem,
                ),
            )
            and not sip.isdeleted(item)
            and item.scene() is self.view.scene()
        ]
        return annotations[0] if len(annotations) == 1 else None

    @staticmethod
    def _handle_points(scene_rect, item):
        return {
            'tl': scene_rect.topLeft(),
            'tm': QPointF(scene_rect.center().x(), scene_rect.top()),
            'tr': scene_rect.topRight(),
            'lm': QPointF(scene_rect.left(), scene_rect.center().y()),
            'rm': QPointF(scene_rect.right(), scene_rect.center().y()),
            'bl': scene_rect.bottomLeft(),
            'bm': QPointF(scene_rect.center().x(), scene_rect.bottom()),
            'br': scene_rect.bottomRight(),
        }

    @staticmethod
    def _line_geometry(item):
        if isinstance(item, LineItem):
            line = item.line()
            return line.p1(), line.p2()
        if isinstance(item, WavyLineItem):
            return QPointF(item._x1, item._y1), QPointF(item._x2, item._y2)
        if isinstance(item, ArrowItem):
            return QPointF(item._start), QPointF(item._end)
        if isinstance(item, DimensionItem):
            return QPointF(item._start), QPointF(item._end)
        raise TypeError(f"Unsupported line annotation: {type(item).__name__}")

    def _scene_line_geometry(self, item):
        start, end = self._line_geometry(item)
        return item.mapToScene(start), item.mapToScene(end)

    @staticmethod
    def _curve_geometry(item):
        if isinstance(item, CurvedArrowItem):
            return QPointF(item._start), QPointF(item._end), QPointF(item._ctrl)
        raise TypeError(f"Unsupported curved annotation: {type(item).__name__}")

    def _scene_curve_geometry(self, item):
        start, end, ctrl = self._curve_geometry(item)
        return item.mapToScene(start), item.mapToScene(end), item.mapToScene(ctrl)

    def _curve_handle_points(self, item):
        start, end, ctrl = self._scene_curve_geometry(item)
        return {'start': start, 'end': end, 'ctrl': ctrl}

    @staticmethod
    def _text_handle_points(item):
        rect = item.rect()
        corners = {
            'tl': rect.topLeft(),
            'tr': rect.topRight(),
            'bl': rect.bottomLeft(),
            'br': rect.bottomRight(),
        }
        return {key: item.mapToScene(point) for key, point in corners.items()}

    def _text_rotation_handle_point(self, item):
        rect = item.rect()
        zoom = max(abs(self.view.transform().m11()), 1e-6)
        scale = max(abs(item.scale()), 1e-6)
        offset = 24.0 / (zoom * scale)
        return item.mapToScene(QPointF(rect.center().x(), rect.top() - offset))

    def _text_rotation_handle_point(self, item):
        rect = item.rect()
        zoom = max(abs(self.view.transform().m11()), 1e-6)
        scale = max(abs(item.scale()), 1e-6)
        offset = 24.0 / (zoom * scale)
        return item.mapToScene(QPointF(rect.center().x(), rect.top() - offset))

    def _line_handle_points(self, item):
        start, end = self._scene_line_geometry(item)
        return {'start': start, 'end': end}

    def sync_handles(self):
        """Показывает ручки для единственной выбранной поддерживаемой аннотации."""
        if self._blocked_by_mode():
            self.remove_handles()
            return

        item = self._selected_annotation()
        if item is None:
            self.remove_handles()
            return

        if isinstance(item, TextItem):
            if item._editable:
                self.remove_handles()
                return
            points = self._text_handle_points(item)
            points['rotate'] = self._text_rotation_handle_point(item)
            show_midpoints = False
        elif isinstance(item, CurvedArrowItem):
            points = self._curve_handle_points(item)
            show_midpoints = False
        elif isinstance(item, self.LINE_ITEMS):
            points = self._line_handle_points(item)
            show_midpoints = False
        else:
            scene_rect = item.mapRectToScene(item.rect()).normalized()
            points = self._handle_points(scene_rect, item)
            show_midpoints = True

        if self.handles is None or self._item is not item:
            self.remove_handles()
            self.handles = CropHandles(
                self.view,
                fill_color=theme_manager.get_color('annotation_handle'),
                show_midpoints=show_midpoints,
            )
            self._item = item
            self.handles.create_handles(points)
        else:
            self.handles.update_handles(points)

    def remove_handles(self):
        if self.handles is not None:
            self.handles.remove_handles()
        self.handles = None
        self._item = None

    def _hit_test(self, event):
        if self.handles is None:
            self.sync_handles()
        if self.handles is None:
            return None
        return self.handles.hit_test(QPointF(event.pos()))

    @staticmethod
    def _anchor_for_handle(rect, handle_id):
        anchors = {
            'tl': rect.bottomRight(),
            'tm': QPointF(rect.center().x(), rect.bottom()),
            'tr': rect.bottomLeft(),
            'lm': QPointF(rect.right(), rect.center().y()),
            'rm': QPointF(rect.left(), rect.center().y()),
            'bl': rect.topRight(),
            'bm': QPointF(rect.center().x(), rect.top()),
            'br': rect.topLeft(),
        }
        return anchors.get(handle_id)

    def _resize_scene_rect(self, old_rect, handle_id, cursor_pos):
        left, right = old_rect.left(), old_rect.right()
        top, bottom = old_rect.top(), old_rect.bottom()

        if 'l' in handle_id:
            left = min(cursor_pos.x(), right - MIN_RECT_SIZE)
        elif 'r' in handle_id:
            right = max(cursor_pos.x(), left + MIN_RECT_SIZE)

        if 't' in handle_id:
            top = min(cursor_pos.y(), bottom - MIN_RECT_SIZE)
        elif 'b' in handle_id:
            bottom = max(cursor_pos.y(), top + MIN_RECT_SIZE)

        if handle_id in ('tm', 'bm'):
            left, right = old_rect.left(), old_rect.right()
        if handle_id in ('lm', 'rm'):
            top, bottom = old_rect.top(), old_rect.bottom()

        return QRectF(QPointF(left, top), QPointF(right, bottom)).normalized()

    def _clamp_to_background(self, rect, anchor, handle_id):
        bg = self.view.image_editor.background_item
        if bg is None or sip.isdeleted(bg):
            return rect

        bg_rect = bg.mapRectToScene(QRectF(bg.pixmap().rect())).normalized()
        left, right = rect.left(), rect.right()
        top, bottom = rect.top(), rect.bottom()

        if handle_id in ('tl', 'lm', 'bl'):
            left = max(bg_rect.left(), left)
        if handle_id in ('tr', 'rm', 'br'):
            right = min(bg_rect.right(), right)
        if handle_id in ('tl', 'tm', 'tr'):
            top = max(bg_rect.top(), top)
        if handle_id in ('bl', 'bm', 'br'):
            bottom = min(bg_rect.bottom(), bottom)

        if handle_id in ('lm', 'rm'):
            top, bottom = self._start_scene_rect.top(), self._start_scene_rect.bottom()
        if handle_id in ('tm', 'bm'):
            left, right = self._start_scene_rect.left(), self._start_scene_rect.right()

        if anchor is not None:
            if handle_id in ('tl', 'tr', 'bl', 'br'):
                if anchor.x() <= left:
                    left = anchor.x()
                if anchor.x() >= right:
                    right = anchor.x()
                if anchor.y() <= top:
                    top = anchor.y()
                if anchor.y() >= bottom:
                    bottom = anchor.y()
            elif handle_id in ('lm', 'rm'):
                top = anchor.y() - self._start_scene_rect.height() / 2
                bottom = anchor.y() + self._start_scene_rect.height() / 2
            elif handle_id in ('tm', 'bm'):
                left = anchor.x() - self._start_scene_rect.width() / 2
                right = anchor.x() + self._start_scene_rect.width() / 2

        return QRectF(QPointF(left, top), QPointF(right, bottom)).normalized()

    @staticmethod
    def _clamp_point_to_rect(point, rect):
        return QPointF(
            min(max(point.x(), rect.left()), rect.right()),
            min(max(point.y(), rect.top()), rect.bottom()),
        )

    def _background_scene_rect(self):
        bg = self.view.image_editor.background_item
        if bg is None or sip.isdeleted(bg):
            return None
        return bg.mapRectToScene(QRectF(bg.pixmap().rect())).normalized()

    @staticmethod
    def _orthogonalize_endpoint(anchor, point):
        """Фиксирует перемещаемую точку по горизонтали или вертикали."""
        dx = point.x() - anchor.x()
        dy = point.y() - anchor.y()
        if abs(dx) >= abs(dy):
            return QPointF(point.x(), anchor.y())
        return QPointF(anchor.x(), point.y())

    def _resize_line_geometry(self, start, end, handle_id, cursor_scene,
                              orthogonal=False):
        anchor = end if handle_id == 'start' else start
        moving = QPointF(cursor_scene)
        if orthogonal:
            moving = self._orthogonalize_endpoint(anchor, moving)
        moving = self._clamp_point_to_rect(moving, self._background_scene_rect()) \
            if self._background_scene_rect() is not None else moving

        dx = moving.x() - anchor.x()
        dy = moving.y() - anchor.y()
        length = math.hypot(dx, dy)
        if length < MIN_ARROW_LENGTH:
            old_dx = (start.x() - end.x()) if handle_id == 'start' else (end.x() - start.x())
            old_dy = (start.y() - end.y()) if handle_id == 'start' else (end.y() - start.y())
            old_len = math.hypot(old_dx, old_dy)
            if old_len < 1e-9:
                old_dx, old_dy, old_len = (MIN_ARROW_LENGTH, 0.0, MIN_ARROW_LENGTH)
            dx = old_dx / old_len * MIN_ARROW_LENGTH
            dy = old_dy / old_len * MIN_ARROW_LENGTH
            moving = QPointF(anchor.x() + dx, anchor.y() + dy)
            bg_rect = self._background_scene_rect()
            if bg_rect is not None:
                moving = self._clamp_point_to_rect(moving, bg_rect)
                dx = moving.x() - anchor.x()
                dy = moving.y() - anchor.y()
                length = math.hypot(dx, dy)
                if length < MIN_ARROW_LENGTH:
                    # У границы подложки минимальную длину физически обеспечить
                    # невозможно; сохраняем допустимую точку внутри подложки.
                    moving = self._clamp_point_to_rect(moving, bg_rect)
        return (moving, anchor) if handle_id == 'start' else (anchor, moving)

    @staticmethod
    def _text_opposite_handle(handle_id):
        return {
            'tl': 'br',
            'tr': 'bl',
            'bl': 'tr',
            'br': 'tl',
        }.get(handle_id)

    def _resize_text(self, item, handle_id, cursor_scene):
        # Геометрия resize фиксируется в момент press. Нельзя каждый move
        # заново брать rect()/anchor из уже масштабированного
        # QGraphicsTextItem: небольшие изменения boundingRect/document layout
        # иначе превращаются в визуальную рябь и дрожание точки привязки.
        anchor_local = self._text_anchor_local
        moving_local = self._text_moving_local
        anchor_scene = self._text_anchor_scene
        original_vector = self._text_original_vector

        if (
            anchor_local is None
            or moving_local is None
            or anchor_scene is None
            or original_vector is None
        ):
            return

        denominator = (
            original_vector.x() ** 2 + original_vector.y() ** 2
        )
        if denominator < 1e-9:
            return

        cursor_vector = QPointF(cursor_scene) - anchor_scene
        scale_factor = (
            cursor_vector.x() * original_vector.x()
            + cursor_vector.y() * original_vector.y()
        ) / denominator
        new_scale = max(MIN_SCALE, self._start_scale * scale_factor)

        item.setScale(new_scale)

        # После setScale вычисляем только фактический сдвиг позиции,
        # необходимый для возврата исходной scene-точки якоря. Сам якорь
        # и исходный вектор при этом не меняются от кадра к кадру.
        current_anchor = item.mapToScene(anchor_local)
        item.setPos(item.pos() + (anchor_scene - current_anchor))

    def _resize_curve_geometry(self, start, end, ctrl, handle_id, cursor_scene):
        bg_rect = self._background_scene_rect()
        moving = self._clamp_point_to_rect(cursor_scene, bg_rect) if bg_rect is not None else QPointF(cursor_scene)
        if handle_id == 'ctrl':
            return start, end, moving

        anchor = end if handle_id == 'start' else start
        dx, dy = moving.x() - anchor.x(), moving.y() - anchor.y()
        length = math.hypot(dx, dy)
        if length < MIN_ARROW_LENGTH:
            old_dx = start.x() - end.x() if handle_id == 'start' else end.x() - start.x()
            old_dy = start.y() - end.y() if handle_id == 'start' else end.y() - start.y()
            old_len = math.hypot(old_dx, old_dy)
            if old_len < 1e-9:
                old_dx, old_dy, old_len = MIN_ARROW_LENGTH, 0.0, MIN_ARROW_LENGTH
            moving = QPointF(anchor.x() + old_dx / old_len * MIN_ARROW_LENGTH,
                             anchor.y() + old_dy / old_len * MIN_ARROW_LENGTH)
            if bg_rect is not None:
                moving = self._clamp_point_to_rect(moving, bg_rect)

        return (moving, end, ctrl) if handle_id == 'start' else (start, moving, ctrl)

    def _apply_scene_curve_geometry(self, item, scene_start, scene_end, scene_ctrl):
        item.set_curve(
            item.mapFromScene(scene_start),
            item.mapFromScene(scene_end),
            item.mapFromScene(scene_ctrl),
        )

    def _apply_scene_line_geometry(self, item, scene_start, scene_end):
        local_start = item.mapFromScene(scene_start)
        local_end = item.mapFromScene(scene_end)
        if isinstance(item, LineItem):
            item.setLine(local_start.x(), local_start.y(), local_end.x(), local_end.y())
        elif isinstance(item, WavyLineItem):
            item.set_points(local_start.x(), local_start.y(), local_end.x(), local_end.y())
        elif isinstance(item, ArrowItem):
            item.set_line(local_start, local_end)
        elif isinstance(item, DimensionItem):
            item.setRect(local_start, local_end)
        else:
            raise TypeError(f"Unsupported line annotation: {type(item).__name__}")

    def handle_mouse_press(self, event) -> bool:
        if self._blocked_by_mode():
            return False
        if event.button() != Qt.LeftButton:
            return False

        self.sync_handles()
        if self.handles is None:
            return False

        handle_id = self._hit_test(event)
        if handle_id is None:
            return False

        item = self._item
        if item is None:
            return False

        if handle_id == 'rotate':
            if not isinstance(item, TextItem) or item._editable:
                return False
            scene_pos = self.view.mapToScene(event.pos())
            center = item.mapToScene(item.rect().center())
            vector = scene_pos - center
            if vector.manhattanLength() <= 1e-6:
                return False
            self._handle_id = 'rotate'
            self._rotation_start = float(item.rotation())
            self._rotation_start_angle = math.degrees(math.atan2(vector.y(), vector.x()))
            self._rotation_press_pos = QPointF(event.pos())
            self._old_pos = QPointF(item.pos())
            self.view._interaction_dragging = True
            return True

        self._handle_id = handle_id
        self._old_rect = None
        self._old_pos = QPointF(item.pos())
        self._start_scale = None
        if isinstance(item, TextItem):
            if item._editable:
                self._handle_id = None
                return False
            self._start_scale = item.scale()
            self._start_geometry = None
            self._start_scene_rect = None
            self._start_local_rect = QRectF(item.rect())
            corners = {
                'tl': self._start_local_rect.topLeft(),
                'tr': self._start_local_rect.topRight(),
                'bl': self._start_local_rect.bottomLeft(),
                'br': self._start_local_rect.bottomRight(),
            }
            opposite_id = self._text_opposite_handle(handle_id)
            self._text_moving_local = QPointF(corners[handle_id])
            self._text_anchor_local = QPointF(corners[opposite_id])
            self._text_anchor_scene = item.mapToScene(self._text_anchor_local)
            self._text_original_vector = (
                item.mapToScene(self._text_moving_local)
                - self._text_anchor_scene
            )
        elif isinstance(item, CurvedArrowItem):
            self._start_geometry = self._scene_curve_geometry(item)
            self._start_scene_rect = None
            self._start_local_rect = None
        elif isinstance(item, self.LINE_ITEMS):
            self._start_geometry = self._scene_line_geometry(item)
            self._start_anchor = (
                self._start_geometry[1]
                if handle_id == 'start'
                else self._start_geometry[0]
            )
            self._start_scene_rect = None
            self._start_local_rect = None
        else:
            self._start_scene_rect = item.mapRectToScene(item.rect()).normalized()
            self._start_local_rect = QRectF(item.rect())
            self._start_anchor = self._anchor_for_handle(
                self._start_scene_rect, handle_id
            )
            self._old_rect = QRectF(item.rect())
        self.view._interaction_dragging = True
        return True

    def handle_mouse_move(self, event) -> bool:
        if self._handle_id is None or self._item is None:
            return False
        if self._blocked_by_mode():
            return True

        cursor_scene = self.view.mapToScene(event.pos())
        item = self._item

        if self._handle_id == 'rotate':
            vector = cursor_scene - item.mapToScene(item.rect().center())
            if vector.manhattanLength() <= 1e-6:
                return True
            angle = math.degrees(math.atan2(vector.y(), vector.x()))
            delta = angle - self._rotation_start_angle
            while delta > 180.0:
                delta -= 360.0
            while delta < -180.0:
                delta += 360.0
            item.setRotation(self._rotation_start + delta)
            self.sync_handles()
            return True

        if self._handle_id == 'rotate':
            vector = cursor_scene - item.mapToScene(item.rect().center())
            if vector.manhattanLength() <= 1e-6:
                return True
            angle = math.degrees(math.atan2(vector.y(), vector.x()))
            delta = angle - self._rotation_start_angle
            while delta > 180.0:
                delta -= 360.0
            while delta < -180.0:
                delta += 360.0
            item.setRotation(self._rotation_start + delta)
            self.sync_handles()
            return True

        if isinstance(item, TextItem):
            self._resize_text(item, self._handle_id, cursor_scene)
            self.sync_handles()
            return True

        if isinstance(item, CurvedArrowItem):
            old_start, old_end, old_ctrl = self._start_geometry
            new_start, new_end, new_ctrl = self._resize_curve_geometry(
                old_start, old_end, old_ctrl, self._handle_id, cursor_scene
            )
            self._apply_scene_curve_geometry(item, new_start, new_end, new_ctrl)
            self.sync_handles()
            return True

        if isinstance(item, self.LINE_ITEMS):
            old_start, old_end = self._start_geometry
            orthogonal = bool(event.modifiers() & Qt.ShiftModifier)
            new_start, new_end = self._resize_line_geometry(
                old_start, old_end, self._handle_id, cursor_scene, orthogonal
            )
            self._apply_scene_line_geometry(item, new_start, new_end)
            self.sync_handles()
            return True

        new_scene_rect = self._resize_scene_rect(
            self._start_scene_rect, self._handle_id, cursor_scene
        )

        anchor = self._start_anchor
        if anchor is not None:
            if self._handle_id in ('tl', 'tr', 'bl', 'br'):
                new_scene_rect = QRectF(
                    QPointF(
                        min(anchor.x(), new_scene_rect.left()),
                        min(anchor.y(), new_scene_rect.top()),
                    ),
                    QPointF(
                        max(anchor.x(), new_scene_rect.right()),
                        max(anchor.y(), new_scene_rect.bottom()),
                    ),
                )
            elif self._handle_id in ('tm', 'bm'):
                new_scene_rect.setLeft(self._start_scene_rect.left())
                new_scene_rect.setRight(self._start_scene_rect.right())
            elif self._handle_id in ('lm', 'rm'):
                new_scene_rect.setTop(self._start_scene_rect.top())
                new_scene_rect.setBottom(self._start_scene_rect.bottom())

        new_scene_rect = self._clamp_to_background(
            new_scene_rect, anchor, self._handle_id
        )
        self._apply_scene_rect(self._item, new_scene_rect, anchor)
        return True

    def _local_anchor_for_handle(self, rect, handle_id):
        return self._anchor_for_handle(rect, handle_id)

    def _apply_scene_rect(self, item, scene_rect, anchor):
        local_anchor = self._local_anchor_for_handle(
            self._start_local_rect, self._handle_id
        )
        local_rect = item.mapRectFromScene(scene_rect).normalized()
        item.setRect(local_rect)

        current_anchor = item.mapToScene(local_anchor)
        delta = anchor - current_anchor
        item.setPos(item.pos() + delta)
        self.sync_handles()

    def handle_mouse_release(self, event) -> bool:
        if self._handle_id is None:
            return False

        item = self._item
        if self._handle_id == 'rotate':
            old_rotation = self._rotation_start
            press_pos = self._rotation_press_pos
            moved = press_pos is not None and QPointF(event.pos()).manhattanLength() > 4
            new_rotation = float(item.rotation())
            if not moved:
                new_rotation = old_rotation + 90.0
                item.setRotation(new_rotation)
            if old_rotation != new_rotation:
                self.view.history.push(ResizeAnnotationCommand(
                    item, old_rotation=old_rotation, new_rotation=new_rotation))
        elif isinstance(item, TextItem):
            old_scale = self._start_scale
            new_scale = item.scale()
            if old_scale is not None and old_scale != new_scale:
                self.view.history.push(
                    ResizeAnnotationCommand(
                        item,
                        old_pos=self._old_pos,
                        new_pos=QPointF(item.pos()),
                        old_scale=old_scale,
                        new_scale=new_scale,
                    )
                )
        elif isinstance(item, CurvedArrowItem):
            old_geometry = self._start_geometry
            new_geometry = self._scene_curve_geometry(item)
            if old_geometry != new_geometry:
                old_local = tuple(item.mapFromScene(point) for point in old_geometry)
                new_local = tuple(item.mapFromScene(point) for point in new_geometry)
                self.view.history.push(
                    ResizeAnnotationCommand(
                        item, old_geometry=old_local, new_geometry=new_local,
                        old_pos=self._old_pos, new_pos=QPointF(item.pos()),
                    )
                )
        elif isinstance(item, self.LINE_ITEMS):
            old_geometry = self._start_geometry
            new_geometry = self._scene_line_geometry(item)
            changed = old_geometry != new_geometry
            if changed and item is not None:
                # Команда хранит геометрию в локальной системе координат.
                # Для line-like items позиция не меняется во время resize.
                old_local = (
                    item.mapFromScene(old_geometry[0]),
                    item.mapFromScene(old_geometry[1]),
                )
                new_local = (
                    item.mapFromScene(new_geometry[0]),
                    item.mapFromScene(new_geometry[1]),
                )
                self.view.history.push(
                    ResizeAnnotationCommand(
                        item,
                        old_geometry=old_local,
                        new_geometry=new_local,
                        old_pos=self._old_pos,
                        new_pos=QPointF(item.pos()),
                    )
                )
        else:
            old_rect = self._old_rect
            new_rect = QRectF(item.rect()) if item is not None else None
            new_pos = QPointF(item.pos()) if item is not None else None

            if item is not None and (old_rect != new_rect or self._old_pos != new_pos):
                self.view.history.push(
                    ResizeAnnotationCommand(
                        item, old_rect, new_rect,
                        old_pos=self._old_pos,
                        new_pos=new_pos,
                    )
                )

        self._handle_id = None
        self._start_scene_rect = None
        self._start_local_rect = None
        self._start_anchor = None
        self._old_rect = None
        self._old_pos = None
        self._start_geometry = None
        self._start_scale = None
        self._text_anchor_local = None
        self._text_moving_local = None
        self._text_anchor_scene = None
        self._text_original_vector = None
        self._rotation_start = None
        self._rotation_start_angle = None
        self._rotation_press_pos = None
        self.view._interaction_dragging = False
        self.sync_handles()
        self.view._update_floating_widgets_visibility()
        return True
