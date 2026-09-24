"""
Модуль: controllers/manipulation_controller.py
Описание: Контроллер манипуляций с элементами редактора.
          Обрабатывает перетаскивание, выделение рамкой, панорамирование,
          изменение размера вставленных изображений, временный указатель и курсор.
          Также реализует циклическое переключение подрежимов инструментов по ПКМ
          с поддержкой рамки выделения при перетаскивании ПКМ.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF, QPoint, QTimer
from PyQt5.QtGui import QPen, QColor, QCursor
from PyQt5.QtWidgets import (QGraphicsRectItem, QGraphicsItem, QApplication,
                             QGraphicsView)

from ..items import (RectangleItem, EllipseItem, FilledRectItem, CloudItem,
                     LineItem, WavyLineItem, ArrowItem, CurvedArrowItem,
                     DimensionItem, TextItem)
from ..items.pasted_image_item import PastedImageItem
from ..items.blur_region_item import BlurRegionItem
from ..history import (MoveItemsCommand, MoveBlurRegionCommand,
                       ResizePastedImageCommand)
from ..tools import RectTool, EllipseTool, LineTool, ArrowTool, TextTool
from ..constants import DRAG_OUTSIDE_DAMPING


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
        self._drag_start_view_pos = QPoint()
        self._drag_start_scroll = QPoint()
        self._drag_scene_prepared = False
        self._drag_start_item_pos = QPointF()
        self._drag_blur_needs_recompute = False
        self._drag_old_background = None
        self._drag_old_blur_state = None
        self._drag_selection_snapshot = []

        # Изменение размера вставленных изображений
        self._resizing_pasted_item = None
        self.view._interaction_dragging = False
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

        # Для различия клика и перетаскивания ПКМ при активном инструменте
        self._right_click_from_tool = False
        self._right_click_had_selection = False
        self._right_click_press_pos = None

    # ==============================================================
    # Три главных метода — вызываются из view.py
    # ==============================================================

    def handle_mouse_press(self, event) -> bool:
        """Обрабатывает нажатие кнопки мыши. Возвращает True, если обработано."""
        if self._handle_resize_press(event):
            return True
        if self._handle_blur_region_press(event):
            return True
        if self._handle_pan_press(event):
            return True
        if self._handle_right_click_press(event):
            return True
        if self._handle_left_click_press(event):
            return True
        if self._handle_temp_pointer_press(event):
            return True
        return False

    def handle_mouse_move(self, event) -> bool:
        """Обрабатывает движение мыши. Возвращает True, если обработано."""
        if self._handle_resize_move(event):
            return True
        if self._handle_pan_move(event):
            return True
        if self._handle_drag_move(event):
            return True
        if self._handle_rubber_band_move(event):
            return True
        return False

    def handle_mouse_release(self, event) -> bool:
        """Обрабатывает отпускание кнопки мыши. Возвращает True, если обработано."""
        if self._handle_resize_release(event):
            return True
        if self._handle_pan_release(event):
            return True
        if self._handle_drag_release(event):
            return True
        if self._handle_rubber_band_release(event):
            return True

        # Отпускание ПКМ (если временный указатель был активен, но рамки не было)
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

        if pos == self._last_cursor_pos:
            item = self._last_cursor_item
        else:
            sp = view.mapToScene(pos)
            item = view._interactive_item_at(sp)
            self._last_cursor_pos = pos
            self._last_cursor_item = item

        # 1. Маркеры изменения размера аннотаций
        annotation = getattr(view, 'annotation_resize_controller', None)
        if annotation is not None and annotation.handles:
            handle_id = annotation.handles.hit_test(pos)
            if handle_id:
                view.viewport().setCursor(
                    annotation.handles.get_cursor_for_handle(handle_id))
                return

        # 2. Маркеры вставленных изображений
        for pasted in view.pasted_images:
            if pasted.isSelected() and pasted.handles:
                handle_id = pasted.handles.hit_test(pos)
                if handle_id:
                    view.viewport().setCursor(
                        pasted.handles.get_cursor_for_handle(handle_id))
                    return

        # 3. Маркеры активной зоны размытия
        if (view.blur_controller.active_blur_index is not None and
                view.blur_controller.active_blur_index < len(
                    view.blur_controller.blur_region_items)):
            active_blur = view.blur_controller.blur_region_items[
                view.blur_controller.active_blur_index]
            if active_blur.handles:
                handle_id = active_blur.handles.hit_test(pos)
                if handle_id:
                    view.viewport().setCursor(
                        active_blur.handles.get_cursor_for_handle(handle_id))
                    return

        # 4. Текст в режиме редактирования
        if (view.active_text_item and item is view.active_text_item
                and view.active_text_item._editable):
            view.viewport().setCursor(Qt.IBeamCursor)
            return

        # 5. Зона размытия
        if item and isinstance(item, BlurRegionItem):
            view.viewport().setCursor(Qt.SizeAllCursor)
            return

        # 6. Элемент, который можно перемещать
        if item and not view._is_background_item(item):
            li = view._item_for_manipulation(item)
            if li is not None and li.flags() & QGraphicsItem.ItemIsMovable:
                view.viewport().setCursor(Qt.SizeAllCursor)
                return

        # 7. Вставленное изображение
        if item and isinstance(item, PastedImageItem):
            view.viewport().setCursor(Qt.SizeAllCursor)
            return

        # 8. Инструменты рисования — используем контрастный курсор
        if view.current_tool in ('rect', 'ellipse', 'arrow', 'line', 'text'):
            from ..controllers.crop_cursor_factory import CropCursorFactory
            view.viewport().setCursor(CropCursorFactory.get_cursor())
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
                    self.view._interaction_dragging = True
                    self._resize_handle = handle_id
                    self._resize_start_rect = p_item.mapRectToScene(p_item.boundingRect())
                    self._resize_start_scale = p_item.scale
                    return True
        return False

    def _handle_blur_region_press(self, event) -> bool:
        """Зоны размытия вне режима размытия."""
        if event.button() != Qt.LeftButton:
            return False
        if self.view.image_editor.crop_mode or self.view.blur_controller.blur_mode:
            return False

        modifiers = event.modifiers()
        is_ctrl = bool(modifiers & Qt.ControlModifier)
        is_shift = bool(modifiers & Qt.ShiftModifier)

        sp = self.view.mapToScene(event.pos())
        item = self.view._interactive_item_at(sp)
        li = self.view._item_for_manipulation(item) if item else None

        skip_blur_handler = False
        if is_ctrl or is_shift:
            skip_blur_handler = True
        elif li is not None and isinstance(li, BlurRegionItem):
            # При уже существующем множественном выделении клик по blur
            # должен продолжать групповое перетаскивание, а не переключать
            # управление на саму зону размытия. Иначе blur_controller
            # снимает выделение с остальных объектов.
            selected_items = self.view.scene().selectedItems()
            non_bg_selected = [
                item for item in selected_items
                if not self.view._is_background_item(item)
            ]
            if len(non_bg_selected) > 1:
                skip_blur_handler = True

        if not skip_blur_handler:
            if self.view.blur_controller.handle_blur_region_press_outside(event):
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
        """Правая кнопка — выделение, рамка или циклическое переключение подрежимов."""
        if event.button() != Qt.RightButton:
            return False
        if self.view.active_text_item and self.view.active_text_item._editable:
            return False

        # При активном инструменте рисования ПКМ может либо переключить подрежим,
        # либо (при перетаскивании) запустить рамку выделения
        if self.view.current_tool is not None:
            return self._start_tool_right_click(event)

        # Стандартное поведение для указателя
        return self._start_pointer_right_click(event)

    def _start_tool_right_click(self, event) -> bool:
        """Начало ПКМ при активном инструменте.

        Снимает выделение (если есть) и готовит возможность рамки.
        Одиночный клик без движения будет обработан в release.
        """
        sp = self.view.mapToScene(event.pos())

        # Проверяем выделение
        selected = self.view.scene().selectedItems()
        non_bg_selected = [it for it in selected if not self.view._is_background_item(it)]

        if non_bg_selected:
            self._right_click_had_selection = True
            self.view.scene().clearSelection()
            self.view._invalidate_cursor_cache()
        else:
            self._right_click_had_selection = False

        # Устанавливаем флаг, что ПКМ был от активного инструмента
        self._right_click_from_tool = True
        self._right_click_press_pos = event.pos()

        # Создаём рамку (она будет видна, если начнётся перетаскивание)
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
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.viewport().update()
        return True

    def _start_pointer_right_click(self, event) -> bool:
        """Стандартный ПКМ для указателя."""
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
            self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
            self.view.viewport().update()
        return True

    def _handle_left_click_press(self, event) -> bool:
        """Левая кнопка — выделение и начало перетаскивания."""
        if event.button() != Qt.LeftButton:
            return False

        sp = self.view.mapToScene(event.pos())
        item = self.view._interactive_item_at(sp)
        if isinstance(item, TextItem) and item._editable:
            return False

        li = self.view._item_for_manipulation(item) if item else None

        if li is not None and not self.view._is_background_item(li):
            modifiers = event.modifiers()
            is_ctrl = bool(modifiers & Qt.ControlModifier)
            is_shift = bool(modifiers & Qt.ShiftModifier)

            selected_before_click = self.view.scene().selectedItems()
            non_bg_selected_before_click = [
                selected_item for selected_item in selected_before_click
                if not self.view._is_background_item(selected_item)
            ]
            preserve_multi_selection_on_blur = (
                isinstance(li, BlurRegionItem)
                and len(non_bg_selected_before_click) > 1
                and not (is_ctrl or is_shift)
            )

            if preserve_multi_selection_on_blur:
                # Клик по blur при существующей группе означает включение
                # самой зоны в группу. Раньше blur оставался вне selection,
                # поэтому после первого drag следующий клик по нему мог
                # переключить обработчик blur и визуально "уронить" группу.
                li.setSelected(True)
            else:
                if li.isSelected():
                    if is_ctrl:
                        li.setSelected(False)
                        return True
                else:
                    if not (is_ctrl or is_shift):
                        self.view.scene().clearSelection()
                    li.setSelected(True)

            selected = self.view.scene().selectedItems()
            # Снимок выделения фиксируем на весь drag. BlurRegionItem является
            # полноценным участником группы и не должен исчезать из selection
            # из-за промежуточного пересчёта blur/подложки.
            self._drag_selection_snapshot = [
                it for it in selected
                if not self.view._is_background_item(it)
                and not sip.isdeleted(it)
            ]
            self._drag_items = list(self._drag_selection_snapshot)

            # Если группа содержит blur, на время группового drag фиксируем
            # уже рассчитанное размытие. Пересчёт blur одновременно с
            # изменением rect самой BlurRegionItem может временно заменить
            # её pixmap и визуально "погасить" blur; кроме того, таймер может
            # отработать уже после отпускания мыши. Финальный пересчёт будет
            # выполнен в _handle_drag_release().
            if any(isinstance(it, BlurRegionItem) for it in self._drag_items):
                self.view.blur_controller._force_blur_recompute()

            if not self._drag_items:
                self._drag_selection_snapshot = []
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
            self._drag_start_view_pos = QPoint(event.pos())
            self._drag_start_item_pos = (
                li.pos() if not isinstance(li, BlurRegionItem)
                else li.rect().topLeft())

            # Временную рабочую область расширяем только после
            # фактического начала движения в _handle_drag_move().
            # Само выделение не должно создавать sceneRect и ползунки.
            self._drag_scene_prepared = False
            self._drag_start_scroll = QPoint(
                self.view.horizontalScrollBar().value(),
                self.view.verticalScrollBar().value())
            self._drag_old_background = self.view.get_background_canvas_state()
            self._drag_old_blur_state = self.view.blur_controller._get_blur_state()
            self.view._interaction_dragging = False
            return True

        return False

    def _handle_temp_pointer_press(self, event) -> bool:
        """Временный указатель (ПКМ или Ctrl)."""
        if event.button() != Qt.LeftButton:
            return False

        if ((self.right_click_temp_pointer or self.modifier_temp_pointer)
                and self.view.current_tool is None):
            sp = self.view.mapToScene(event.pos())
            item = self.view._interactive_item_at(sp)
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

    @staticmethod
    def _dampen_point_outside_background(point, background_rect, damping=DRAG_OUTSIDE_DAMPING):
        """Мягко замедляет координаты точки за пределами подложки.

        Внутри подложки координата не меняется. За каждой границей ось
        замедляется независимо: это позволяет, например, продолжать
        свободно двигать объект по Y, даже если курсор вышел за подложку
        только справа. Чем дальше курсор уходит наружу, тем меньше
        дополнительное перемещение объекта.
        """
        if damping <= 0:
            return QPointF(point)

        def damp_axis(value, low, high):
            if value < low:
                excess = value - low
                return low + excess / (1.0 + abs(excess) / damping)
            if value > high:
                excess = value - high
                return high + excess / (1.0 + abs(excess) / damping)
            return value

        return QPointF(
            damp_axis(point.x(), background_rect.left(), background_rect.right()),
            damp_axis(point.y(), background_rect.top(), background_rect.bottom()),
        )

    def _handle_drag_move(self, event) -> bool:
        """Групповое перетаскивание элементов."""
        if not self._drag_items:
            return False

        # Обычный клик и обычное перетаскивание внутри viewport не должны
        # менять sceneRect: иначе QGraphicsView сразу показывает полосы
        # прокрутки и визуально сдвигает изображение.
        #
        # Временная рабочая область нужна только когда курсор действительно
        # подошёл к краю viewport и пользователь пытается выйти за подложку.
        edge = 32
        speed = 4
        vp = self.view.viewport().rect()
        hbar = self.view.horizontalScrollBar()
        vbar = self.view.verticalScrollBar()

        near_edge = (
            event.pos().x() <= vp.left() + edge
            or event.pos().x() >= vp.right() - edge
            or event.pos().y() <= vp.top() + edge
            or event.pos().y() >= vp.bottom() - edge
        )

        if not self._drag_scene_prepared:
            if (event.pos() - self._drag_start_view_pos).manhattanLength() < 2:
                return True

            # До фактического движения это ещё клик, поэтому плавающие
            # виджеты не трогаем. Скрывать/показывать их начинаем только
            # после перехода в реальный drag.
            self.view._interaction_dragging = True

            if near_edge:
                # prepare_drag_scene_rect() расширяет sceneRect и может из-за
                # целочисленных scrollbar дать микросдвиг точки под курсором.
                # Сохраняем исходный drag baseline, компенсируя только этот
                # микросдвиг. Нельзя заменять baseline текущей точкой:
                # это добавляет весь накопленный delta повторно и даёт
                # скачок объекта к другой части сцены.
                cursor_scene_before = self.view.mapToScene(event.pos())
                self.view.prepare_drag_scene_rect(event.pos())
                cursor_scene_after = self.view.mapToScene(event.pos())
                self._drag_start_scene_pos += (
                    cursor_scene_after - cursor_scene_before
                )
                self._drag_scene_prepared = True

        if self._drag_scene_prepared:
            # Автопрокрутка работает только после подготовки расширенной
            # рабочей области.
            # Автопрокрутка намеренно медленная: 24 px на каждый
            # mouseMove при 100%+ масштабе давали резкие скачки.
            if event.pos().x() <= vp.left() + edge:
                distance = vp.left() + edge - event.pos().x()
                hbar.setValue(hbar.value() - min(speed, max(1, distance // 4)))
            elif event.pos().x() >= vp.right() - edge:
                distance = event.pos().x() - (vp.right() - edge)
                hbar.setValue(hbar.value() + min(speed, max(1, distance // 4)))

            if event.pos().y() <= vp.top() + edge:
                distance = vp.top() + edge - event.pos().y()
                vbar.setValue(vbar.value() - min(speed, max(1, distance // 4)))
            elif event.pos().y() >= vp.bottom() - edge:
                distance = event.pos().y() - (vp.bottom() - edge)
                vbar.setValue(vbar.value() + min(speed, max(1, distance // 4)))

        # Берём обе точки через mapToScene. Он автоматически учитывает
        # текущее положение scrollbar.
        current_scene_pos = self.view.mapToScene(event.pos())

        # За пределами подложки не запрещаем перемещение полностью, но
        # постепенно уменьшаем его. Это предотвращает случайный уход объекта
        # на сотни/тысячи пикселей и последующее создание огромных белых полей
        # при expand_background_to_content(). По X и Y торможение независимое.
        bg = self.view.image_editor.background_item
        if bg is not None and not sip.isdeleted(bg):
            bg_rect = bg.sceneBoundingRect()
            current_scene_pos = self._dampen_point_outside_background(
                current_scene_pos, bg_rect)

        delta = current_scene_pos - self._drag_start_scene_pos

        if event.modifiers() & Qt.ShiftModifier:
            if abs(delta.x()) > abs(delta.y()):
                delta.setY(0.0)
            else:
                delta.setX(0.0)

        group_contains_blur = any(
            isinstance(it, BlurRegionItem) for it in self._drag_items
        )

        for idx, drag_item in enumerate(self._drag_items):
            if isinstance(drag_item, BlurRegionItem):
                old_rect = self._drag_old_rects[idx]
                new_rect = old_rect.translated(delta)
                drag_item.setRect(new_rect)
                try:
                    idx_blur = self.view.blur_controller.blur_region_items.index(drag_item)
                    self.view.blur_controller.blur_regions[idx_blur] = new_rect
                    self._drag_blur_needs_recompute = True
                    # При наличии blur в самой группе не запускаем
                    # асинхронный preview-recompute во время drag.
                    # Геометрию зоны обновляем сразу, а pixmap пересчитаем
                    # один раз после release.
                except ValueError:
                    pass
                if drag_item.handles:
                    drag_item.handles.update_handles(new_rect)
            else:
                old_pos = self._drag_old_positions[idx]
                new_pos = old_pos + delta
                drag_item.setPos(new_pos)
                if isinstance(drag_item, PastedImageItem):
                    drag_item.show_handles()
                    if self.view.blur_controller.blur_regions and not group_contains_blur:
                        self._drag_blur_needs_recompute = True
                        self.view.blur_controller._schedule_blur_recompute()

        self.view.scene().update()
        self.view._update_pasted_image_handles()

        # Ручки аннотаций принадлежат геометрии фигуры и должны следовать
        # за ней во время обычного перетаскивания.
        annotation = getattr(self.view, 'annotation_resize_controller', None)
        if annotation is not None:
            annotation.sync_handles()

        # Во время drag снимок группы является источником истины. Blur
        # и связанные с ним обновления могут косвенно менять selection;
        # восстанавливаем группу уже на каждом move, а не только на release.
        # Это исключает состояние "после первого движения группа потеряла
        # фокус", когда следующий press начинает работать как одиночный.
        selection_snapshot = [
            it for it in self._drag_selection_snapshot
            if not sip.isdeleted(it) and it.scene() is self.view.scene()
        ]
        current_selection = [
            it for it in self.view.scene().selectedItems()
            if not self.view._is_background_item(it)
            and not sip.isdeleted(it)
        ]
        if set(current_selection) != set(selection_snapshot):
            self.view.scene().clearSelection()
            for it in selection_snapshot:
                it.setSelected(True)

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
        if self.view.blur_controller.blur_regions:
            self.view.blur_controller._force_blur_recompute()
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
        """Завершение группового перетаскивания и расширение подложки."""
        if not self._drag_items:
            return False

        normal_items = [it for it in self._drag_items
                        if not isinstance(it, BlurRegionItem)]
        old_positions = []
        new_positions = []
        for idx, it in enumerate(self._drag_items):
            if not isinstance(it, BlurRegionItem):
                old_positions.append(self._drag_old_positions[idx])
                new_positions.append(it.pos())

        old_canvas = self._drag_old_background
        old_blur_state = self._drag_old_blur_state
        canvas_changed = self.view.expand_background_to_content(margin=0)
        new_canvas = self.view.get_background_canvas_state()
        new_blur_state = self.view.blur_controller._get_blur_state()

        blur_changed = (old_blur_state is not None and new_blur_state is not None and
                        old_blur_state.get('rects') != new_blur_state.get('rects'))
        positions_changed = old_positions != new_positions
        if positions_changed or canvas_changed or blur_changed:
            old_pixmap, old_pos = old_canvas if old_canvas else (None, None)
            new_pixmap, new_pos = new_canvas if new_canvas else (None, None)
            self.view.history.push(MoveItemsCommand(
                normal_items, old_positions, new_positions,
                background_item=self.view.background_item,
                old_pixmap=old_pixmap if canvas_changed else None,
                new_pixmap=new_pixmap if canvas_changed else None,
                old_background_pos=old_pos if canvas_changed else None,
                new_background_pos=new_pos if canvas_changed else None,
                blur_controller=self.view.blur_controller,
                old_blur_state=old_blur_state if (canvas_changed or blur_changed) else None,
                new_blur_state=new_blur_state if (canvas_changed or blur_changed) else None
            ))

        # Любое перемещение аннотации может временно пересекать blur.
        # После завершения drag принудительно пересобираем результат, чтобы
        # уход аннотации из зоны никогда не оставлял устаревший/повреждённый
        # пиксмап размытия.
        if self.view.blur_controller.blur_regions:
            self.view.blur_controller._force_blur_recompute()
        self._drag_blur_needs_recompute = False

        self.view._interaction_dragging = False
        self.view.widget_manager.update_floating_widgets_visibility()
        self._drag_items = []
        self._drag_old_positions = []
        self._drag_old_rects = []
        self._drag_start_scene_pos = QPointF()
        self._drag_start_view_pos = QPoint()
        self._drag_start_scroll = QPoint()
        self._drag_scene_prepared = False
        self._drag_start_item_pos = QPointF()
        self._drag_old_background = None
        self._drag_old_blur_state = None

        # Внутренние операции завершения drag (пересчёт blur, расширение
        # подложки, обновление ручек) могут менять active blur. Selection же
        # должно остаться тем же самым набором объектов, с которого начался
        # drag. Восстанавливаем его последним — перед следующим кликом.
        selection_snapshot = [
            it for it in self._drag_selection_snapshot
            if not sip.isdeleted(it) and it.scene() is self.view.scene()
        ]
        self.view.scene().clearSelection()
        for it in selection_snapshot:
            it.setSelected(True)
        self._drag_selection_snapshot = []

        self.view._update_pasted_image_handles()
        self.view._update_blur_region_handles()
        # _update_blur_region_handles управляет только визуальным active
        # состоянием blur и не должен менять восстановленное выделение.
        self.invalidate_cursor_cache()
        return True

    def _handle_rubber_band_release(self, event) -> bool:
        """Завершение рамки выделения ПКМ."""
        if not self.rubber_band_active or event.button() != Qt.RightButton:
            return False

        # Сохраняем прямоугольник рамки до её удаления
        rect = self.rubber_band_item.rect() if self.rubber_band_item else QRectF()
        self.view.scene().removeItem(self.rubber_band_item)
        self.rubber_band_item = None
        self.rubber_band_active = False
        self.rubber_band_start = None

        # Проверяем, был ли ПКМ от активного инструмента
        if self._right_click_from_tool:
            # Определяем, было ли движение (рамка больше порога)
            threshold = 5
            significant_move = (rect.width() > threshold or rect.height() > threshold)

            if significant_move:
                # Выделяем элементы, пересекающие рамку
                for item in self.view.scene().items():
                    if self.view._is_background_item(item):
                        continue
                    li = self.view._item_for_manipulation(item)
                    if li.sceneBoundingRect().intersects(rect):
                        li.setSelected(True)
            else:
                # Одиночный клик: если было выделение, мы его уже сняли,
                # поэтому просто переключаем режим
                if not self._right_click_had_selection:
                    self._handle_tool_mode_cycle()

            # Сбрасываем флаги
            self._right_click_from_tool = False
            self._right_click_had_selection = False
            self._right_click_press_pos = None
        else:
            # Обычная рамка для указателя
            for item in self.view.scene().items():
                if self.view._is_background_item(item):
                    continue
                li = self.view._item_for_manipulation(item)
                if li.sceneBoundingRect().intersects(rect):
                    li.setSelected(True)
            self._restore_tool_if_needed()

        self.view.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.view.viewport().update()
        return True

    # ==============================================================
    # Циклическое переключение подрежимов при активном инструменте
    # ==============================================================

    def _handle_tool_mode_cycle(self) -> bool:
        """ПКМ при активном инструменте рисования."""
        selected = self.view.scene().selectedItems()
        non_bg_selected = [it for it in selected if not self.view._is_background_item(it)]

        # Если есть выделение — снимаем его и ничего не переключаем
        if non_bg_selected:
            self.view.scene().clearSelection()
            self.view._invalidate_cursor_cache()
            return True

        # Выделения нет — циклируем подрежим активного инструмента
        tool = self.view.current_tool
        if tool == 'rect':
            self._cycle_rect_mode()
        elif tool == 'ellipse':
            self._cycle_ellipse_mode()
        elif tool == 'arrow':
            self._cycle_arrow_mode()
        elif tool == 'line':
            self._cycle_line_mode()
        elif tool == 'text':
            self._cycle_text_bg()
        else:
            return False

        self.view._invalidate_cursor_cache()
        self.view.widget_manager.update_floating_widgets_visibility()
        return True

    def _cycle_rect_mode(self):
        modes = ['rect', 'square', 'filled']
        current = self.view.shape_mode
        idx = modes.index(current) if current in modes else 0
        new_mode = modes[(idx + 1) % len(modes)]
        self.view.shape_mode = new_mode
        self.view.shape_mode_widget.set_current_mode(new_mode)

    def _cycle_ellipse_mode(self):
        modes = ['ellipse', 'circle', 'cloud']
        current = self.view.ellipse_mode
        idx = modes.index(current) if current in modes else 0
        new_mode = modes[(idx + 1) % len(modes)]
        self.view.ellipse_mode = new_mode
        self.view.ellipse_mode_widget.set_current_mode(new_mode)

    def _cycle_arrow_mode(self):
        modes = ['straight', 'curved', 'dimension']
        current = self.view.arrow_mode
        idx = modes.index(current) if current in modes else 0
        new_mode = modes[(idx + 1) % len(modes)]
        self.view.arrow_mode = new_mode
        self.view.arrow_mode_widget.set_current_mode(new_mode)

    def _cycle_line_mode(self):
        modes = ['straight', 'dashed', 'wavy']
        current = self.view.line_mode
        idx = modes.index(current) if current in modes else 0
        new_mode = modes[(idx + 1) % len(modes)]
        self.view.line_mode = new_mode
        self.view.line_mode_widget.set_current_mode(new_mode)

    def _cycle_text_bg(self):
        backgrounds = [None, 'white', 'black']
        widget = self.view.text_format_widget
        current = widget._current_bg
        if current not in backgrounds:
            current = None
        idx = backgrounds.index(current)
        new_bg_key = backgrounds[(idx + 1) % len(backgrounds)]

        # Обновляем виджет и текущее значение фона
        widget.set_current_bg(new_bg_key)
        self.view.widget_manager._on_text_bg_changed(new_bg_key)

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
        self.view.setDragMode(QGraphicsView.NoDrag)
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