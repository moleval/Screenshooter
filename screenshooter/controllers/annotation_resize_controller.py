"""
Модуль: controllers/annotation_resize_controller.py
Описание: изменение размера аннотаций через универсальные ручки.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QPointF, QRectF

from ..constants import MIN_RECT_SIZE
from ..history import ResizeAnnotationCommand
from ..items import EllipseItem, FilledRectItem, RectangleItem, CloudItem
from ..items.crop_handles import CropHandles
from ..theme import theme_manager


class AnnotationResizeController:
    """Единственная точка входа для resize аннотаций."""

    RECT_HANDLES = ('tl', 'tm', 'tr', 'lm', 'rm', 'bl', 'bm', 'br')
    ELLIPSE_HANDLES = RECT_HANDLES
    RECT_ITEMS = (RectangleItem, FilledRectItem, CloudItem)

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

    def _blocked_by_mode(self) -> bool:
        return bool(
            self.view.blur_controller.blur_mode
            or self.view.image_editor.crop_mode
        )

    def _selected_annotation(self):
        selected = self.view.scene().selectedItems()
        annotations = [
            item for item in selected
            if isinstance(item, (RectangleItem, FilledRectItem, CloudItem, EllipseItem))
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

    def sync_handles(self):
        """Показывает ручки для единственной выбранной поддерживаемой аннотации."""
        if self._blocked_by_mode():
            self.remove_handles()
            return

        item = self._selected_annotation()
        if item is None:
            self.remove_handles()
            return

        scene_rect = item.mapRectToScene(item.rect()).normalized()
        points = self._handle_points(scene_rect, item)

        if self.handles is None or self._item is not item:
            self.remove_handles()
            self.handles = CropHandles(
                self.view,
                fill_color=theme_manager.get_color('annotation_handle'),
                show_midpoints=True,
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

    @staticmethod
    def _resize_scene_rect(old_rect, handle_id, cursor_pos):
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
        """Ограничивает только перемещаемую сторону, сохраняя anchor."""
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
                top, bottom = anchor.y() - self._start_scene_rect.height() / 2, anchor.y() + self._start_scene_rect.height() / 2
            elif handle_id in ('tm', 'bm'):
                left, right = anchor.x() - self._start_scene_rect.width() / 2, anchor.x() + self._start_scene_rect.width() / 2

        return QRectF(QPointF(left, top), QPointF(right, bottom)).normalized()

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

        self._handle_id = handle_id
        self._start_scene_rect = item.mapRectToScene(item.rect()).normalized()
        self._start_local_rect = QRectF(item.rect())
        self._start_anchor = self._anchor_for_handle(
            self._start_scene_rect, handle_id
        )
        self._old_rect = QRectF(item.rect())
        self._old_pos = QPointF(item.pos())
        self.view._interaction_dragging = True
        return True

    def handle_mouse_move(self, event) -> bool:
        if self._handle_id is None or self._item is None:
            return False
        if self._blocked_by_mode():
            return True

        cursor_scene = self.view.mapToScene(event.pos())
        item = self._item

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

    def handle_mouse_release(self, event) -> bool:
        if self._handle_id is None:
            return False

        item = self._item
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
        self.view._interaction_dragging = False
        self.sync_handles()
        self.view._update_floating_widgets_visibility()
        return True
