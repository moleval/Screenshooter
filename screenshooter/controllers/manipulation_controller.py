"""
Модуль: controllers/manipulation_controller.py
Описание: Контроллер манипуляций с элементами редактора.
          Обрабатывает перетаскивание, выделение рамкой, панорамирование,
          изменение размера вставленных изображений, временный указатель и курсор.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF, QPoint, QTimer
from PyQt5.QtGui import QPen, QColor, QCursor
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsItem, QApplication

from ..items import (RectangleItem, EllipseItem, FilledRectItem, CloudItem,
                     LineItem, WavyLineItem, ArrowItem, CurvedArrowItem,
                     DimensionItem, TextItem)
from ..items.pasted_image_item import PastedImageItem
from ..items.blur_region_item import BlurRegionItem
from ..history import (MoveItemsCommand, MoveBlurRegionCommand,
                       ResizePastedImageCommand)
from ..tools import RectTool, EllipseTool, LineTool, ArrowTool, TextTool


class ManipulationController:
    """
    Управляет всеми манипуляциями мыши с элементами редактора:
    перетаскивание, выделение, рамка, панорамирование, изменение размера, курсор.
    """

    def __init__(self, view):
        self.view = view

        # Групповое перетаскивание
        self._drag_items = []
        self._drag_old_positions = []
        self._drag_old_rects = []
        self._drag_start_scene_pos = QPointF()
        self._drag_start_item_pos = QPointF()
        self._drag_blur_needs_recompute = False

        # Изменение размера вставленных изображений
        self._resizing_pasted_item = None
        self._resize_handle = None
        self._resize_start_rect = None
        self._resize_start_scale = 1.0

        # Панорамирование
        self._pan_active = False
        self._pan_start_pos = QPoint()
        self._pan_start_scroll = QPoint()

        # Рамка выделения ПКМ
        self.rubber_band_active = False
        self.rubber_band_start = None
        self.rubber_band_item = None

        # Временный указатель
        self.right_click_temp_pointer = False
        self.previous_tool_for_right_click = None
        self.ctrl_pressed = False
        self.modifier_temp_pointer = False
        self.previous_tool_for_modifier = None

        # Кэш курсора
        self._last_cursor_pos = None
        self._last_cursor_item = None

    # ==============================================================
    # Три главных метода — вызываются из view.py
    # ==============================================================

    def handle_mouse_press(self, event) -> bool:
        """Обрабатывает нажатие кнопки мыши. Возвращает True, если обработано."""
        if self._handle_resize_press(event): return True
        if self._handle_blur_region_press(event): return True
        if self._handle_pan_press(event): return True
        if self._handle_right_click_press(event): return True
        if self._handle_left_click_press(event): return True
        if self._handle_temp_pointer_press(event): return True
        return False

    def handle_mouse_move(self, event) -> bool:
        """Обрабатывает движение мыши. Возвращает True, если обработано."""
        if self._handle_resize_move(event): return True
        if self._handle_pan_move(event): return True
        if self._handle_drag_move(event): return True
        if self._handle_rubber_band_move(event): return True
        return False

    def handle_mouse_release(self, event) -> bool:
        """Обрабатывает отпускание кнопки мыши. Возвращает True, если обработано."""
        if self._handle_resize_release(event): return True
        if self._handle_pan_release(event): return True
        if self._handle_drag_release(event): return True
        if self._handle_rubber_band_release(event): return True

        # 5. Отпускание ПКМ (если временный указатель был активен, но рамки не было)
        if event.button() == Qt.RightButton and self.right_click_temp_pointer:
            self._restore_tool_if_needed()
            return True

        return False

    # ==============================================================
    # Курсор
    # ==============================================================

    def invalidate_cursor_cache(self):
        """Сбрасывает кэш курсора при изменении сцены."""
        self._last_cursor_pos = None
        self._last_cursor_item = None

    def update_cursor(self, pos):
        """Определяет курсор по позиции мыши и элементу под курсором."""
        view = self.view

        # Кэширование: если позиция не изменилась, используем кэш
        if pos == self._last_cursor_pos:
            item = self._last_cursor_item
        else:
            sp = view.mapToScene(pos)
            item = view.scene().itemAt(sp, view.transform())
            self._last_cursor_pos = pos
            self._last_cursor_item = item

        # 1. Маркеры вставленных изображений
        for pasted in view.pasted_images:
            if pasted.isSelected() and pasted.handles:
                handle_id = pasted.handles.hit_test(pos)
                if handle_id:
                    view.viewport().setCursor(
                        pasted.handles.get_cursor_for_handle(handle_id))
                    return

        # 2. Маркеры активной зоны размытия
        if (view.image_editor.active_blur_index is not None and
                view.image_editor.active_blur_index < len(
                    view.image_editor.blur_region_items)):
            active_blur = view.image_editor.blur_region_items[
                view.image_editor.active_blur_index]
            if active_blur.handles:
                handle_id = active_blur.handles.hit_test(pos)
                if handle_id:
                    view.viewport().setCursor(
                        active_blur.handles.get_cursor_for_handle(handle_id))
                    return

        # 3. Текст в режиме редактирования
        if (view.active_text_item and item is view.active_text_item
                and view.active_text_item._editable):
            view.viewport().setCursor(Qt.IBeamCursor)
            return

        # 4. Зона размытия
        if item and isinstance(item, BlurRegionItem):
            view.viewport().setCursor(Qt.SizeAllCursor)
            return

        # 5. Элемент, который можно перемещать
        if item and not view._is_background_item(item):
            li = view._item_for_manipulation(item)
            if li is not None and li.flags() & QGraphicsItem.ItemIsMovable:
                view.viewport().setCursor(Qt.SizeAllCursor)
                return

        # 6. Вставленное изображение
        if item and isinstance(item, PastedImageItem):
            view.viewport().setCursor(Qt.SizeAllCursor)
            return

        # 7. Инструменты рисования
        if view.current_tool in ('rect', 'ellipse', 'arrow', 'line', 'text'):
            view.viewport().setCursor(Qt.CrossCursor)
        else:
            view.viewport().setCursor(Qt.ArrowCursor)

    def _refresh_cursor(self):
        """Обновляет курсор по текущей позиции мыши."""
        lp = self.view.viewport().mapFromGlobal(QCursor.pos())
        if self.view.viewport().rect().contains(lp):
            self.update_cursor(lp)
        else:
            self.view.viewport().setCursor(Qt.ArrowCursor)

    # ==============================================================
    # Нажатие кнопки мыши
    # ==============================================================

    def _handle_resize_press(self, event) -> bool:
        """Маркеры вставленных изображений."""
        if event.button() != Qt.LeftButton:
            return False
        for p_item in self.view.pasted_images:
            if p_item.isSelected() and p_item.handles:
                handle_id = p_item.handles.hit_test(event.pos())
                if handle_id:
                    self._resizing_pasted_item = p_item
                    self._resize_handle = handle_id
                    self._resize_start_rect = p_item.mapRectToScene(p_item.boundingRect())
                    self._resize_start_scale = p_item.scale
                    return True
        return False

    def _handle_blur_region_press(self, event) -> bool:
        """Зоны размытия вне режима размытия."""
        if event.button() != Qt.LeftButton:
            return False
        if self.view.image_editor.crop_mode or self.view.image_editor.blur_mode:
            return False

        modifiers = event.modifiers()
        is_ctrl = bool(modifiers & Qt.ControlModifier)
        is_shift = bool(modifiers & Qt.ShiftModifier)

        sp = self.view.mapToScene(event.pos())
        item = self.view.scene().itemAt(sp, self.view.transform())
        li = self.view._item_for_manipulation(item) if item else None

        skip_blur_handler = False
        if is_ctrl or is_shift:
            skip_blur_handler = True
        elif li is not None and isinstance(li, BlurRegionItem):
            selected_items = self.view.scene().selectedItems()
            if li.isSelected() and len(selected_items) > 1:
                skip_blur_handler = True

        if not skip_blur_handler:
            if self.view.image_editor.handle_blur_region_press_outside(event):
                return True
        return False

    def _handle_pan_press(self, event) -> bool:
        """Панорамирование средней кнопкой."""
        if event.button() != Qt.MiddleButton:
            return False
        if self.view.active_text_item and self.view.active_text_item._editable:
            return False
        self._pan_active = True
        self._pan_start_pos = event.pos()
        self._pan_start_scroll = QPoint(
            self.view.horizontalScrollBar().value(),
            self.view.verticalScrollBar().value())
        self.view.viewport().setCursor(Qt.ClosedHandCursor)
        return True

    def _handle_right_click_press(self, event) -> bool:
        """Правая кнопка — выделение элемента или начало рамки."""
        if event.button() != Qt.RightButton:
            return False
        if self.view.active_text_item and self.view.active_text_item._editable:
            return False

        sp = self.view.mapToScene(event.pos())
        right_item = None
        for it in self.view.scene().items(sp):
            if not self.view._is_background_item(it):
                right_item = it
                break

        if right_item:
            right_li = self.view._item_for_manipulation(right_item)
            self.view.scene().clearSelection()
            right_li.setSelected(True)
            self._activate_temp_pointer('right_click')
        else:
            self.view.scene().clearSelection()
            self._activate_temp_pointer('right_click')
            self.rubber_band_active = True
            self.rubber_band_start = sp
            pen = QPen(QColor(255, 200, 0), 3, Qt.DashLine)
            pen.setCosmetic(True)
            self.rubber_band_item = QGraphicsRectItem(QRectF(sp, sp))
            self.rubber_band_item.setPen(pen)
            self.rubber_band_item.setZValue(10000)
            self.rubber_band_item.setFlag(QGraphicsRectItem.ItemIsMovable, False)
            self.rubber_band_item.setFlag(QGraphicsRectItem.ItemIsSelectable, False)
            self.view.scene().addItem(self.rubber_band_item)
            QApplication.processEvents()
            self.view.setViewportUpdateMode(self.view.FullViewportUpdate)
            self.view.viewport().update()
        return True

    def _handle_left_click_press(self, event) -> bool:
        """Левая кнопка — выделение и начало перетаскивания."""
        if event.button() != Qt.LeftButton:
            return False

        sp = self.view.mapToScene(event.pos())
        item = self.view.scene().itemAt(sp, self.view.transform())
        if isinstance(item, TextItem) and item._editable:
            return False

        li = self.view._item_for_manipulation(item) if item else None

        if li is not None and not self.view._is_background_item(li):
            modifiers = event.modifiers()
            is_ctrl = bool(modifiers & Qt.ControlModifier)
            is_shift = bool(modifiers & Qt.ShiftModifier)

            if li.isSelected():
                if is_ctrl:
                    li.setSelected(False)
                    return True
            else:
                if not (is_ctrl or is_shift):
                    self.view.scene().clearSelection()
                li.setSelected(True)

            selected = self.view.scene().selectedItems()
            self._drag_items = [it for it in selected
                                if not self.view._is_background_item(it)]

            if not self._drag_items:
                return True

            self._drag_old_positions = []
            self._drag_old_rects = []
            self._drag_blur_needs_recompute = False
            for it in self._drag_items:
                if isinstance(it, BlurRegionItem):
                    self._drag_old_positions.append(None)
                    self._drag_old_rects.append(it.rect())
                else:
                    self._drag_old_positions.append(it.pos())
                    self._drag_old_rects.append(None)

            self._drag_start_scene_pos = sp
            self._drag_start_item_pos = (
                li.pos() if not isinstance(li, BlurRegionItem)
                else li.rect().topLeft())
            return True

        return False

    def _handle_temp_pointer_press(self, event) -> bool:
        """Временный указатель (ПКМ или Ctrl)."""
        if event.button() != Qt.LeftButton:
            return False

        if ((self.right_click_temp_pointer or self.modifier_temp_pointer)
                and self.view.current_tool is None):
            sp = self.view.mapToScene(event.pos())
            item = self.view.scene().itemAt(sp, self.view.transform())
            li = self.view._item_for_manipulation(item) if item else None

            if li is None or self.view._is_background_item(li):
                if self.right_click_temp_pointer:
                    self.view.scene().clearSelection()
                    self.right_click_temp_pointer = False
                    if not self.modifier_temp_pointer:
                        self._restore_tool_if_needed()
                return True
        return False

    # ==============================================================
    # Движение мыши
    # ==============================================================

    def _handle_resize_move(self, event) -> bool:
        """Изменение размера вставленного изображения через угловые маркеры."""
        if self._resizing_pasted_item is None:
            return False

        sp = self.view.mapToScene(event.pos())
        item = self._resizing_pasted_item
        start_rect = self._resize_start_rect
        handle_id = self._resize_handle
        left, top = start_rect.left(), start_rect.top()
        right, bottom = start_rect.right(), start_rect.bottom()
        min_size = PastedImageItem.MIN_SIZE

        if handle_id == 'tl':
            left = min(sp.x(), right - min_size)
            top = min(sp.y(), bottom - min_size)
        elif handle_id == 'tr':
            right = max(sp.x(), left + min_size)
            top = min(sp.y(), bottom - min_size)
        elif handle_id == 'bl':
            left = min(sp.x(), right - min_size)
            bottom = max(sp.y(), top + min_size)
        elif handle_id == 'br':
            right = max(sp.x(), left + min_size)
            bottom = max(sp.y(), top + min_size)

        new_rect = QRectF(left, top, right - left, bottom - top).normalized()
        local_rect = item.mapRectFromScene(new_rect)
        scale_x = local_rect.width() / item.original_pixmap.width()
        scale_y = local_rect.height() / item.original_pixmap.height()
        scale = min(scale_x, scale_y)

        corner_anchors = {'tl': 'br', 'tr': 'bl', 'bl': 'tr', 'br': 'tl'}
        anchor_id = corner_anchors[handle_id]

        old_scene_rect = item.mapRectToScene(item.boundingRect())
        old_anchor = self._get_rect_corner(old_scene_rect, anchor_id)

        item.set_image_scale(scale)

        new_scene_rect = item.mapRectToScene(item.boundingRect())
        new_anchor = self._get_rect_corner(new_scene_rect, anchor_id)

        shift = old_anchor - new_anchor
        item.setPos(item.pos() + shift)

        item.update_handles()

        return True

    @staticmethod
    def _get_rect_corner(rect, corner_id):
        """Возвращает координаты угла прямоугольника."""
        if corner_id == 'tl':
            return rect.topLeft()
        elif corner_id == 'tr':
            return rect.topRight()
        elif corner_id == 'bl':
            return rect.bottomLeft()
        elif corner_id == 'br':
            return rect.bottomRight()

    def _handle_pan_move(self, event) -> bool:
        """Панорамирование."""
        if not self._pan_active:
            return False
        dx = event.pos().x() - self._pan_start_pos.x()
        dy = event.pos().y() - self._pan_start_pos.y()
        scale = self.view.transform().m11()
        if scale != 0:
            self.view.horizontalScrollBar().setValue(
                int(self._pan_start_scroll.x() - dx / scale))
            self.view.verticalScrollBar().setValue(
                int(self._pan_start_scroll.y() - dy / scale))
        return True

    def _handle_drag_move(self, event) -> bool:
        """Групповое перетаскивание элементов."""
        if not self._drag_items:
            return False

        current_scene_pos = self.view.mapToScene(event.pos())
        delta = current_scene_pos - self._drag_start_scene_pos

        if event.modifiers() & Qt.ShiftModifier:
            if abs(delta.x()) > abs(delta.y()):
                delta.setY(0.0)
            else:
                delta.setX(0.0)

        for idx, drag_item in enumerate(self._drag_items):
            if isinstance(drag_item, BlurRegionItem):
                old_rect = self._drag_old_rects[idx]
                new_rect = old_rect.translated(delta)
                if self.view.image_editor.background_item is not None:
                    image_rect = QRectF(
                        self.view.image_editor.background_item.pixmap().rect())
                    if new_rect.left() < image_rect.left():
                        new_rect.moveLeft(image_rect.left())
                    elif new_rect.right() > image_rect.right():
                        new_rect.moveRight(image_rect.right())
                    if new_rect.top() < image_rect.top():
                        new_rect.moveTop(image_rect.top())
                    elif new_rect.bottom() > image_rect.bottom():
                        new_rect.moveBottom(image_rect.bottom())
                drag_item.setRect(new_rect)
                try:
                    idx_blur = self.view.image_editor.blur_region_items.index(drag_item)
                    self.view.image_editor.blur_regions[idx_blur] = new_rect
                    self._drag_blur_needs_recompute = True
                    self.view.image_editor._schedule_blur_recompute(moving_index=idx_blur)
                except ValueError:
                    pass
                if drag_item.handles:
                    drag_item.handles.update_handles(new_rect)
            else:
                old_pos = self._drag_old_positions[idx]
                new_pos = old_pos + delta
                if self.view.image_editor.background_item is not None:
                    image_rect = QRectF(
                        self.view.image_editor.background_item.pixmap().rect())
                    item_rect = drag_item.boundingRect()
                    proposed_rect = QRectF(
                        new_pos + item_rect.topLeft(),
                        new_pos + item_rect.bottomRight())
                    if proposed_rect.left() < image_rect.left():
                        new_pos.setX(new_pos.x() + (
                            image_rect.left() - proposed_rect.left()))
                    elif proposed_rect.right() > image_rect.right():
                        new_pos.setX(new_pos.x() - (
                            proposed_rect.right() - image_rect.right()))
                    proposed_rect = QRectF(
                        new_pos + item_rect.topLeft(),
                        new_pos + item_rect.bottomRight())
                    if proposed_rect.top() < image_rect.top():
                        new_pos.setY(new_pos.y() + (
                            image_rect.top() - proposed_rect.top()))
                    elif proposed_rect.bottom() > image_rect.bottom():
                        new_pos.setY(new_pos.y() - (
                            proposed_rect.bottom() - image_rect.bottom()))
                drag_item.setPos(new_pos)
                if isinstance(drag_item, PastedImageItem):
                    drag_item.show_handles()

        self.view.scene().update()
        self.view._update_pasted_image_handles()
        return True

    def _handle_rubber_band_move(self, event) -> bool:
        """Рамка выделения ПКМ."""
        if not self.rubber_band_active or not self.rubber_band_item:
            return False
        cp = self.view.mapToScene(event.pos())
        self.rubber_band_item.setRect(
            QRectF(self.rubber_band_start, cp).normalized())
        self.rubber_band_item.update()
        self.view.viewport().update()
        return True

    # ==============================================================
    # Отпускание кнопки мыши
    # ==============================================================

    def _handle_resize_release(self, event) -> bool:
        """Завершение изменения размера вставленного изображения."""
        if self._resizing_pasted_item is None:
            return False
        item = self._resizing_pasted_item
        old_scale = self._resize_start_scale
        new_scale = item.scale
        if old_scale != new_scale:
            self.view.history.push(
                ResizePastedImageCommand(item, old_scale, new_scale))
        self._resizing_pasted_item = None
        self._resize_handle = None
        self._resize_start_rect = None
        self._resize_start_scale = 1.0
        self.view._update_pasted_image_handles()
        return True

    def _handle_pan_release(self, event) -> bool:
        """Завершение панорамирования."""
        if event.button() != Qt.MiddleButton or not self._pan_active:
            return False
        self._pan_active = False
        self._refresh_cursor()
        return True

    def _handle_drag_release(self, event) -> bool:
        """Завершение группового перетаскивания."""
        if not self._drag_items:
            return False

        normal_items = [it for it in self._drag_items
                        if not isinstance(it, BlurRegionItem)]

        if normal_items:
            old_positions = []
            new_positions = []
            for idx, it in enumerate(self._drag_items):
                if not isinstance(it, BlurRegionItem):
                    old_positions.append(self._drag_old_positions[idx])
                    new_positions.append(it.pos())
            if old_positions != new_positions:
                self.view.history.push(
                    MoveItemsCommand(normal_items, old_positions, new_positions))

        for idx, it in enumerate(self._drag_items):
            if isinstance(it, BlurRegionItem):
                old_rect = self._drag_old_rects[idx]
                new_rect = it.rect()
                if old_rect != new_rect:
                    try:
                        idx_blur = self.view.image_editor.blur_region_items.index(it)
                        self.view.history.push(MoveBlurRegionCommand(
                            self.view.image_editor, idx_blur, old_rect, new_rect))
                    except ValueError:
                        pass

        if self._drag_blur_needs_recompute:
            self.view.image_editor._force_blur_recompute()
            self._drag_blur_needs_recompute = False

        self._drag_items = []
        self._drag_old_positions = []
        self._drag_old_rects = []
        self._drag_start_scene_pos = QPointF()
        self._drag_start_item_pos = QPointF()
        self.view._update_pasted_image_handles()
        self.view._update_blur_region_handles()
        self.invalidate_cursor_cache()
        return True

    def _handle_rubber_band_release(self, event) -> bool:
        """Завершение рамки выделения ПКМ."""
        if not self.rubber_band_active or event.button() != Qt.RightButton:
            return False

        if self.rubber_band_item:
            self.view.scene().removeItem(self.rubber_band_item)
            rect = self.rubber_band_item.rect()
            self.rubber_band_item = None
            for item in self.view.scene().items():
                if self.view._is_background_item(item):
                    continue
                li = self.view._item_for_manipulation(item)
                if li.sceneBoundingRect().intersects(rect):
                    li.setSelected(True)
        self.rubber_band_active = False
        self.rubber_band_start = None
        self.view.setViewportUpdateMode(self.view.SmartViewportUpdate)
        self.view.viewport().update()
        
        # Восстанавливаем инструмент после завершения выделения рамкой
        self._restore_tool_if_needed()
        
        return True

    # ==============================================================
    # Вспомогательные методы
    # ==============================================================

    def _activate_temp_pointer(self, src):
        """Активирует временный указатель при ПКМ или Ctrl."""
        if self.view.current_tool:
            if src == 'right_click' and not self.right_click_temp_pointer:
                self.right_click_temp_pointer = True
                self.previous_tool_for_right_click = self.view.current_tool
            elif src == 'modifier' and not self.modifier_temp_pointer:
                self.modifier_temp_pointer = True
                self.previous_tool_for_modifier = self.view.current_tool
        self.view.current_tool = None
        self.view.setDragMode(self.view.NoDrag)
        # Скрываем виджеты инструментов при активации временного указателя
        self.view.widget_manager.update_floating_widgets_visibility()

    def _restore_tool_if_needed(self):
        """Восстанавливает инструмент после временного указателя."""
        if self.right_click_temp_pointer and not self.modifier_temp_pointer:
            tool = self.previous_tool_for_right_click
            self.right_click_temp_pointer = False
            self.previous_tool_for_right_click = None
            if tool:
                self._restore_tool_state(tool)
            self.view.widget_manager.update_floating_widgets_visibility()
        elif self.modifier_temp_pointer and not self.right_click_temp_pointer:
            tool = self.previous_tool_for_modifier
            self.modifier_temp_pointer = False
            self.previous_tool_for_modifier = None
            if tool:
                self._restore_tool_state(tool)
            self.view.widget_manager.update_floating_widgets_visibility()

    def _restore_tool_state(self, t):
        """Восстанавливает состояние инструмента без снятия выделения."""
        self.view._apply_tool(t)
        self.view._first_click_after_activation = (t == 'text')

        # Создаем объект инструмента, чтобы он мог обрабатывать события мыши
        if t == 'rect':
            self.view._tool = RectTool(self.view)
        elif t == 'ellipse':
            self.view._tool = EllipseTool(self.view)
        elif t == 'line':
            self.view._tool = LineTool(self.view)
        elif t == 'arrow':
            self.view._tool = ArrowTool(self.view)
        elif t == 'text':
            self.view._tool = TextTool(self.view)
        else:
            self.view._tool = None

        if not self.view.scene().selectedItems():
            self.view.widget_manager.update_info_widget_content(
                self.view.current_pen_color, self.view.get_current_width())

        self.invalidate_cursor_cache()
        QTimer.singleShot(0, self._refresh_cursor)