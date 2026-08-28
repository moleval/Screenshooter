"""
Модуль: image_edit_controller.py
Описание: Контроллер операций редактирования фонового изображения.
          Управляет режимами обрезки и поворота.
          Размытие вынесено в BlurController.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt5.QtGui import QImage, QPainter, QPixmap
from PyQt5.QtWidgets import QGraphicsRectItem

from .constants import MIN_RECT_SIZE, CROP_BG_COLOR
from .controllers.crop_cursor_factory import CropCursorFactory
from .controllers.crop_overlay_controller import CropOverlayController
from .controllers.status_bar_manager import StatusBarManager
from .history import (CropCommand, RotateCommand,
                      CropPastedImageCommand, RotatePastedImageCommand)
from .image_processing import crop_pixmap, rotate_pixmap
from .items.pasted_image_item import PastedImageItem
from .items.blur_region_item import BlurRegionItem   # добавлено


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
        self.crop_rect = None
        self.temp_crop_start = None
        self.active_handle = None

        # Менеджер статусной строки
        self.status_bar_manager = StatusBarManager(self.view)

        # Контроллер визуальных элементов обрезки
        self.overlay = CropOverlayController(self.view, self.status_bar_manager)

    # --------------------------------------------------------------
    # Установка фонового элемента и сброс
    # --------------------------------------------------------------
    def set_background_item(self, item):
        self.background_item = item
        self.crop_target_item = item
        self.reset_state()

    def reset_state(self):
        self.crop_mode = False
        self.overlay.clear()
        self.overlay.remove_handles()
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
    # Ограничение точки пределами целевого изображения
    # --------------------------------------------------------------
    def _clamp_to_target(self, scene_pos):
        """Ограничивает точку пределами целевого изображения.

        Если точка выходит за пределы картинки — возвращает ближайшую
        допустимую точку на границе картинки.
        """
        if self.crop_target_item is None:
            return scene_pos

        image_rect = self.crop_target_item.mapRectToScene(
            QRectF(self.crop_target_item.pixmap().rect()))

        x = max(image_rect.left(), min(image_rect.right(), scene_pos.x()))
        y = max(image_rect.top(), min(image_rect.bottom(), scene_pos.y()))

        return QPointF(x, y)

    # --------------------------------------------------------------
    # Режим обрезки
    # --------------------------------------------------------------
    def start_crop_mode(self):
        if self.crop_mode:
            return
        self.view.blur_controller.disable_blur_mode()

        # Не вычисляем выделение заново — view.start_crop_mode() уже установил
        # self.crop_target_item до вызова этого метода.
        self.view.set_tool(None)

        self.crop_mode = True
        self.temp_crop_start = None
        self.active_handle = None
        # Устанавливаем кастомный контрастный курсор из фабрики
        self.view.setCursor(CropCursorFactory.get_cursor())
        self.view.setBackgroundBrush(CROP_BG_COLOR)

        # Fallback, если контроллер вызван напрямую (без view.start_crop_mode)
        if self.crop_target_item is None:
            self.crop_target_item = self.background_item

        if self.crop_target_item:
            self.crop_rect = self.crop_target_item.mapRectToScene(
                QRectF(self.crop_target_item.pixmap().rect()))
        else:
            self.crop_rect = self.view.sceneRect()

        self.overlay.clear()
        self.overlay.create_handles(self.crop_rect)
        self.overlay.update(self.crop_rect)
        self.overlay.update_resolution_text(self.crop_rect, self.crop_target_item)

        self.view.crop_mode_changed.emit(True)
        self.view._update_floating_widgets_visibility()

        # Обновляем статусную строку ПОСЛЕ всех виджетов
        QTimer.singleShot(0, self._update_status_bar_for_crop_target)

    def cancel_crop_mode(self):
        self.disable_crop_mode()

    def disable_crop_mode(self):
        self.crop_mode = False
        self.overlay.clear()
        self.overlay.remove_handles()
        self.crop_rect = None
        self.temp_crop_start = None
        self.active_handle = None
        # Возвращаем обычный курсор
        self.view.setCursor(Qt.CrossCursor)
        self.view.setBackgroundBrush(self.view.normal_background_color)
        self.view.crop_mode_changed.emit(False)
        self.view._update_floating_widgets_visibility()
        self.crop_target_item = None

        # Восстанавливаем разрешение подложки в статусной строке
        self.view.update_resolution_from_background()
        # Возвращаем статусную строку в обычное состояние
        self.status_bar_manager.reset_to_normal()

    def _update_status_bar_for_crop_target(self):
        self.status_bar_manager.set_crop_status(self.crop_target_item)

    def _apply_handle_drag(self, handle_id, new_scene_pos):
        rect = self.crop_rect.normalized()
        left, top, right, bottom = rect.left(), rect.top(), rect.right(), rect.bottom()
        image_rect = self.crop_target_item.mapRectToScene(
            QRectF(self.crop_target_item.pixmap().rect()))

        x = max(image_rect.left(), min(image_rect.right(), new_scene_pos.x()))
        y = max(image_rect.top(), min(image_rect.bottom(), new_scene_pos.y()))

        if handle_id == 'tl':
            left = min(x, right - MIN_RECT_SIZE)
            top = min(y, bottom - MIN_RECT_SIZE)
        elif handle_id == 'tr':
            right = max(x, left + MIN_RECT_SIZE)
            top = min(y, bottom - MIN_RECT_SIZE)
        elif handle_id == 'bl':
            left = min(x, right - MIN_RECT_SIZE)
            bottom = max(y, top + MIN_RECT_SIZE)
        elif handle_id == 'br':
            right = max(x, left + MIN_RECT_SIZE)
            bottom = max(y, top + MIN_RECT_SIZE)
        elif handle_id == 'tm':
            top = min(y, bottom - MIN_RECT_SIZE)
        elif handle_id == 'bm':
            bottom = max(y, top + MIN_RECT_SIZE)
        elif handle_id == 'lm':
            left = min(x, right - MIN_RECT_SIZE)
        elif handle_id == 'rm':
            right = max(x, left + MIN_RECT_SIZE)

        return QRectF(left, top, right - left, bottom - top).normalized()

    def apply_crop(self):
        if not self.crop_mode or not self.crop_rect or not self.crop_target_item:
            return

        crop = self.crop_rect.normalized()
        if self.crop_target_item is self.background_item:
            items_to_remove = []
            items_to_shift = []
            old_positions = []
            new_positions = []

            overlay_items = self.overlay.get_all_overlay_items()
            handle_items = self.overlay.get_handle_items()

            for item in self.view.scene().items():
                if item is self.background_item:
                    continue
                if item in overlay_items or item in handle_items.values():
                    continue
                if isinstance(item, BlurRegionItem):
                    # Зоны размытия обрабатываются отдельно через blur_controller
                    continue

                br = item.sceneBoundingRect()
                if not crop.contains(br):
                    items_to_remove.append(item)
                else:
                    items_to_shift.append(item)
                    old_pos = item.pos()
                    old_positions.append(old_pos)
                    new_positions.append(old_pos - crop.topLeft())

            old_pixmap = self.background_item.pixmap()
            new_pixmap = crop_pixmap(old_pixmap, crop)
            if new_pixmap.isNull():
                self.overlay.clear()
                return

            command = CropCommand(
                self.view.scene(), self.background_item,
                old_pixmap, new_pixmap, items_to_remove,
                controller=self, crop_rect=crop,
                items_to_shift=items_to_shift,
                old_positions=old_positions,
                new_positions=new_positions
            )
            self.view.history.push(command)

            self.overlay.clear()
            self.overlay.remove_handles()
            self.crop_rect = None
            self.temp_crop_start = None
            self.active_handle = None
            self.crop_mode = False
            self.view.setCursor(Qt.CrossCursor)
            self.view.setBackgroundBrush(self.view.normal_background_color)
            self.view.crop_mode_changed.emit(False)
            self.view._update_floating_widgets_visibility()
            self.crop_target_item = None

            self.view.update_resolution_from_background()
            self.status_bar_manager.reset_to_normal()

        else:
            old_original = self.crop_target_item.original_pixmap
            old_scale = self.crop_target_item.scale
            old_pos = self.crop_target_item.pos()
            displayed_pixmap = self.crop_target_item.pixmap()

            local_crop_display = self.crop_target_item.mapRectFromScene(crop)

            disp_w = displayed_pixmap.width()
            disp_h = displayed_pixmap.height()
            orig_w = old_original.width()
            orig_h = old_original.height()

            if disp_w > 0 and disp_h > 0 and orig_w > 0 and orig_h > 0:
                scale_x = orig_w / disp_w
                scale_y = orig_h / disp_h
                crop_orig_rect = QRectF(
                    round(local_crop_display.x() * scale_x),
                    round(local_crop_display.y() * scale_y),
                    round(local_crop_display.width() * scale_x),
                    round(local_crop_display.height() * scale_y)
                )
            else:
                crop_orig_rect = local_crop_display

            new_original = crop_pixmap(old_original, crop_orig_rect)
            if new_original.isNull():
                self.overlay.clear()
                return

            new_width = new_original.width()
            new_height = new_original.height()
            if new_width > 0 and new_height > 0:
                new_scale = min(crop.width() / new_width, crop.height() / new_height)
                if new_scale <= 0:
                    new_scale = 1.0
            else:
                new_scale = 1.0

            crop_scene_pos = crop.topLeft()
            command = CropPastedImageCommand(
                self.crop_target_item, old_original, new_original,
                old_pos, old_scale, new_scale, crop_scene_pos
            )
            self.view.history.push(command)

            self.overlay.clear()
            self.overlay.remove_handles()
            self.crop_rect = None
            self.temp_crop_start = None
            self.active_handle = None
            self.crop_mode = False
            self.view.setCursor(Qt.CrossCursor)
            self.view.setBackgroundBrush(self.view.normal_background_color)
            self.view.crop_mode_changed.emit(False)
            self.view._update_floating_widgets_visibility()
            self.crop_target_item = None

            self.view.update_resolution_from_background()
            self.status_bar_manager.reset_to_normal()

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
    # --------------------------------------------------------------
    def handle_mouse_press(self, event):
        if self.crop_mode and event.button() == Qt.LeftButton:
            handle_id = self.overlay.hit_test_handle(QPointF(event.pos()))
            if handle_id:
                self.active_handle = handle_id
                return True
            sp = self.view.mapToScene(event.pos())
            sp = self._clamp_to_target(sp)
            self.temp_crop_start = sp
            self.crop_rect = QRectF(sp, sp)
            self.overlay.clear()
            self.overlay.remove_handles()
            self.overlay.update(self.crop_rect)
            self.overlay.update_resolution_text(self.crop_rect, self.crop_target_item)
            return True
        return False

    def handle_mouse_move(self, event):
        if self.crop_mode:
            if self.active_handle is not None:
                sp = self.view.mapToScene(event.pos())
                self.crop_rect = self._apply_handle_drag(self.active_handle, sp)
                self.overlay.update(self.crop_rect)
                self.overlay.update_resolution_text(self.crop_rect, self.crop_target_item)
                return True
            if self.temp_crop_start is not None:
                sp = self.view.mapToScene(event.pos())
                sp = self._clamp_to_target(sp)
                self.crop_rect = QRectF(self.temp_crop_start, sp).normalized()
                self.overlay.update(self.crop_rect)
                self.overlay.update_resolution_text(self.crop_rect, self.crop_target_item)
                return True
            handle_id = self.overlay.hit_test_handle(QPointF(event.pos()))
            if handle_id:
                self.view.viewport().setCursor(
                    self.overlay.get_handle_cursor(handle_id))
            else:
                self.view.viewport().setCursor(CropCursorFactory.get_cursor())
            return True
        return False

    def handle_mouse_release(self, event):
        if self.crop_mode and event.button() == Qt.LeftButton:
            if self.active_handle is not None:
                self.active_handle = None
                return True
            if self.temp_crop_start is not None:
                sp = self.view.mapToScene(event.pos())
                sp = self._clamp_to_target(sp)
                self.crop_rect = QRectF(self.temp_crop_start, sp).normalized()
                if (self.crop_rect.width() < MIN_RECT_SIZE or
                        self.crop_rect.height() < MIN_RECT_SIZE):
                    if self.crop_target_item:
                        self.crop_rect = self.crop_target_item.mapRectToScene(
                            QRectF(self.crop_target_item.pixmap().rect()))
                    else:
                        self.crop_rect = self.view.sceneRect()
                    self.overlay.clear()
                    self.overlay.remove_handles()
                    self.overlay.create_handles(self.crop_rect)
                    self.overlay.update(self.crop_rect)
                    self.overlay.update_resolution_text(self.crop_rect, self.crop_target_item)
                else:
                    self.overlay.remove_handles()
                    self.overlay.create_handles(self.crop_rect)
                    self.overlay.update(self.crop_rect)
                    self.overlay.update_resolution_text(self.crop_rect, self.crop_target_item)
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