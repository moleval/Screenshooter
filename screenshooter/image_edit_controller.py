"""
Модуль: image_edit_controller.py
Описание: Контроллер операций редактирования фонового изображения.
          Управляет режимами обрезки, поворота и размытия.
          Обрабатывает создание, перемещение и изменение размеров зон размытия,
          а также применение команд undo/redo для этих операций.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt5.QtGui import QPen, QColor, QBrush, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import QGraphicsRectItem

from .constants import MIN_RECT_SIZE
from .history import (CropCommand, RotateCommand, BlurCommand,
                      AddBlurRegionCommand, RemoveBlurRegionCommand,
                      MoveBlurRegionCommand, ResizeBlurRegionCommand,
                      CropPastedImageCommand, RotatePastedImageCommand)
from .image_processing import crop_pixmap, rotate_pixmap, blur_region
from .items.crop_handles import CropHandles
from .items.pasted_image_item import PastedImageItem
from .items.blur_region_item import BlurRegionItem


class ImageEditController:
    """
    Управляет операциями с фоновым изображением (crop, blur, rotate).
    Также поддерживает операции с вставленными изображениями.
    """

    def __init__(self, view):
        self.view = view

        self.background_item = None
        self.crop_target_item = None
        self.crop_mode = False
        self.blur_mode = False
        self.crop_rect_item = None
        self.crop_rect = None
        self.crop_overlay_items = []
        self.temp_crop_start = None
        self.handles = None
        self.active_handle = None

        self.blur_base_pixmap = None
        self.blur_regions = []
        self.blur_region_items = []
        self.active_blur_index = None
        self.blur_interaction = None
        self.blur_temp_item = None
        self.blur_start_point = None
        self.blur_move_start = None
        self.blur_resize_handle = None
        self.blur_old_rect = None

        self.blur_outside_mode = False
        self.blur_outside_interaction = None

        # Таймер троттлинга перерисовки размытия при перетаскивании
        self._blur_recompute_timer = QTimer()
        self._blur_recompute_timer.setInterval(50)
        self._blur_recompute_timer.timeout.connect(self._recompute_blurred_pixmap)

    # --------------------------------------------------------------
    # Установка фонового элемента и сброс
    # --------------------------------------------------------------
    def set_background_item(self, item):
        self.background_item = item
        self.crop_target_item = item
        self.reset_state()

    def reset_state(self):
        self.crop_mode = False
        self.blur_mode = False
        self._clear_crop_preview()
        self._remove_handles()
        self.crop_rect = None
        self.temp_crop_start = None
        self.active_handle = None

        self._clear_all_blur_regions()
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
    # Внутренние методы размытия
    # --------------------------------------------------------------
    def _clear_all_blur_regions(self):
        for item in self.blur_region_items:
            if not self._is_deleted(item):
                item.remove()
        for it in self.view.scene().items():
            if isinstance(it, BlurRegionItem):
                it.remove()
        self.blur_region_items.clear()
        self.blur_regions.clear()
        self.active_blur_index = None
        self.blur_interaction = None
        self.blur_temp_item = None
        self.blur_base_pixmap = None
        self.blur_outside_mode = False
        self.blur_outside_interaction = None
        self._blur_recompute_timer.stop()

    def _clear_blur_regions(self):
        self._clear_all_blur_regions()

    def _get_blur_state(self):
        return {
            'rects': [QRectF(r) for r in self.blur_regions],
            'base_pixmap': self.blur_base_pixmap.copy() if self.blur_base_pixmap else None,
            'active_index': self.active_blur_index,
        }

    def _restore_blur_state(self, state):
        self._clear_all_blur_regions()
        self.blur_regions = state['rects']
        self.blur_base_pixmap = state['base_pixmap']
        self.active_blur_index = None
        self.blur_region_items = []
        for rect in self.blur_regions:
            item = BlurRegionItem(rect, self.view, mode='inactive')
            self.view.scene().addItem(item)
            self.blur_region_items.append(item)
        for it in self.view.scene().items():
            if isinstance(it, BlurRegionItem) and it not in self.blur_region_items:
                it.remove()

    def _apply_crop_to_blur_regions(self, crop_rect: QRectF):
        if self.blur_base_pixmap is not None:
            self.blur_base_pixmap = crop_pixmap(self.blur_base_pixmap, crop_rect)

        new_regions = []
        for item in self.blur_region_items:
            if not self._is_deleted(item):
                item.remove()
        self.blur_region_items.clear()

        for rect in self.blur_regions:
            inter = rect.intersected(crop_rect)
            if not inter.isEmpty():
                inter.moveLeft(inter.left() - crop_rect.left())
                inter.moveTop(inter.top() - crop_rect.top())
                new_regions.append(inter)

        self.blur_regions = new_regions
        self.active_blur_index = None

        for rect in self.blur_regions:
            item = BlurRegionItem(rect, self.view, mode='inactive')
            self.view.scene().addItem(item)
            self.blur_region_items.append(item)

        self._recompute_blurred_pixmap()

    def _add_blur_region_internal(self, rect):
        if self.blur_base_pixmap is None:
            self.blur_base_pixmap = self.background_item.pixmap()
        self.blur_regions.append(rect)
        item = BlurRegionItem(rect, self.view, mode='active')
        self.view.scene().addItem(item)
        self.blur_region_items.append(item)
        self._recompute_blurred_pixmap()
        self._set_active_blur(len(self.blur_regions) - 1)

    def _remove_last_blur_region(self):
        if self.blur_regions:
            self.blur_regions.pop()
            if self.blur_region_items:
                item = self.blur_region_items.pop()
                item.remove()
            for it in self.view.scene().items():
                if isinstance(it, BlurRegionItem) and it not in self.blur_region_items:
                    it.remove()
            self.active_blur_index = None
            self._recompute_blurred_pixmap()

    def _remove_blur_region_at(self, index):
        if 0 <= index < len(self.blur_regions):
            rect = self.blur_regions.pop(index)
            item = self.blur_region_items.pop(index)
            item.remove()
            if self.active_blur_index is not None:
                if self.active_blur_index == index:
                    self.active_blur_index = None
                elif self.active_blur_index > index:
                    self.active_blur_index -= 1
            for it in self.view.scene().items():
                if isinstance(it, BlurRegionItem) and it not in self.blur_region_items:
                    it.remove()
            self._recompute_blurred_pixmap()
            return rect
        return None

    def _insert_blur_region_at(self, index, rect):
        self.blur_regions.insert(index, rect)
        item = BlurRegionItem(rect, self.view, mode='inactive')
        self.view.scene().addItem(item)
        self.blur_region_items.insert(index, item)
        self._recompute_blurred_pixmap()

    def _update_blur_region_rect(self, index, rect):
        if 0 <= index < len(self.blur_regions):
            self.blur_regions[index] = rect
            item = self.blur_region_items[index]
            item.update_rect(rect)
            if self.active_blur_index == index and item.mode == 'active':
                if item.handles:
                    item.handles.update_handles(rect)
            self._recompute_blurred_pixmap()

    def _recompute_blurred_pixmap(self):
        # ЭТАП 2: принудительная перерисовка для SmartViewportUpdate
        if self.blur_base_pixmap is None:
            return
        pixmap = QPixmap(self.blur_base_pixmap)
        for rect in self.blur_regions:
            pixmap = blur_region(pixmap, rect, radius=10.0)
        # Уведомляем сцену об изменении ДО замены пиксмапа
        self.background_item.prepareGeometryChange()
        self.background_item.setPixmap(pixmap)
        self.background_item.update()
        # Принудительная перерисовка для SmartViewportUpdate
        self.view.viewport().update()

    def _schedule_blur_recompute(self):
        """Запускает отложенную перерисовку размытия (троттлинг ~20 fps)."""
        if not self._blur_recompute_timer.isActive():
            self._blur_recompute_timer.start()

    def _force_blur_recompute(self):
        """Останавливает таймер и немедленно перерисовывает размытие."""
        self._blur_recompute_timer.stop()
        self._recompute_blurred_pixmap()

    def _set_active_blur(self, index):
        # ЭТАП 1: защита от удалённых C++ объектов
        self._clear_active_blur()
        if 0 <= index < len(self.blur_region_items):
            item = self.blur_region_items[index]
            if not sip.isdeleted(item):
                item.set_mode('active')
                self.active_blur_index = index

    def _clear_active_blur(self):
        # ЭТАП 1: защита от удалённых C++ объектов
        if self.active_blur_index is not None and self.active_blur_index < len(self.blur_region_items):
            item = self.blur_region_items[self.active_blur_index]
            if not sip.isdeleted(item):
                item.set_mode('inactive')
        self.active_blur_index = None

    def delete_active_blur_region(self):
        if self.active_blur_index is not None:
            command = RemoveBlurRegionCommand(self, self.active_blur_index)
            self.view.history.push(command)

    # --------------------------------------------------------------
    # Скрытие зон для рендера
    # --------------------------------------------------------------
    def hide_blur_regions_for_render(self):
        # ЭТАП 1: защита от удалённых C++ объектов
        for item in self.blur_region_items:
            if not sip.isdeleted(item):
                item.setVisible(False)

    def show_blur_regions_after_render(self):
        # ЭТАП 1: защита от удалённых C++ объектов
        for item in self.blur_region_items:
            if not sip.isdeleted(item):
                item.setVisible(True)

    # --------------------------------------------------------------
    # Режим обрезки
    # --------------------------------------------------------------
    def start_crop_mode(self):
        if self.crop_mode:
            return
        self.disable_blur_mode()
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
    # Режим размытия
    # --------------------------------------------------------------
    def start_blur_mode(self):
        if self.blur_mode:
            return
        self.disable_crop_mode()
        self.view.set_tool(None)
        self.view.scene().clearSelection()
        self.blur_mode = True
        self.temp_crop_start = None
        self.active_handle = None
        self.blur_interaction = None
        self.active_blur_index = None
        # ЭТАП 1: защита от удалённых C++ объектов
        for item in self.blur_region_items:
            if not sip.isdeleted(item):
                item.set_mode('inactive')
        self.view.setCursor(Qt.CrossCursor)
        self.view.blur_mode_changed.emit(True)
        self.view._update_floating_widgets_visibility()

    def cancel_blur_mode(self):
        self.disable_blur_mode()

    def disable_blur_mode(self):
        self.blur_mode = False
        self._clear_active_blur()
        self.blur_interaction = None
        self.blur_temp_item = None
        self._blur_recompute_timer.stop()
        self.view.setCursor(Qt.CrossCursor)
        self.view.blur_mode_changed.emit(False)
        self.view._update_floating_widgets_visibility()

    def handle_blur_escape(self):
        if self.blur_interaction == 'drawing':
            if self.blur_temp_item:
                self.blur_temp_item.remove()
                self.blur_temp_item = None
            self.blur_interaction = None
            self.blur_start_point = None
            return
        if self.active_blur_index is not None:
            self._clear_active_blur()
            return
        self.disable_blur_mode()

    def apply_blur(self, rect: QRectF):
        if not self.background_item or rect.isEmpty():
            return
        image_rect = QRectF(self.background_item.pixmap().rect())
        blur_rect = rect.intersected(image_rect)
        if blur_rect.isEmpty():
            return
        command = AddBlurRegionCommand(self, blur_rect)
        self.view.history.push(command)

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
    # Обработчики мыши для crop/blur режимов
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

        if self.blur_mode and event.button() == Qt.LeftButton:
            sp = self.view.mapToScene(event.pos())

            if self.active_blur_index is not None:
                item = self.blur_region_items[self.active_blur_index]
                handle_id = item.handles.hit_test(QPointF(event.pos()))
                if handle_id:
                    self.blur_interaction = 'resizing'
                    self.blur_resize_handle = handle_id
                    self.blur_old_rect = QRectF(item.rect())
                    if not item.isSelected():
                        self.view.scene().clearSelection()
                        item.setSelected(True)
                    return True
                if item.rect().contains(sp):
                    self.blur_interaction = 'moving'
                    self.blur_move_start = sp
                    self.blur_old_rect = QRectF(item.rect())
                    if not item.isSelected():
                        self.view.scene().clearSelection()
                        item.setSelected(True)
                    return True

            for idx, rect in enumerate(self.blur_regions):
                if idx == self.active_blur_index:
                    continue
                if rect.contains(sp):
                    self._set_active_blur(idx)
                    self.blur_interaction = 'moving'
                    self.blur_move_start = sp
                    self.blur_old_rect = QRectF(rect)
                    item = self.blur_region_items[idx]
                    self.view.scene().clearSelection()
                    item.setSelected(True)
                    return True

            self._clear_active_blur()
            self.blur_interaction = 'drawing'
            self.blur_start_point = sp
            self.blur_temp_item = BlurRegionItem(QRectF(sp, sp), self.view, mode='drawing')
            self.view.scene().addItem(self.blur_temp_item)
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

        if self.blur_mode:
            sp = self.view.mapToScene(event.pos())

            if self.blur_interaction == 'resizing':
                if self.active_blur_index is not None:
                    new_rect = self._apply_blur_resize(
                        self.active_blur_index, self.blur_resize_handle, sp)
                    item = self.blur_region_items[self.active_blur_index]
                    item.update_rect(new_rect)
                    self.blur_regions[self.active_blur_index] = new_rect
                    self._schedule_blur_recompute()
                return True

            if self.blur_interaction == 'moving':
                if self.active_blur_index is not None:
                    item = self.blur_region_items[self.active_blur_index]
                    delta = sp - self.blur_move_start

                    if event.modifiers() & Qt.ShiftModifier:
                        if abs(delta.x()) > abs(delta.y()):
                            delta.setY(0.0)
                        else:
                            delta.setX(0.0)

                    new_rect = self._constrain_move(self.blur_old_rect, delta)
                    if not new_rect.isEmpty():
                        item.update_rect(new_rect)
                        self.blur_regions[self.active_blur_index] = new_rect
                        self._schedule_blur_recompute()
                return True

            if self.blur_interaction == 'drawing':
                if self.blur_temp_item:
                    rect = QRectF(self.blur_start_point, sp).normalized()
                    self.blur_temp_item.setRect(rect)
                return True

            # Нет активного взаимодействия — только курсор, НЕ перехватываем
            if self.active_blur_index is not None:
                item = self.blur_region_items[self.active_blur_index]
                handle_id = item.handles.hit_test(QPointF(event.pos()))
                if handle_id:
                    self.view.viewport().setCursor(
                        item.handles.get_cursor_for_handle(handle_id))
                elif item.rect().contains(sp):
                    self.view.viewport().setCursor(Qt.SizeAllCursor)
                else:
                    self.view.viewport().setCursor(Qt.CrossCursor)
            else:
                cursor_changed = False
                for item in self.blur_region_items:
                    if item.rect().contains(sp):
                        self.view.viewport().setCursor(Qt.SizeAllCursor)
                        cursor_changed = True
                        break
                if not cursor_changed:
                    self.view.viewport().setCursor(Qt.CrossCursor)
            return False

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

        if self.blur_mode and event.button() == Qt.LeftButton:
            if self.blur_interaction == 'resizing':
                if self.active_blur_index is not None:
                    old_rect = self.blur_old_rect
                    new_rect = self.blur_regions[self.active_blur_index]
                    self._force_blur_recompute()
                    if new_rect != old_rect:
                        command = ResizeBlurRegionCommand(
                            self, self.active_blur_index, old_rect, new_rect)
                        self.view.history.push(command)
                self.blur_interaction = None
                self.blur_resize_handle = None
                self.blur_old_rect = None
                return True

            if self.blur_interaction == 'moving':
                if self.active_blur_index is not None:
                    old_rect = self.blur_old_rect
                    new_rect = self.blur_regions[self.active_blur_index]
                    self._force_blur_recompute()
                    if new_rect != old_rect:
                        command = MoveBlurRegionCommand(
                            self, self.active_blur_index, old_rect, new_rect)
                        self.view.history.push(command)
                self.blur_interaction = None
                self.blur_move_start = None
                self.blur_old_rect = None
                return True

            if self.blur_interaction == 'drawing':
                sp = self.view.mapToScene(event.pos())
                rect = QRectF(self.blur_start_point, sp).normalized()
                if self.blur_temp_item:
                    self.blur_temp_item.remove()
                    self.blur_temp_item = None
                if rect.width() < MIN_RECT_SIZE or rect.height() < MIN_RECT_SIZE:
                    self.blur_interaction = None
                    self.blur_start_point = None
                    return True
                self.blur_interaction = None
                self.blur_start_point = None
                self.apply_blur(rect)
                return True

        return False

    # --------------------------------------------------------------
    # Обработка зон размытия вне режима "Размыть"
    # --------------------------------------------------------------
    def handle_blur_region_press_outside(self, event):
        if event.button() != Qt.LeftButton:
            return False

        sp = self.view.mapToScene(event.pos())

        if self.active_blur_index is not None:
            item = self.blur_region_items[self.active_blur_index]
            handle_id = item.handles.hit_test(QPointF(event.pos()))
            if handle_id:
                self.blur_outside_mode = True
                self.blur_outside_interaction = 'resizing'
                self.blur_resize_handle = handle_id
                self.blur_old_rect = QRectF(item.rect())
                if not item.isSelected():
                    self.view.scene().clearSelection()
                    item.setSelected(True)
                return True
            if item.rect().contains(sp):
                self.blur_outside_mode = True
                self.blur_outside_interaction = 'moving'
                self.blur_move_start = sp
                self.blur_old_rect = QRectF(item.rect())
                if not item.isSelected():
                    self.view.scene().clearSelection()
                    item.setSelected(True)
                return True

        for idx, rect in enumerate(self.blur_regions):
            if idx == self.active_blur_index:
                continue
            if rect.contains(sp):
                self._set_active_blur(idx)
                self.blur_outside_mode = True
                self.blur_outside_interaction = 'moving'
                self.blur_move_start = sp
                self.blur_old_rect = QRectF(rect)
                item = self.blur_region_items[idx]
                self.view.scene().clearSelection()
                item.setSelected(True)
                return True

        self._clear_active_blur()
        return False

    def handle_blur_region_move_outside(self, event):
        if not self.blur_outside_mode:
            sp = self.view.mapToScene(event.pos())
            if self.active_blur_index is not None:
                item = self.blur_region_items[self.active_blur_index]
                handle_id = item.handles.hit_test(QPointF(event.pos()))
                if handle_id:
                    self.view.viewport().setCursor(
                        item.handles.get_cursor_for_handle(handle_id))
                elif item.rect().contains(sp):
                    self.view.viewport().setCursor(Qt.SizeAllCursor)
            else:
                for item in self.blur_region_items:
                    if item.rect().contains(sp):
                        self.view.viewport().setCursor(Qt.SizeAllCursor)
                        break
            return False

        sp = self.view.mapToScene(event.pos())
        if self.blur_outside_interaction == 'resizing':
            if self.active_blur_index is not None:
                new_rect = self._apply_blur_resize(
                    self.active_blur_index, self.blur_resize_handle, sp)
                item = self.blur_region_items[self.active_blur_index]
                item.update_rect(new_rect)
                self.blur_regions[self.active_blur_index] = new_rect
                self._schedule_blur_recompute()
            return True
        elif self.blur_outside_interaction == 'moving':
            if self.active_blur_index is not None:
                item = self.blur_region_items[self.active_blur_index]
                delta = sp - self.blur_move_start

                if event.modifiers() & Qt.ShiftModifier:
                    if abs(delta.x()) > abs(delta.y()):
                        delta.setY(0.0)
                    else:
                        delta.setX(0.0)

                new_rect = self._constrain_move(self.blur_old_rect, delta)
                if not new_rect.isEmpty():
                    item.update_rect(new_rect)
                    self.blur_regions[self.active_blur_index] = new_rect
                    self._schedule_blur_recompute()
            return True

        return False

    def handle_blur_region_release_outside(self, event):
        if event.button() != Qt.LeftButton or not self.blur_outside_mode:
            return False

        if self.blur_outside_interaction == 'resizing':
            if self.active_blur_index is not None:
                old_rect = self.blur_old_rect
                new_rect = self.blur_regions[self.active_blur_index]
                self._force_blur_recompute()
                if new_rect != old_rect:
                    command = ResizeBlurRegionCommand(
                        self, self.active_blur_index, old_rect, new_rect)
                    self.view.history.push(command)
            self.blur_resize_handle = None
            self.blur_old_rect = None
        elif self.blur_outside_interaction == 'moving':
            if self.active_blur_index is not None:
                old_rect = self.blur_old_rect
                new_rect = self.blur_regions[self.active_blur_index]
                self._force_blur_recompute()
                if new_rect != old_rect:
                    command = MoveBlurRegionCommand(
                        self, self.active_blur_index, old_rect, new_rect)
                    self.view.history.push(command)
            self.blur_move_start = None
            self.blur_old_rect = None

        self.blur_outside_mode = False
        self.blur_outside_interaction = None
        return True

    # --------------------------------------------------------------
    # Вспомогательные
    # --------------------------------------------------------------
    def _apply_blur_resize(self, index, handle_id, new_scene_pos):
        item = self.blur_region_items[index]
        rect = item.rect()
        left, top, right, bottom = rect.left(), rect.top(), rect.right(), rect.bottom()
        image_rect = QRectF(self.background_item.pixmap().rect())
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

    def _constrain_move(self, old_rect: QRectF, delta: QPointF):
        image_rect = QRectF(self.background_item.pixmap().rect())
        new_rect = old_rect.translated(delta)

        if new_rect.left() < image_rect.left():
            new_rect.moveLeft(image_rect.left())
        elif new_rect.right() > image_rect.right():
            new_rect.moveRight(image_rect.right())

        if new_rect.top() < image_rect.top():
            new_rect.moveTop(image_rect.top())
        elif new_rect.bottom() > image_rect.bottom():
            new_rect.moveBottom(image_rect.bottom())

        return new_rect