"""
Модуль: controllers/crop_overlay_controller.py
Описание: Управление визуальными элементами режима обрезки:
          рамка, затемнение, маркеры, текст разрешения.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPen, QBrush, QFont
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
    def __init__(self, view, status_bar_manager):
        self.view = view
        self.status_bar_manager = status_bar_manager

        self.crop_rect_item = None
        self.crop_overlay_items = []
        self.crop_size_label = None
        self.crop_size_bg = None
        self.handles = None

    def update(self, rect):
        crop = rect.normalized()
        scene_rect = self.view.sceneRect()

        overlay_color = theme_manager.get_color('crop_overlay')

        if not self.crop_overlay_items:
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

        rect_color = theme_manager.get_color('crop_rect')

        if not self.crop_rect_item:
            self.crop_rect_item = QGraphicsRectItem()
            pen = QPen(rect_color, 2, Qt.DashLine)
            pen.setCosmetic(True)
            self.crop_rect_item.setPen(pen)
            self.crop_rect_item.setBrush(QBrush(Qt.NoBrush))
            self.crop_rect_item.setZValue(CROP_RECT_Z)
            self.crop_rect_item.setAcceptedMouseButtons(Qt.NoButton)
            self.view.scene().addItem(self.crop_rect_item)
        self.crop_rect_item.setRect(crop)

        if self.handles:
            self.handles.update_handles(crop)

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
                crop_w = round(local_crop_display.width() * scale_x)
                crop_h = round(local_crop_display.height() * scale_y)
            else:
                crop_w = round(rect.width())
                crop_h = round(rect.height())

            bg_resolution = self.status_bar_manager.get_background_resolution()
            text = f"{bg_resolution} / {original.width()}×{original.height()}"
            self.status_bar_manager.update_crop_status_text(text)
        else:
            crop_w = round(rect.width())
            crop_h = round(rect.height())

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