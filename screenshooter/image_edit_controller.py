"""
Модуль: image_edit_controller.py
Описание: Контроллер операций редактирования фонового изображения.
          Управляет режимами обрезки и поворота.
          Размытие вынесено в BlurController.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer, QPoint
from PyQt5.QtGui import (QPen, QColor, QBrush, QImage, QPainter, QPixmap,
                         QFont, QCursor)
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsItem

from .constants import (
    MIN_RECT_SIZE,
    CROP_CURSOR_SIZE, CROP_LABEL_MARGIN, CROP_LABEL_PADDING,
    CROP_LABEL_FONT_SIZE, CROP_STATUS_FONT_SIZE,
    CROP_CURSOR_OUTLINE_WIDTH, CROP_CURSOR_LINE_WIDTH,
    CROP_OVERLAY_Z, CROP_RECT_Z, CROP_LABEL_Z,
    CROP_BG_COLOR, CROP_OVERLAY_COLOR, CROP_RECT_COLOR,
    CROP_LABEL_TEXT_COLOR, CROP_LABEL_BG_COLOR,
    CROP_CURSOR_OUTLINE_COLOR, CROP_CURSOR_LINE_COLOR,
    STATUS_STYLE_CROP, STATUS_STYLE_NORMAL,
)
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
        self.crop_size_label = None
        self.crop_size_bg = None

        # Кэшируем курсор обрезки, чтобы не создавать его каждый раз
        self._crop_cursor = None

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
    # Кастомный курсор для режима обрезки
    # --------------------------------------------------------------
    def _create_crop_cursor(self):
        """Создаёт контрастный курсор-перекрестие для режима обрезки.

        Чёрные линии с белой обводкой, размер CROP_CURSOR_SIZE пикселей.
        Видим на любом фоне.
        """
        if self._crop_cursor is not None:
            return self._crop_cursor

        size = CROP_CURSOR_SIZE
        center = size // 2
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Белая обводка (толще)
        pen_outline = QPen(CROP_CURSOR_OUTLINE_COLOR, CROP_CURSOR_OUTLINE_WIDTH)
        painter.setPen(pen_outline)
        painter.drawLine(center, 0, center, size)
        painter.drawLine(0, center, size, center)

        # Чёрные линии (тоньше, поверх белых)
        pen_main = QPen(CROP_CURSOR_LINE_COLOR, CROP_CURSOR_LINE_WIDTH)
        painter.setPen(pen_main)
        painter.drawLine(center, 0, center, size)
        painter.drawLine(0, center, size, center)

        painter.end()

        self._crop_cursor = QCursor(pixmap, center, center)
        return self._crop_cursor

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
        # Устанавливаем кастомный контрастный курсор
        self.view.setCursor(self._create_crop_cursor())
        self.view.setBackgroundBrush(CROP_BG_COLOR)

        # Fallback, если контроллер вызван напрямую (без view.start_crop_mode)
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

        # Обновляем статусную строку ПОСЛЕ всех виджетов
        # (отложенно через таймер, чтобы гарантировать перерисовку)
        QTimer.singleShot(0, self._update_status_bar_for_crop_target)

    def cancel_crop_mode(self):
        self.disable_crop_mode()

    def disable_crop_mode(self):
        self.crop_mode = False
        self._clear_crop_preview()
        self._remove_handles()
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
        # Принудительно обновляем статусную строку
        if hasattr(self.view, 'status_label') and self.view.status_label is not None:
            self.view.status_label.setStyleSheet(STATUS_STYLE_NORMAL)
            self.view.status_label.repaint()

    def _clear_crop_preview(self):
        if self.crop_rect_item is not None and not self._is_deleted(self.crop_rect_item):
            if self.crop_rect_item.scene() is self.view.scene():
                self.view.scene().removeItem(self.crop_rect_item)
        self.crop_rect_item = None

        # Удаляем текст с разрешением и его фон
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

    def _get_background_resolution(self):
        """Возвращает разрешение подложки в формате 'WxH'."""
        bg = self.background_item
        if bg is not None and not self._is_deleted(bg):
            pixmap = bg.pixmap()
            if not pixmap.isNull():
                return f"{pixmap.width()}×{pixmap.height()}"
        return "?"

    def _update_status_bar_for_crop_target(self):
        """Обновляет статусную строку при входе в режим обрезки.

        Для вставленных изображений показываем: разрешение_подложки / разрешение_картинки.
        Для подложки показываем только разрешение подложки.
        """
        if isinstance(self.crop_target_item, PastedImageItem):
            bg_resolution = self._get_background_resolution()
            if hasattr(self.crop_target_item, 'original_pixmap') and self.crop_target_item.original_pixmap is not None:
                pixmap = self.crop_target_item.original_pixmap
                img_resolution = f"{pixmap.width()}×{pixmap.height()}"
            else:
                img_resolution = "?"
            text = f"{bg_resolution} / {img_resolution}"
        else:
            text = self._get_background_resolution()

        if hasattr(self.view, 'status_label') and self.view.status_label is not None:
            self.view.status_label.setText(text)
            self.view.status_label.setVisible(True)
            self.view.status_label.setStyleSheet(STATUS_STYLE_CROP)
            self.view.layout_manager.update_status_label_position()
            self.view.status_label.raise_()
            self.view.status_label.update()
            self.view.status_label.repaint()

    def _force_repaint_status_label(self):
        """Принудительно перерисовывает статусную строку."""
        if hasattr(self.view, 'status_label') and self.view.status_label is not None:
            self.view.status_label.update()
            self.view.status_label.repaint()
            self.view.viewport().update()

    def _update_crop_overlay(self, rect):
        crop = rect.normalized()
        scene_rect = self.view.sceneRect()

        if not self.crop_overlay_items:
            for _ in range(4):
                overlay = QGraphicsRectItem()
                overlay.setPen(QPen(Qt.NoPen))
                overlay.setBrush(CROP_OVERLAY_COLOR)
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
            self.crop_rect_item = QGraphicsRectItem()
            pen = QPen(CROP_RECT_COLOR, 2, Qt.DashLine)
            pen.setCosmetic(True)
            self.crop_rect_item.setPen(pen)
            self.crop_rect_item.setBrush(QBrush(Qt.NoBrush))
            self.crop_rect_item.setZValue(CROP_RECT_Z)
            self.crop_rect_item.setAcceptedMouseButtons(Qt.NoButton)
            self.view.scene().addItem(self.crop_rect_item)
        self.crop_rect_item.setRect(crop)

        if self.handles:
            self.handles.update_handles(crop)

        self._update_crop_resolution_text(crop)

    def _update_crop_resolution_text(self, rect):
        """Обновляет разрешение рядом с рамкой обрезки."""
        if self.crop_target_item is None:
            return

        if isinstance(self.crop_target_item, PastedImageItem):
            original = self.crop_target_item.original_pixmap
            if original is None or original.isNull():
                return
            full_w = original.width()
            full_h = original.height()

            displayed = self.crop_target_item.pixmap()
            full_scene_w = displayed.width()
            full_scene_h = displayed.height()

            if full_scene_w > 0 and full_scene_h > 0:
                ratio_w = rect.width() / full_scene_w
                ratio_h = rect.height() / full_scene_h
            else:
                ratio_w = 1.0
                ratio_h = 1.0

            crop_w = round(full_w * ratio_w)
            crop_h = round(full_h * ratio_h)
            crop_w = min(crop_w, full_w)
            crop_h = min(crop_h, full_h)

            bg_resolution = self._get_background_resolution()
            text = f"{bg_resolution} / {full_w}×{full_h}"
            if hasattr(self.view, 'status_label') and self.view.status_label is not None:
                self.view.status_label.setText(text)
                self.view.status_label.setVisible(True)
                self.view.status_label.setStyleSheet(STATUS_STYLE_CROP)
                self.view.layout_manager.update_status_label_position()
                self.view.status_label.raise_()
                self.view.status_label.update()
                self.view.status_label.repaint()
        else:
            crop_w = round(rect.width())
            crop_h = round(rect.height())

        if crop_w > 0 and crop_h > 0:
            self._update_crop_size_label(rect, f"{crop_w}×{crop_h}")

    def _update_crop_size_label(self, rect, text):
        """Создаёт или обновляет текстовый элемент с разрешением рядом с рамкой обрезки.

        Умное позиционирование:
        - Если текст помещается под рамкой — показываем под рамкой
        - Если текст выходит за пределы видимой области — показываем внутри рамки

        Стиль: белый полупрозрачный фон с тёмным текстом (как у info_widget).
        """
        if self.crop_size_label is None:
            self.crop_size_label = QGraphicsSimpleTextItem()
            # Тёмный текст (как у info_widget)
            self.crop_size_label.setBrush(CROP_LABEL_TEXT_COLOR)
            self.crop_size_label.setZValue(CROP_LABEL_Z)
            self.crop_size_label.setAcceptedMouseButtons(Qt.NoButton)
            font = QFont()
            font.setPointSize(CROP_LABEL_FONT_SIZE)
            font.setBold(True)
            self.crop_size_label.setFont(font)
            self.crop_size_label.setFlag(QGraphicsItem.ItemIgnoresTransformations)

            self.crop_size_bg = QGraphicsRectItem()
            # Белый полупрозрачный фон (как у info_widget)
            self.crop_size_bg.setBrush(CROP_LABEL_BG_COLOR)
            self.crop_size_bg.setPen(QPen(Qt.NoPen))
            self.crop_size_bg.setZValue(CROP_RECT_Z)
            self.crop_size_bg.setAcceptedMouseButtons(Qt.NoButton)
            self.crop_size_bg.setFlag(QGraphicsItem.ItemIgnoresTransformations)

            self.view.scene().addItem(self.crop_size_bg)
            self.view.scene().addItem(self.crop_size_label)

        self.crop_size_label.setText(text)

        label_rect = self.crop_size_label.boundingRect()

        # Получаем видимую область viewport в координатах сцены
        viewport_rect = self.view.viewport().rect()
        visible_scene_rect = self.view.mapToScene(viewport_rect).boundingRect()

        # Проверяем, помещается ли текст под рамкой
        text_below_y = rect.bottom() + CROP_LABEL_MARGIN
        text_fits_below = (text_below_y + label_rect.height() + CROP_LABEL_PADDING * 2) <= visible_scene_rect.bottom()

        if text_fits_below:
            # Текст под рамкой (по центру, с отступом)
            x = rect.center().x() - label_rect.width() / 2
            y = rect.bottom() + CROP_LABEL_MARGIN
        else:
            # Текст внутри рамки (в верхнем левом углу, с отступом)
            x = rect.left() + CROP_LABEL_MARGIN
            y = rect.top() + CROP_LABEL_MARGIN

        self.crop_size_label.setPos(x, y)

        # Обновляем фон под текстом (относительно позиции текста)
        self.crop_size_bg.setRect(QRectF(-CROP_LABEL_PADDING, -CROP_LABEL_PADDING,
                                          label_rect.width() + CROP_LABEL_PADDING * 2,
                                          label_rect.height() + CROP_LABEL_PADDING * 2))
        self.crop_size_bg.setPos(x, y)

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
            for item in self.view.scene().items():
                if item is self.background_item:
                    continue
                if item in self.crop_overlay_items or item is self.crop_rect_item:
                    continue
                if self.handles and item in self.handles.handle_items.values():
                    continue
                if item is self.crop_size_label or item is self.crop_size_bg:
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
            # Возвращаем обычный курсор
            self.view.setCursor(Qt.CrossCursor)
            self.view.setBackgroundBrush(self.view.normal_background_color)
            self.view.crop_mode_changed.emit(False)
            self.view._update_floating_widgets_visibility()
            self.crop_target_item = None

            # Обновляем разрешение подложки после обрезки
            self.view.update_resolution_from_background()
            # Принудительно обновляем статусную строку (БЕЗ скрытия)
            if hasattr(self.view, 'status_label') and self.view.status_label is not None:
                self.view.status_label.setStyleSheet(STATUS_STYLE_NORMAL)
                self.view.status_label.repaint()

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
            # Возвращаем обычный курсор
            self.view.setCursor(Qt.CrossCursor)
            self.view.setBackgroundBrush(self.view.normal_background_color)
            self.view.crop_mode_changed.emit(False)
            self.view._update_floating_widgets_visibility()
            self.crop_target_item = None

            # Обновляем разрешение подложки после обрезки
            self.view.update_resolution_from_background()
            # Принудительно обновляем статусную строку
            if hasattr(self.view, 'status_label') and self.view.status_label is not None:
                self.view.status_label.setStyleSheet(STATUS_STYLE_NORMAL)
                self.view.status_label.repaint()

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
            if self.handles:
                handle_id = self.handles.hit_test(QPointF(event.pos()))
                if handle_id:
                    self.active_handle = handle_id
                    return True
            sp = self.view.mapToScene(event.pos())
            # Ограничиваем точку старта пределами картинки
            sp = self._clamp_to_target(sp)
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
                # Ограничиваем текущую точку пределами картинки
                sp = self._clamp_to_target(sp)
                self.crop_rect = QRectF(self.temp_crop_start, sp).normalized()
                self._update_crop_overlay(self.crop_rect)
                return True
            if self.handles:
                handle_id = self.handles.hit_test(QPointF(event.pos()))
                if handle_id:
                    self.view.viewport().setCursor(
                        self.handles.get_cursor_for_handle(handle_id))
                else:
                    # Кастомный контрастный курсор
                    self.view.viewport().setCursor(self._create_crop_cursor())
            else:
                # Кастомный контрастный курсор
                self.view.viewport().setCursor(self._create_crop_cursor())
            return True
        return False

    def handle_mouse_release(self, event):
        if self.crop_mode and event.button() == Qt.LeftButton:
            if self.active_handle is not None:
                self.active_handle = None
                return True
            if self.temp_crop_start is not None:
                sp = self.view.mapToScene(event.pos())
                # Ограничиваем точку отпускания пределами картинки
                sp = self._clamp_to_target(sp)
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