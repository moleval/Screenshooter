"""
Модуль: image_edit_controller.py
Описание: Контроллер операций редактирования фонового изображения.
          Управляет режимами обрезки и поворота.
          Размытие вынесено в BlurController.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPen, QColor, QBrush, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import QGraphicsRectItem

from .constants import MIN_RECT_SIZE
from .history import (CropCommand, RotateCommand,
                      CropPastedImageCommand, RotatePastedImageCommand)
from .image_processing import crop_pixmap, rotate_pixmap
from .items.crop_handles import CropHandles
from .items.pasted_image_item import PastedImageItem


class ImageEditController:
    """
    Управляет операциями с фоновым изображением (crop, rotate).
    Также поддерживает операции с вставленными изображениями.
    Размытие вынесено в BlurController.
    """

    def __init__(self, view):
        self.view = view

        self.background_item = None
        self.crop_target_item = None
        self.crop_mode = False
        self.crop_rect_item = None
        self.crop_rect = None
        self.crop_overlay_items = []
        self.temp_crop_start = None
        self.handles = None
        self.active_handle = None

    # --------------------------------------------------------------
    # Установка фонового элемента и сброс
    # --------------------------------------------------------------
    def set_background_item(self, item):
        self.background_item = item
        self.crop_target_item = item
        self.reset_state()

    def reset_state(self):
        self.crop_mode = False
        self._clear_crop_preview()
        self._remove_handles()
        self.crop_rect = None
        self.temp_crop_start = None
        self.active_handle = None

        # Сброс размытия делегирован в blur_controller
        self.view.blur_controller.reset_state()

        self.view.setBackgroundBrush(self.view.normal_background_color)
        self.view.crop_mode_changed.emit(False)
        self.view.blur_mode_changed.emit(False)
        self.view._update_floating_widgets_visibility()

    @staticmethod
    def _is_deleted(obj):
        return obj is None or sip.isdeleted(obj)

    # --------------------------------------------------------------
    # Маркеры рамки обрезки
    # --------------------------------------------------------------
    def _remove_handles(self):
        if self.handles:
            self.handles.remove_handles()
            self.handles = None

    def _create_handles_for_rect(self, rect):
        self._remove_handles()
        self.handles = CropHandles(self.view)
        self.handles.create_handles(rect)

    # --------------------------------------------------------------
    # Режим обрезки
    # --------------------------------------------------------------
    def start_crop_mode(self):
        if self.crop_mode:
            return
        self.view.blur_controller.disable_blur_mode()
        self.view.set_tool(None)
        self.view.scene().clearSelection()
        self.crop_mode = True
        self.temp_crop_start = None
        self.active_handle = None
        self.view.setCursor(Qt.CrossCursor)
        self.view.setBackgroundBrush(QColor(90, 90, 90))

        if self.crop_target_item is None:
            self.crop_target_item = self.background_item
        if self.crop_target_item:
            self.crop_rect = self.crop_target_item.mapRectToScene(
                QRectF(self.crop_target_item.pixmap().rect()))
        else:
            self.crop_rect = self.view.sceneRect()

        self._clear_crop_preview()
        self._create_handles_for_rect(self.crop_rect)
        self._update_crop_overlay(self.crop_rect)

        self.view.crop_mode_changed.emit(True)
        self.view._update_floating_widgets_visibility()

    def cancel_crop_mode(self):
        self.disable_crop_mode()

    def disable_crop_mode(self):
        self.crop_mode = False
        self._clear_crop_preview()
        self._remove_handles()
        self.crop_rect = None
        self.temp_crop_start = None
        self.active_handle = None
        self.view.setCursor(Qt.CrossCursor)
        self.view.setBackgroundBrush(self.view.normal_background_color)
        self.view.crop_mode_changed.emit(False)
        self.view._update_floating_widgets_visibility()
        self.crop_target_item = None

    def _clear_crop_preview(self):
        if self.crop_rect_item is not None and not self._is_deleted(self.crop_rect_item):
            if self.crop_rect_item.scene() is self.view.scene():
                self.view.scene().removeItem(self.crop_rect_item)
        self.crop_rect_item = None

        for item in self.crop_overlay_items:
            if item is not None and not self._is_deleted(item):
                if item.scene() is self.view.scene():
                    self.view.scene().removeItem(item)
        self.crop_overlay_items.clear()

    def _update_crop_overlay(self, rect):
        crop = rect.normalized()
        scene_rect = self.view.sceneRect()

        if not self.crop_overlay_items:
            for _ in range(4):
                overlay = QGraphicsRectItem()
                overlay.setPen(QPen(Qt.NoPen))
                overlay.setBrush(QColor(0, 0, 0, 120))
                overlay.setZValue(1000)
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
            self.crop_rect_item = QGraphicsRectItem()
            pen = QPen(QColor(0, 120, 215), 2, Qt.DashLine)
            pen.setCosmetic(True)
            self.crop_rect_item.setPen(pen)
            self.crop_rect_item.setBrush(QBrush(Qt.NoBrush))
            self.crop_rect_item.setZValue(1001)
            self.crop_rect_item.setAcceptedMouseButtons(Qt.NoButton)
            self.view.scene().addItem(self.crop_rect_item)
        self.crop_rect_item.setRect(crop)

        if self.handles:
            self.handles.update_handles(crop)

    def _apply_handle_drag(self, handle_id, new_scene_pos):
        rect = self.crop_rect.normalized()
        left, top, right, bottom = rect.left(), rect.top(), rect.right(), rect.bottom()
        image_rect = self.crop_target_item.mapRectToScene(
            QRectF(self.crop_target_item.pixmap().rect()))
        min_size = MIN_RECT_SIZE

        x = max(image_rect.left(), min(image_rect.right(), new_scene_pos.x()))
        y = max(image_rect.top(), min(image_rect.bottom(), new_scene_pos.y()))

        if handle_id == 'tl':
            left = min(x, right - min_size)
            top = min(y, bottom - min_size)
        elif handle_id == 'tr':
            right = max(x, left + min_size)
            top = min(y, bottom - min_size)
        elif handle_id == 'bl':
            left = min(x, right - min_size)
            bottom = max(y, top + min_size)
        elif handle_id == 'br':
            right = max(x, left + min_size)
            bottom = max(y, top + min_size)
        elif handle_id == 'tm':
            top = min(y, bottom - min_size)
        elif handle_id == 'bm':
            bottom = max(y, top + min_size)
        elif handle_id == 'lm':
            left = min(x, right - min_size)
        elif handle_id == 'rm':
            right = max(x, left + min_size)

        return QRectF(left, top, right - left, bottom - top).normalized()

    def apply_crop(self):
        if not self.crop_mode or not self.crop_rect or not self.crop_target_item:
            return

        crop = self.crop_rect.normalized()
        if self.crop_target_item is self.background_item:
            items_to_remove = []
            for item in self.view.scene().items():
                if item is self.background_item:
                    continue
                if item in self.crop_overlay_items or item is self.crop_rect_item:
                    continue
                if self.handles and item in self.handles.handle_items.values():
                    continue
                br = item.sceneBoundingRect()
                if not crop.contains(br):
                    items_to_remove.append(item)

            old_pixmap = self.background_item.pixmap()
            new_pixmap = crop_pixmap(old_pixmap, crop)
            if new_pixmap.isNull():
                self._clear_crop_preview()
                return

            command = CropCommand(
                self.view.scene(), self.background_item,
                old_pixmap, new_pixmap, items_to_remove,
                controller=self, crop_rect=crop
            )
            self.view.history.push(command)

            self._clear_crop_preview()
            self._remove_handles()
            self.crop_rect = None
            self.temp_crop_start = None
            self.active_handle = None
            self.crop_mode = False
            self.view.setCursor(Qt.CrossCursor)
            self.view.setBackgroundBrush(self.view.normal_background_color)
            self.view.crop_mode_changed.emit(False)
            self.view._update_floating_widgets_visibility()
            self.crop_target_item = None
        else:
            old_original = self.crop_target_item.original_pixmap
            displayed_pixmap = self.crop_target_item.pixmap()
            local_crop = self.crop_target_item.mapRectFromScene(crop)
            new_original = crop_pixmap(displayed_pixmap, local_crop)
            if new_original.isNull():
                self._clear_crop_preview()
                return

            old_pos = self.crop_target_item.pos()
            old_scale = self.crop_target_item.scale
            crop_scene_pos = crop.topLeft()
            command = CropPastedImageCommand(
                self.crop_target_item, old_original, new_original,
                old_pos, old_scale, crop_scene_pos
            )
            self.view.history.push(command)

            self._clear_crop_preview()
            self._remove_handles()
            self.crop_rect = None
            self.temp_crop_start = None
            self.active_handle = None
            self.crop_mode = False
            self.view.setCursor(Qt.CrossCursor)
            self.view.setBackgroundBrush(self.view.normal_background_color)
            self.view.crop_mode_changed.emit(False)
            self.view._update_floating_widgets_visibility()
            self.crop_target_item = None

    # --------------------------------------------------------------
    # Поворот
    # --------------------------------------------------------------
    def rotate_image(self, angle: float):
        selected_pasted = [it for it in self.view.scene().selectedItems()
                           if isinstance(it, PastedImageItem)]
        if selected_pasted:
            for item in selected_pasted:
                old_original = item.original_pixmap
                displayed_pixmap = item.pixmap()
                new_original = rotate_pixmap(displayed_pixmap, angle)
                old_pos = item.pos()
                old_scale = item.scale
                command = RotatePastedImageCommand(
                    item, old_original, new_original, old_pos, old_scale)
                self.view.history.push(command)
            return

        if not self.background_item:
            return

        items_to_remove = []
        for item in self.view.scene().items():
            if item is self.background_item:
                continue
            items_to_remove.append(item)

        target_rect = QRectF(self.background_item.pixmap().rect())
        rendered_image = QImage(target_rect.size().toSize(), QImage.Format_ARGB32)
        rendered_image.fill(Qt.transparent)
        painter = QPainter(rendered_image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        self.view.scene().render(painter, target_rect, target_rect)
        painter.end()

        rendered_pixmap = QPixmap.fromImage(rendered_image)
        rotated_pixmap = rotate_pixmap(rendered_pixmap, angle)

        old_pixmap = self.background_item.pixmap()
        command = RotateCommand(
            self.view.scene(), self.background_item,
            old_pixmap, rotated_pixmap, items_to_remove,
            controller=self
        )
        self.view.history.push(command)

    # --------------------------------------------------------------
    # Обработчики мыши — только режим обрезки
    # (обработка размытия делегирована в blur_controller через view.py)
    # --------------------------------------------------------------
    def handle_mouse_press(self, event):
        if self.crop_mode and event.button() == Qt.LeftButton:
            if self.handles:
                handle_id = self.handles.hit_test(QPointF(event.pos()))
                if handle_id:
                    self.active_handle = handle_id
                    return True
            sp = self.view.mapToScene(event.pos())
            self.temp_crop_start = sp
            self.crop_rect = QRectF(sp, sp)
            self._clear_crop_preview()
            self._remove_handles()
            self._update_crop_overlay(self.crop_rect)
            return True
        return False

    def handle_mouse_move(self, event):
        if self.crop_mode:
            if self.active_handle is not None:
                sp = self.view.mapToScene(event.pos())
                self.crop_rect = self._apply_handle_drag(self.active_handle, sp)
                self._update_crop_overlay(self.crop_rect)
                return True
            if self.temp_crop_start is not None:
                sp = self.view.mapToScene(event.pos())
                self.crop_rect = QRectF(self.temp_crop_start, sp).normalized()
                self._update_crop_overlay(self.crop_rect)
                return True
            if self.handles:
                handle_id = self.handles.hit_test(QPointF(event.pos()))
                if handle_id:
                    self.view.viewport().setCursor(
                        self.handles.get_cursor_for_handle(handle_id))
                else:
                    self.view.viewport().setCursor(Qt.CrossCursor)
            else:
                self.view.viewport().setCursor(Qt.CrossCursor)
            return True
        return False

    def handle_mouse_release(self, event):
        if self.crop_mode and event.button() == Qt.LeftButton:
            if self.active_handle is not None:
                self.active_handle = None
                return True
            if self.temp_crop_start is not None:
                sp = self.view.mapToScene(event.pos())
                self.crop_rect = QRectF(self.temp_crop_start, sp).normalized()
                if (self.crop_rect.width() < MIN_RECT_SIZE or
                        self.crop_rect.height() < MIN_RECT_SIZE):
                    if self.crop_target_item:
                        self.crop_rect = self.crop_target_item.mapRectToScene(
                            QRectF(self.crop_target_item.pixmap().rect()))
                    else:
                        self.crop_rect = self.view.sceneRect()
                    self._clear_crop_preview()
                    self._remove_handles()
                    self._create_handles_for_rect(self.crop_rect)
                    self._update_crop_overlay(self.crop_rect)
                else:
                    self._remove_handles()
                    self._create_handles_for_rect(self.crop_rect)
                    self._update_crop_overlay(self.crop_rect)
                self.temp_crop_start = None
                return True
        return False

    # --------------------------------------------------------------
    # Делегирование обработки зон размытия ВНЕ режима в blur_controller
    # --------------------------------------------------------------
    def handle_blur_region_press_outside(self, event):
        return self.view.blur_controller.handle_blur_region_press_outside(event)

    def handle_blur_region_move_outside(self, event):
        return self.view.blur_controller.handle_blur_region_move_outside(event)

    def handle_blur_region_release_outside(self, event):
        return self.view.blur_controller.handle_blur_region_release_outside(event)

    # --------------------------------------------------------------
    # Делегаты для blur_controller — нужны для команд в history/__init__.py
    # --------------------------------------------------------------
    def _get_blur_state(self):
        return self.view.blur_controller._get_blur_state()

    def _restore_blur_state(self, state):
        self.view.blur_controller._restore_blur_state(state)

    def _apply_crop_to_blur_regions(self, crop_rect):
        self.view.blur_controller._apply_crop_to_blur_regions(crop_rect)

    def _clear_blur_regions(self):
        self.view.blur_controller._clear_blur_regions()

    def _add_blur_region_internal(self, rect):
        self.view.blur_controller._add_blur_region_internal(rect)

    def _remove_blur_region_at(self, index):
        return self.view.blur_controller._remove_blur_region_at(index)

    def _insert_blur_region_at(self, index, rect):
        self.view.blur_controller._insert_blur_region_at(index, rect)

    def _update_blur_region_rect(self, index, rect):
        self.view.blur_controller._update_blur_region_rect(index, rect)

    def _recompute_blurred_pixmap(self):
        self.view.blur_controller._recompute_blurred_pixmap()