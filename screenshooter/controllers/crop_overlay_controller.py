"""
Модуль: controllers/crop_overlay_controller.py
Описание: Управление визуальными элементами режима обрезки:
          рамка, затемнение, маркеры, текст разрешения.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPen, QBrush, QFont, QColor
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsItem

from ..constants import (
    CROP_OVERLAY_Z, CROP_RECT_Z, CROP_LABEL_Z,
    CROP_LABEL_MARGIN, CROP_LABEL_PADDING,
    CROP_LABEL_FONT_SIZE,
)
from ..items.crop_handles import CropHandles
from ..items.pasted_image_item import PastedImageItem
from ..theme import theme_manager


class CropOverlayController:
    """Управляет визуальными элементами режима обрезки."""

    def __init__(self, view, status_bar_manager):
        self.view = view
        self.status_bar_manager = status_bar_manager

        self.crop_rect_item = None
        self.crop_overlay_items = []
        self.crop_size_label = None
        self.crop_size_bg = None
        self.handles = None
        self.aspect_guide_items = []
        self.active_aspect_ratio = None
        self._displayed_aspect_ratio = None
        self._last_caught_aspect_ratio = None

    def update(self, rect, active_aspect_ratio=None):
        crop = rect.normalized()
        scene_rect = self.view.sceneRect()

        if not self.crop_overlay_items:
            overlay_color = theme_manager.get_color('crop_overlay')
            for _ in range(4):
                overlay = QGraphicsRectItem()
                overlay.setPen(QPen(Qt.NoPen))
                overlay.setBrush(overlay_color)
                overlay.setZValue(CROP_OVERLAY_Z)
                overlay.setAcceptedMouseButtons(Qt.NoButton)
                self.view.scene().addItem(overlay)
                self.crop_overlay_items.append(overlay)

        top = QRectF(scene_rect.left(), scene_rect.top(),
                     scene_rect.width(), crop.top() - scene_rect.top())
        bottom = QRectF(scene_rect.left(), crop.bottom(),
                        scene_rect.width(), scene_rect.bottom() - crop.bottom())
        left = QRectF(scene_rect.left(), crop.top(),
                      crop.left() - scene_rect.left(), crop.height())
        right = QRectF(crop.right(), crop.top(),
                       scene_rect.right() - crop.right(), crop.height())

        self.crop_overlay_items[0].setRect(top)
        self.crop_overlay_items[1].setRect(bottom)
        self.crop_overlay_items[2].setRect(left)
        self.crop_overlay_items[3].setRect(right)

        if not self.crop_rect_item:
            rect_color = theme_manager.get_color('crop_rect')
            self.crop_rect_item = QGraphicsRectItem()
            pen = QPen(rect_color, 2, Qt.DashLine)
            pen.setCosmetic(True)
            self.crop_rect_item.setPen(pen)
            self.crop_rect_item.setBrush(QBrush(Qt.NoBrush))
            self.crop_rect_item.setZValue(CROP_RECT_Z)
            self.crop_rect_item.setAcceptedMouseButtons(Qt.NoButton)
            self.view.scene().addItem(self.crop_rect_item)
        self.crop_rect_item.setRect(crop)

        self.active_aspect_ratio = active_aspect_ratio
        self._update_aspect_guides(crop)

        if self.handles:
            self.handles.update_handles(crop)


    def _update_aspect_guides(self, rect):
        """Показывает одну текущую цель соотношения сторон с фиксацией цели."""
        ratios = (
            (1, 1), (4, 5), (5, 4), (3, 4), (4, 3),
            (2, 3), (3, 2), (10, 16), (16, 10), (9, 16),
            (16, 9), (9, 21), (21, 9), (1, 2), (2, 1),
            (1, 3), (3, 1),
        )
        crop = QRectF(rect).normalized()
        if crop.width() < 20 or crop.height() < 20:
            self._clear_aspect_guides()
            self._displayed_aspect_ratio = None
            self._last_caught_aspect_ratio = None
            return

        current_ratio = crop.width() / crop.height()
        ordered = sorted(ratios, key=lambda pair: pair[0] / pair[1])

        if self.active_aspect_ratio is not None:
            self._displayed_aspect_ratio = self.active_aspect_ratio
            self._last_caught_aspect_ratio = self.active_aspect_ratio
        elif self._displayed_aspect_ratio is None:
            self._displayed_aspect_ratio = min(
                ordered,
                key=lambda pair: abs(current_ratio - pair[0] / pair[1]),
            )
        else:
            displayed_value = (
                self._displayed_aspect_ratio[0]
                / self._displayed_aspect_ratio[1]
            )
            last_caught = self._last_caught_aspect_ratio

            # После ухода с пойманной цели не возвращаем её сразу:
            # следующей целью становится ближайшее другое соотношение.
            if last_caught is not None:
                candidates = [
                    pair for pair in ordered if pair != last_caught
                ]
                next_ratio = min(
                    candidates,
                    key=lambda pair: abs(current_ratio - pair[0] / pair[1]),
                )
                if abs(current_ratio - displayed_value) > 0.08 * displayed_value:
                    self._displayed_aspect_ratio = next_ratio
                    self._last_caught_aspect_ratio = None

        visible_ratio = self._displayed_aspect_ratio
        if visible_ratio is None:
            self._clear_aspect_guides()
            return

        while len(self.aspect_guide_items) < 1:
            item = QGraphicsRectItem()
            item.setBrush(QBrush(Qt.NoBrush))
            item.setAcceptedMouseButtons(Qt.NoButton)
            item.setZValue(CROP_RECT_Z - 1)
            self.view.scene().addItem(item)
            self.aspect_guide_items.append(item)

        for index, item in enumerate(self.aspect_guide_items):
            if index > 0:
                item.setVisible(False)

        rw, rh = visible_ratio
        target_ratio = rw / rh
        if crop.width() / crop.height() >= target_ratio:
            height = crop.height()
            width = height * target_ratio
        else:
            width = crop.width()
            height = width / target_ratio

        target = QRectF(
            crop.center().x() - width / 2,
            crop.center().y() - height / 2,
            width,
            height,
        )
        is_active = self.active_aspect_ratio == visible_ratio
        color = (
            QColor(245, 190, 0, 225)
            if is_active
            else QColor(0, 120, 215, 65)
        )
        pen = QPen(color, 2 if is_active else 1, Qt.DashLine)
        pen.setCosmetic(True)
        self.aspect_guide_items[0].setPen(pen)
        self.aspect_guide_items[0].setRect(target)
        self.aspect_guide_items[0].setVisible(True)

    def _clear_aspect_guides(self):
        for item in self.aspect_guide_items:
            if item is not None and not self._is_deleted(item):
                if item.scene() is self.view.scene():
                    self.view.scene().removeItem(item)
        self.aspect_guide_items.clear()

    def hide_for_render(self):
        """Скрывает crop UI, не меняя состояние режима обрезки."""
        items = list(self.crop_overlay_items) + list(self.aspect_guide_items)
        if self.crop_rect_item is not None:
            items.append(self.crop_rect_item)
        if self.crop_size_label is not None:
            items.append(self.crop_size_label)
        if self.crop_size_bg is not None:
            items.append(self.crop_size_bg)
        if self.handles:
            items.extend(self.handles.handle_items.values())
        states = []
        for item in items:
            if item is not None and not self._is_deleted(item):
                states.append((item, item.isVisible()))
                item.setVisible(False)
        return states

    @staticmethod
    def show_after_render(states):
        for item, visible in states:
            try:
                if not sip.isdeleted(item):
                    item.setVisible(visible)
            except RuntimeError:
                pass

    def clear(self):
        if self.crop_rect_item is not None and not self._is_deleted(self.crop_rect_item):
            if self.crop_rect_item.scene() is self.view.scene():
                self.view.scene().removeItem(self.crop_rect_item)
        self.crop_rect_item = None

        if self.crop_size_label is not None and not self._is_deleted(self.crop_size_label):
            if self.crop_size_label.scene() is self.view.scene():
                self.view.scene().removeItem(self.crop_size_label)
        self.crop_size_label = None

        if self.crop_size_bg is not None and not self._is_deleted(self.crop_size_bg):
            if self.crop_size_bg.scene() is self.view.scene():
                self.view.scene().removeItem(self.crop_size_bg)
        self.crop_size_bg = None

        self._clear_aspect_guides()
        for item in self.crop_overlay_items:
            if item is not None and not self._is_deleted(item):
                if item.scene() is self.view.scene():
                    self.view.scene().removeItem(item)
        self.crop_overlay_items.clear()

    def create_handles(self, rect):
        self.remove_handles()
        self.handles = CropHandles(self.view)
        self.handles.create_handles(rect)

    def remove_handles(self):
        if self.handles:
            self.handles.remove_handles()
            self.handles = None

    def update_handles(self, rect):
        if self.handles:
            self.handles.update_handles(rect)

    def hit_test_handle(self, pos):
        if self.handles:
            return self.handles.hit_test(pos)
        return None

    def get_handle_cursor(self, handle_id):
        if self.handles:
            return self.handles.get_cursor_for_handle(handle_id)
        return None

    def get_handle_items(self):
        if self.handles:
            return self.handles.handle_items
        return {}

    def update_resolution_text(self, rect, crop_target_item):
        if crop_target_item is None:
            return

        if isinstance(crop_target_item, PastedImageItem):
            original = crop_target_item.original_pixmap
            if original is None or original.isNull():
                return

            displayed = crop_target_item.pixmap()
            if displayed.isNull():
                return

            local_crop_display = crop_target_item.mapRectFromScene(rect)
            orig_w = original.width()
            orig_h = original.height()
            disp_w = displayed.width()
            disp_h = displayed.height()

            if disp_w > 0 and disp_h > 0 and orig_w > 0 and orig_h > 0:
                scale_x = orig_w / disp_w
                scale_y = orig_h / disp_h
                crop_orig_rect = QRectF(
                    round(local_crop_display.x() * scale_x),
                    round(local_crop_display.y() * scale_y),
                    round(local_crop_display.width() * scale_x),
                    round(local_crop_display.height() * scale_y)
                )
                crop_w = crop_orig_rect.toRect().width()
                crop_h = crop_orig_rect.toRect().height()
            else:
                crop_w = rect.toRect().width()
                crop_h = rect.toRect().height()

            bg_resolution = self.status_bar_manager.get_background_resolution()
            text = f"{bg_resolution} / {original.width()}×{original.height()}"
            self.status_bar_manager.update_crop_status_text(text)
        else:
            crop_w = rect.toRect().width()
            crop_h = rect.toRect().height()

        if crop_w > 0 and crop_h > 0:
            self._update_size_label(rect, f"{crop_w}×{crop_h}")

    def _update_size_label(self, rect, text):
        label_text_color = theme_manager.get_color('crop_label_text')
        label_bg_color = theme_manager.get_color('crop_label_bg')

        if self.crop_size_label is None:
            self.crop_size_label = QGraphicsSimpleTextItem()
            self.crop_size_label.setBrush(label_text_color)
            self.crop_size_label.setZValue(CROP_LABEL_Z)
            self.crop_size_label.setAcceptedMouseButtons(Qt.NoButton)
            font = QFont()
            font.setPointSize(CROP_LABEL_FONT_SIZE)
            font.setBold(True)
            self.crop_size_label.setFont(font)
            self.crop_size_label.setFlag(QGraphicsItem.ItemIgnoresTransformations)

            self.crop_size_bg = QGraphicsRectItem()
            self.crop_size_bg.setBrush(label_bg_color)
            self.crop_size_bg.setPen(QPen(Qt.NoPen))
            self.crop_size_bg.setZValue(CROP_RECT_Z)
            self.crop_size_bg.setAcceptedMouseButtons(Qt.NoButton)
            self.crop_size_bg.setFlag(QGraphicsItem.ItemIgnoresTransformations)

            self.view.scene().addItem(self.crop_size_bg)
            self.view.scene().addItem(self.crop_size_label)

        self.crop_size_label.setText(text)

        label_rect = self.crop_size_label.boundingRect()

        viewport_rect = self.view.viewport().rect()
        visible_scene_rect = self.view.mapToScene(viewport_rect).boundingRect()

        text_below_y = rect.bottom() + CROP_LABEL_MARGIN
        text_fits_below = (text_below_y + label_rect.height() + CROP_LABEL_PADDING * 2) <= visible_scene_rect.bottom()

        if text_fits_below:
            x = rect.center().x() - label_rect.width() / 2
            y = rect.bottom() + CROP_LABEL_MARGIN
        else:
            x = rect.left() + CROP_LABEL_MARGIN
            y = rect.top() + CROP_LABEL_MARGIN

        self.crop_size_label.setPos(x, y)

        self.crop_size_bg.setRect(QRectF(-CROP_LABEL_PADDING, -CROP_LABEL_PADDING,
                                          label_rect.width() + CROP_LABEL_PADDING * 2,
                                          label_rect.height() + CROP_LABEL_PADDING * 2))
        self.crop_size_bg.setPos(x, y)

    def get_all_overlay_items(self):
        items = []
        items.extend(self.crop_overlay_items)
        if self.crop_rect_item is not None:
            items.append(self.crop_rect_item)
        if self.crop_size_label is not None:
            items.append(self.crop_size_label)
        if self.crop_size_bg is not None:
            items.append(self.crop_size_bg)
        return items

    @staticmethod
    def _is_deleted(obj):
        return obj is None or sip.isdeleted(obj)