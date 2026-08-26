"""
Модуль: view.py
Описание: Основной виджет редактора (EditorView) на базе QGraphicsView.
"""

import math
from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF, QPoint, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import (QPainter, QPen, QColor, QPolygonF, QFont, QImage,
                         QIcon, QPainterPath, QCursor, QBrush, QPixmap)
from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsRectItem,
                             QGraphicsEllipseItem, QGraphicsPixmapItem,
                             QGraphicsTextItem, QGraphicsItem, QStyle,
                             QInputDialog, QLabel)

from .constants import MIN_RECT_SIZE, MIN_ARROW_LENGTH
from .items import (TextItem, DimensionTextItem, RectangleItem, EllipseItem,
                    FilledRectItem, LineItem, WavyLineItem, ArrowItem,
                    CurvedArrowItem, DimensionItem, CloudItem)
from .items.pasted_image_item import PastedImageItem
from .items.blur_region_item import BlurRegionItem
from .widgets.zoom_widget import ZoomWidget
from .widgets.text_format_widget import TextFormatWidget
from .widgets.info_widget import InfoWidget
from .widgets.mode_widgets import (ShapeModeWidget, ShapeModeWidgetEllipse,
                                   ShapeModeWidgetArrow, LineModeWidget)
from .history import (HistoryManager, AddItemCommand, RemoveItemCommand,
                      MoveItemCommand, MoveItemsCommand, ChangePenCommand,
                      AddPastedImageCommand, RemovePastedImageCommand,
                      ResizePastedImageCommand, CropPastedImageCommand,
                      RotatePastedImageCommand, RemoveSelectedItemsCommand,
                      MoveBlurRegionCommand, ResizeBlurRegionCommand)
from .image_edit_controller import ImageEditController
from .ui.layout_manager import LayoutManager
from .tools import RectTool, EllipseTool, LineTool, ArrowTool, TextTool


class EditorView(QGraphicsView):
    TEXT_FORMAT_TOP_OFFSET = 10
    TEXT_FORMAT_RIGHT_OFFSET = 8
    zoomChangedByWheel = pyqtSignal(int)
    crop_mode_changed = pyqtSignal(bool)
    blur_mode_changed = pyqtSignal(bool)

    def __init__(self, scene):
        super().__init__(scene)
        # ЭТАП 2: SmartViewportUpdate вместо FullViewportUpdate
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.current_tool = None
        self.start_point = None
        self.temp_item = None
        self.current_pen_color = QColor(255, 0, 0)
        self.pen_width = 2
        self.text_size = 10
        self.auto_fit = True
        self.normal_background_color = QColor(235, 242, 250)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(self.normal_background_color)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.right_click_temp_pointer = False
        self.previous_tool_for_right_click = None
        self.ctrl_pressed = False
        self.modifier_temp_pointer = False
        self.previous_tool_for_modifier = None
        self.rubber_band_active = False
        self.rubber_band_start = None
        self.rubber_band_item = None
        self.active_text_item = None
        self.current_text_bg = None
        self._first_click_after_activation = True
        self.shape_mode = 'rect'
        self.ellipse_mode = 'ellipse'
        self.arrow_mode = 'straight'
        self.line_mode = 'straight'
        self.setCursor(Qt.CrossCursor)
        self._pan_active = False
        self._pan_start_pos = QPoint()
        self._pan_start_scroll = QPoint()

        self.pasted_images = []
        self._resizing_pasted_item = None
        self._resize_handle = None
        self._resize_start_rect = None
        self._resize_start_scale = 1.0

        self._drag_items = []
        self._drag_old_positions = []
        self._drag_old_rects = []
        self._drag_start_scene_pos = QPointF()
        self._drag_start_item_pos = QPointF()
        self._drag_blur_needs_recompute = False

        self.history = HistoryManager()
        self.image_editor = ImageEditController(self)

        self.zoom_widget = ZoomWidget(self)
        self.zoom_widget.zoomChanged.connect(self._on_zoom_widget_changed)
        self.zoom_widget.fitRequested.connect(self._fit_to_view)

        self.text_format_widget = TextFormatWidget(self)
        self.text_format_widget.bgChanged.connect(self._on_text_bg_changed)
        self.text_format_widget.setVisible(False)

        self.shape_mode_widget = ShapeModeWidget(self)
        self.shape_mode_widget.modeChanged.connect(self._on_shape_mode_changed)
        self.shape_mode_widget.setVisible(False)

        self.ellipse_mode_widget = ShapeModeWidgetEllipse(self)
        self.ellipse_mode_widget.modeChanged.connect(self._on_ellipse_mode_changed)
        self.ellipse_mode_widget.setVisible(False)

        self.arrow_mode_widget = ShapeModeWidgetArrow(self)
        self.arrow_mode_widget.modeChanged.connect(self._on_arrow_mode_changed)
        self.arrow_mode_widget.setVisible(False)

        self.line_mode_widget = LineModeWidget(self)
        self.line_mode_widget.modeChanged.connect(self._on_line_mode_changed)
        self.line_mode_widget.setVisible(False)

        self.info_widget = InfoWidget(self)
        self.info_widget.setVisible(True)

        self.status_label = QLabel(self)
        self.status_label.setAttribute(Qt.WA_TranslucentBackground)
        self.status_label.setStyleSheet(
            "background-color: rgba(255,255,255,180); color: #333; "
            "border-radius: 6px; padding: 4px 8px;"
        )
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.status_label.setWordWrap(False)
        self.status_label.setVisible(False)

        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._restore_status_label)
        self._resolution_text = ""

        self.layout_manager = LayoutManager(self)
        self._tool = None

        self._update_info_widget_content(self.current_pen_color, self.pen_width)

        for w in (self.zoom_widget, self.text_format_widget,
                  self.shape_mode_widget, self.ellipse_mode_widget,
                  self.arrow_mode_widget, self.line_mode_widget,
                  self.info_widget, self.status_label):
            w.setCursor(Qt.ArrowCursor)

        self.scene().selectionChanged.connect(self._sync_selection_properties)
        self.scene().selectionChanged.connect(self._update_floating_widgets_visibility)
        self.scene().selectionChanged.connect(self._update_blur_region_handles)

    # ==============================================================
    # Вспомогательные
    # ==============================================================
    def _is_background_item(self, item):
        if item is None:
            return False
        curr = item
        while curr is not None:
            if curr is self.image_editor.background_item:
                return True
            curr = curr.parentItem()
        return False

    def _deactivate_active_text(self):
        if self.active_text_item is None:
            return
        old_item = self.active_text_item
        self.active_text_item = None
        if old_item._editable:
            old_item.setEditable(False)

    # ==============================================================
    # Undo / Redo
    # ==============================================================
    def undo(self):
        old = self._get_background_pixmap_size()
        self.history.undo()
        new = self._get_background_pixmap_size()
        if old != new:
            self.fit_background_to_view()
        self._update_after_history_change()

    def redo(self):
        old = self._get_background_pixmap_size()
        self.history.redo()
        new = self._get_background_pixmap_size()
        if old != new:
            self.fit_background_to_view()
        self._update_after_history_change()

    def _get_background_pixmap_size(self):
        bg = self.image_editor.background_item
        if bg is None or sip.isdeleted(bg) or bg.scene() is not self.scene():
            return None
        return bg.pixmap().size()

    def _update_after_history_change(self):
        self.viewport().update()
        if (self.image_editor.background_item and
                not sip.isdeleted(self.image_editor.background_item) and
                self.image_editor.background_item.scene() is self.scene()):
            self.setSceneRect(QRectF(self.image_editor.background_item.pixmap().rect()))
            self.update_resolution_from_background()
        self._update_floating_widgets_visibility()
        self._update_pasted_image_handles()
        self._update_blur_region_handles()

    def update_resolution_from_background(self):
        if (self.image_editor.background_item and
                not sip.isdeleted(self.image_editor.background_item) and
                self.image_editor.background_item.scene() is self.scene()):
            pixmap = self.image_editor.background_item.pixmap()
            self.set_resolution_text(f"{pixmap.width()}×{pixmap.height()}")
        else:
            self.set_resolution_text("")

    def fit_background_to_view(self):
        bg = self.image_editor.background_item
        if bg is None or sip.isdeleted(bg) or bg.scene() is not self.scene():
            return
        self.fitInView(bg, Qt.KeepAspectRatio)
        self.auto_fit = False
        scale = self.transform().m11() * 100
        self.zoom_widget.set_zoom(scale)

    # ==============================================================
    # Свойства и делегаты
    # ==============================================================
    @property
    def crop_mode(self):
        return self.image_editor.crop_mode

    @property
    def blur_mode(self):
        return self.image_editor.blur_mode

    @property
    def background_item(self):
        return self.image_editor.background_item

    def set_background_item(self, item):
        self.image_editor.set_background_item(item)

    def start_crop_mode(self):
        selected_pasted = [it for it in self.scene().selectedItems()
                           if isinstance(it, PastedImageItem)]
        if selected_pasted:
            self.image_editor.crop_target_item = selected_pasted[0]
        else:
            self.image_editor.crop_target_item = self.image_editor.background_item
        self.image_editor.start_crop_mode()

    def cancel_crop_mode(self):
        self.image_editor.cancel_crop_mode()

    def apply_crop(self):
        self.image_editor.apply_crop()

    def start_blur_mode(self):
        self.image_editor.start_blur_mode()

    def cancel_blur_mode(self):
        self.image_editor.cancel_blur_mode()

    def rotate_image(self, angle):
        self.image_editor.rotate_image(angle)

    # ==============================================================
    # Вставленные изображения
    # ==============================================================
    def add_pasted_image(self, pixmap):
        item = PastedImageItem(pixmap, self)
        self.pasted_images.append(item)
        self.scene().addItem(item)
        center = self.mapToScene(self.viewport().rect().center())
        item.setPos(center - QPointF(pixmap.width() / 2, pixmap.height() / 2))
        viewport_rect = self.viewport().rect()
        max_w = viewport_rect.width() * 0.8
        max_h = viewport_rect.height() * 0.8
        if pixmap.width() > max_w or pixmap.height() > max_h:
            scale = min(max_w / pixmap.width(), max_h / pixmap.height())
            item.set_image_scale(scale)
        self.history.push(AddPastedImageCommand(self.scene(), item, self))
        self.scene().clearSelection()
        item.setSelected(True)
        item.show_handles()
        return item

    def remove_pasted_image(self, item):
        if item in self.pasted_images:
            self.history.push(RemovePastedImageCommand(self.scene(), item, self))

    def clear_pasted_images(self):
        for item in self.pasted_images[:]:
            item.hide_handles()
            self.scene().removeItem(item)
        self.pasted_images.clear()

    def _update_pasted_image_handles(self):
        selected_ids = {id(it) for it in self.scene().selectedItems()
                        if isinstance(it, PastedImageItem)}
        for item in self.pasted_images:
            if id(item) in selected_ids:
                item.show_handles()
            else:
                item.hide_handles()

    def hide_pasted_image_handles_for_render(self):
        for item in self.pasted_images:
            item.hide_handles()

    def show_pasted_image_handles_after_render(self):
        for item in self.pasted_images:
            if item.isSelected():
                item.show_handles()

    # ==============================================================
    # Ручки зон размытия при множественном выделении
    # ЭТАП 1: защита от удалённых C++ объектов при закрытии
    # ==============================================================
    def _update_blur_region_handles(self):
        """Скрывает ручки зон размытия при множественном выделении."""
        try:
            if self.image_editor.blur_outside_mode:
                return
            if self.image_editor.blur_interaction is not None:
                return

            selected = self.scene().selectedItems()
            non_bg_selected = [it for it in selected if not self._is_background_item(it)]

            if len(non_bg_selected) > 1:
                self.image_editor._clear_active_blur()
            elif len(non_bg_selected) == 1:
                item = non_bg_selected[0]
                if isinstance(item, BlurRegionItem) and not sip.isdeleted(item):
                    try:
                        idx = self.image_editor.blur_region_items.index(item)
                        self.image_editor._set_active_blur(idx)
                    except ValueError:
                        pass
                else:
                    self.image_editor._clear_active_blur()
            else:
                self.image_editor._clear_active_blur()
        except RuntimeError:
            pass  # C++ объекты уже удалены (закрытие приложения)

    # ==============================================================
    # Drag & Drop
    # ==============================================================
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            for url in e.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(
                        ('.png', '.jpg', '.jpeg', '.bmp')):
                    e.acceptProposedAction()
                    return
        e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            for url in e.mimeData().urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        self.add_pasted_image(pixmap)
            e.acceptProposedAction()
        else:
            e.ignore()

    # ==============================================================
    # Статусный виджет
    # ==============================================================
    def set_resolution_text(self, text):
        self._resolution_text = text
        self.status_label.setText(text)
        self.status_label.setToolTip(text if text else "")
        self.status_label.setVisible(bool(text))
        self.layout_manager.update_status_label_position()

    def show_status_message(self, message, duration=15000):
        self.status_label.setText(message)
        self.status_label.setToolTip(message)
        self.status_label.setVisible(True)
        self.layout_manager.update_status_label_position()
        self._status_timer.start(duration)

    def _restore_status_label(self):
        if self._resolution_text:
            self.status_label.setText(self._resolution_text)
        else:
            self.status_label.setVisible(False)

    # ==============================================================
    # Мышь
    # ==============================================================
    def mousePressEvent(self, e):
        sp = self.mapToScene(e.pos())
        item = self.scene().itemAt(sp, self.transform())
        li = self._item_for_manipulation(item) if item else None

        modifiers = e.modifiers()
        is_ctrl = bool(modifiers & Qt.ControlModifier)
        is_shift = bool(modifiers & Qt.ShiftModifier)

        # --- Режим Размыть ---
        if self.image_editor.blur_mode:
            is_blur_item = isinstance(li, BlurRegionItem)
            is_empty_or_bg = li is None or self._is_background_item(li)

            is_blur_handle = False
            if (self.image_editor.active_blur_index is not None and
                    self.image_editor.active_blur_index < len(
                        self.image_editor.blur_region_items)):
                active_blur = self.image_editor.blur_region_items[
                    self.image_editor.active_blur_index]
                if active_blur.handles:
                    hid = active_blur.handles.hit_test(QPointF(e.pos()))
                    if hid:
                        is_blur_handle = True

            skip_blur_in_blur_mode = False
            if is_ctrl or is_shift:
                skip_blur_in_blur_mode = True
            elif is_blur_item:
                selected_items = self.scene().selectedItems()
                if li.isSelected() and len(selected_items) > 1:
                    skip_blur_in_blur_mode = True

            if not skip_blur_in_blur_mode and (is_blur_item or is_empty_or_bg or is_blur_handle):
                if self.image_editor.handle_mouse_press(e):
                    e.accept()
                    return

        # --- Режим Обрезки ---
        elif self.image_editor.crop_mode:
            if self.image_editor.handle_mouse_press(e):
                e.accept()
                return

        # --- Маркеры вставленных изображений ---
        if e.button() == Qt.LeftButton:
            for p_item in self.pasted_images:
                if p_item.isSelected() and p_item.handles:
                    handle_id = p_item.handles.hit_test(e.pos())
                    if handle_id:
                        self._resizing_pasted_item = p_item
                        self._resize_handle = handle_id
                        self._resize_start_rect = p_item.mapRectToScene(p_item.boundingRect())
                        self._resize_start_scale = p_item.scale
                        e.accept()
                        return

        # --- Зоны размытия ВНЕ режима размытия ---
        if (e.button() == Qt.LeftButton and
                not self.image_editor.crop_mode and
                not self.image_editor.blur_mode):
            skip_blur_handler = False
            if is_ctrl or is_shift:
                skip_blur_handler = True
            elif li is not None and isinstance(li, BlurRegionItem):
                selected_items = self.scene().selectedItems()
                if li.isSelected() and len(selected_items) > 1:
                    skip_blur_handler = True

            if not skip_blur_handler:
                if self.image_editor.handle_blur_region_press_outside(e):
                    e.accept()
                    return

        # --- Панорамирование ---
        if e.button() == Qt.MiddleButton:
            if self.active_text_item and self.active_text_item._editable:
                e.accept()
                return
            self._pan_active = True
            self._pan_start_pos = e.pos()
            self._pan_start_scroll = QPoint(
                self.horizontalScrollBar().value(),
                self.verticalScrollBar().value())
            self.viewport().setCursor(Qt.ClosedHandCursor)
            e.accept()
            return

        # --- Правая кнопка ---
        if e.button() == Qt.RightButton:
            if self.active_text_item and self.active_text_item._editable:
                e.accept()
                return
            right_item = None
            for it in self.scene().items(sp):
                if not self._is_background_item(it):
                    right_item = it
                    break
            if right_item:
                right_li = self._item_for_manipulation(right_item)
                self.scene().clearSelection()
                right_li.setSelected(True)
                self._activate_temp_pointer('right_click')
            else:
                self.scene().clearSelection()
                self._activate_temp_pointer('right_click')
                self.rubber_band_active = True
                self.rubber_band_start = sp
                pen = QPen(QColor(255, 200, 0), 3, Qt.DashLine)
                pen.setCosmetic(True)  # толщина не зависит от масштаба
                self.rubber_band_item = QGraphicsRectItem(QRectF(sp, sp))
                self.rubber_band_item.setPen(pen)
                # Поверх всех элементов
                self.rubber_band_item.setZValue(10000)
                self.rubber_band_item.setFlag(QGraphicsRectItem.ItemIsMovable, False)
                self.rubber_band_item.setFlag(QGraphicsRectItem.ItemIsSelectable, False)
                self.scene().addItem(self.rubber_band_item)
                # Временно переключаемся на FullViewportUpdate для перерисовки рамки
                self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
                self.viewport().update()
            e.accept()
            return

        # --- Левая кнопка ---
        if e.button() == Qt.LeftButton:
            if isinstance(item, TextItem) and item._editable:
                super().mousePressEvent(e)
                e.accept()
                return

            if self.current_tool == 'text':
                if isinstance(li, TextItem):
                    if self.active_text_item is not None and self.active_text_item is not li:
                        self._deactivate_active_text()
                else:
                    if self.active_text_item and self.active_text_item._editable:
                        self._deactivate_active_text()
                    if li is None or self._is_background_item(li):
                        if self._first_click_after_activation:
                            ti = TextItem(self, bg_color=self.current_text_bg)
                            ti.setDefaultTextColor(self.current_pen_color)
                            font = QFont()
                            font.setPointSize(self.text_size * 4)
                            ti.setFont(font)
                            ti.setPos(sp)
                            self.scene().addItem(ti)
                            self.active_text_item = ti
                            ti.setSelected(True)
                            ti.setEditable(True)
                            self._first_click_after_activation = False
                            self.history.push(AddItemCommand(self.scene(), ti))
                            e.accept()
                            return

            # Общая логика выделения и перетаскивания
            if li is not None and not self._is_background_item(li):
                if li.isSelected():
                    if is_ctrl:
                        li.setSelected(False)
                        e.accept()
                        return
                else:
                    if not (is_ctrl or is_shift):
                        self.scene().clearSelection()
                    li.setSelected(True)

                selected = self.scene().selectedItems()
                self._drag_items = [it for it in selected
                                    if not self._is_background_item(it)]

                if not self._drag_items:
                    e.accept()
                    return

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
                e.accept()
                return

            # Временный указатель
            if ((self.right_click_temp_pointer or self.modifier_temp_pointer)
                    and self.current_tool is None):
                if li is None or self._is_background_item(li):
                    if self.right_click_temp_pointer:
                        self.scene().clearSelection()
                        self.right_click_temp_pointer = False
                        if not self.modifier_temp_pointer:
                            self._restore_tool_if_needed()
                    e.accept()
                    return
                else:
                    super().mousePressEvent(e)
                    e.accept()
                    return

            # Рисование
            if self.current_tool in ('rect', 'ellipse', 'arrow', 'line'):
                if self._tool is not None:
                    self.start_point = sp
                    self.temp_item = self._tool.start_draw(sp)
                    if self.temp_item:
                        self.scene().addItem(self.temp_item)
                e.accept()
                return

            super().mousePressEvent(e)
            e.accept()
            return

        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not self._drag_items:
            if self.image_editor.blur_mode:
                if self.image_editor.handle_mouse_move(e):
                    e.accept()
                    return
            elif self.image_editor.crop_mode:
                if self.image_editor.handle_mouse_move(e):
                    e.accept()
                    return

        if self._resizing_pasted_item is not None:
            sp = self.mapToScene(e.pos())
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
            elif handle_id == 'tm':
                top = min(sp.y(), bottom - min_size)
            elif handle_id == 'bm':
                bottom = max(sp.y(), top + min_size)
            elif handle_id == 'lm':
                left = min(sp.x(), right - min_size)
            elif handle_id == 'rm':
                right = max(sp.x(), left + min_size)

            new_rect = QRectF(left, top, right - left, bottom - top).normalized()
            local_rect = item.mapRectFromScene(new_rect)
            scale_x = local_rect.width() / item.original_pixmap.width()
            scale_y = local_rect.height() / item.original_pixmap.height()
            scale = min(scale_x, scale_y)
            item.set_image_scale(scale)
            e.accept()
            return

        if not self._drag_items:
            if not self.image_editor.crop_mode and not self.image_editor.blur_mode:
                if self.image_editor.handle_blur_region_move_outside(e):
                    e.accept()
                    return

        if self._pan_active:
            dx = e.pos().x() - self._pan_start_pos.x()
            dy = e.pos().y() - self._pan_start_pos.y()
            scale = self.transform().m11()
            if scale != 0:
                self.horizontalScrollBar().setValue(
                    int(self._pan_start_scroll.x() - dx / scale))
                self.verticalScrollBar().setValue(
                    int(self._pan_start_scroll.y() - dy / scale))
            e.accept()
            return

        # Групповое перетаскивание
        if self._drag_items:
            current_scene_pos = self.mapToScene(e.pos())
            delta = current_scene_pos - self._drag_start_scene_pos

            if e.modifiers() & Qt.ShiftModifier:
                if abs(delta.x()) > abs(delta.y()):
                    delta.setY(0.0)
                else:
                    delta.setX(0.0)

            for idx, drag_item in enumerate(self._drag_items):
                if isinstance(drag_item, BlurRegionItem):
                    old_rect = self._drag_old_rects[idx]
                    new_rect = old_rect.translated(delta)
                    if self.image_editor.background_item is not None:
                        image_rect = QRectF(
                            self.image_editor.background_item.pixmap().rect())
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
                        idx_blur = self.image_editor.blur_region_items.index(drag_item)
                        self.image_editor.blur_regions[idx_blur] = new_rect
                        self._drag_blur_needs_recompute = True
                        self.image_editor._schedule_blur_recompute()
                    except ValueError:
                        pass
                    if drag_item.handles:
                        drag_item.handles.update_handles(new_rect)
                else:
                    old_pos = self._drag_old_positions[idx]
                    new_pos = old_pos + delta
                    if self.image_editor.background_item is not None:
                        image_rect = QRectF(
                            self.image_editor.background_item.pixmap().rect())
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

            self.scene().update()
            self._update_pasted_image_handles()
            e.accept()
            return

        self._update_cursor(e.pos())

        if self.temp_item and self._tool is not None and self.current_tool not in ('text',):
            sp = self.mapToScene(e.pos())
            self._tool.update_draw(self.temp_item, sp, e.modifiers())
            e.accept()
            return

        # Рамка выделения ПКМ — перерисовка в режиме FullViewportUpdate
        if self.rubber_band_active and self.rubber_band_item:
            cp = self.mapToScene(e.pos())
            self.rubber_band_item.setRect(
                QRectF(self.rubber_band_start, cp).normalized())
            e.accept()
            return

        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if not self._drag_items:
            if self.image_editor.blur_mode:
                if self.image_editor.handle_mouse_release(e):
                    e.accept()
                    return
            elif self.image_editor.crop_mode:
                if self.image_editor.handle_mouse_release(e):
                    e.accept()
                    return

        if self._resizing_pasted_item is not None:
            item = self._resizing_pasted_item
            old_scale = self._resize_start_scale
            new_scale = item.scale
            if old_scale != new_scale:
                self.history.push(
                    ResizePastedImageCommand(item, old_scale, new_scale))
            self._resizing_pasted_item = None
            self._resize_handle = None
            self._resize_start_rect = None
            self._resize_start_scale = 1.0
            self._update_pasted_image_handles()
            e.accept()
            return

        if not self._drag_items:
            if (e.button() == Qt.LeftButton and
                    not self.image_editor.crop_mode and
                    not self.image_editor.blur_mode):
                if self.image_editor.handle_blur_region_release_outside(e):
                    e.accept()
                    return

        if e.button() == Qt.MiddleButton and self._pan_active:
            self._pan_active = False
            self._refresh_cursor()
            e.accept()
            return

        # Завершение группового перетаскивания
        if self._drag_items:
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
                    self.history.push(
                        MoveItemsCommand(normal_items, old_positions, new_positions))

            for idx, it in enumerate(self._drag_items):
                if isinstance(it, BlurRegionItem):
                    old_rect = self._drag_old_rects[idx]
                    new_rect = it.rect()
                    if old_rect != new_rect:
                        try:
                            idx_blur = self.image_editor.blur_region_items.index(it)
                            self.history.push(MoveBlurRegionCommand(
                                self.image_editor, idx_blur, old_rect, new_rect))
                        except ValueError:
                            pass

            if self._drag_blur_needs_recompute:
                self.image_editor._force_blur_recompute()
                self._drag_blur_needs_recompute = False

            self._drag_items = []
            self._drag_old_positions = []
            self._drag_old_rects = []
            self._drag_start_scene_pos = QPointF()
            self._drag_start_item_pos = QPointF()
            self._update_pasted_image_handles()
            self._update_blur_region_handles()
            e.accept()
            return

        if self.rubber_band_active and e.button() == Qt.RightButton:
            if self.rubber_band_item:
                self.scene().removeItem(self.rubber_band_item)
                rect = self.rubber_band_item.rect()
                self.rubber_band_item = None
                for item in self.scene().items():
                    if self._is_background_item(item):
                        continue
                    li = self._item_for_manipulation(item)
                    if li.sceneBoundingRect().intersects(rect):
                        li.setSelected(True)
            self.rubber_band_active = False
            self.rubber_band_start = None
            # Возвращаем SmartViewportUpdate после завершения рамки
            self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
            self.viewport().update()
            e.accept()
            return

        if (self.temp_item and e.button() == Qt.LeftButton and
                self._tool is not None and self.current_tool not in ('text',)):
            if self._tool.finish_draw(self.temp_item):
                self.scene().clearSelection()
                self.temp_item.setSelected(True)
                self.history.push(AddItemCommand(self.scene(), self.temp_item))
            else:
                self.scene().removeItem(self.temp_item)
            self.temp_item = None
            self.start_point = None
            e.accept()
            return

        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        sp = self.mapToScene(e.pos())
        item = self.scene().itemAt(sp, self.transform())
        li = self._item_for_manipulation(item) if item else None

        if isinstance(li, TextItem):
            if self.active_text_item is not None and self.active_text_item is not li:
                self._deactivate_active_text()
            self.active_text_item = li
            li.setSelected(True)
            li.setEditable(True)
            if self.current_tool == 'text':
                self._first_click_after_activation = False
            e.accept()
            return

        if self.current_tool == 'text' and (li is None or self._is_background_item(li)):
            self._deactivate_active_text()
            ti = TextItem(self, bg_color=self.current_text_bg)
            ti.setDefaultTextColor(self.current_pen_color)
            font = QFont()
            font.setPointSize(self.text_size * 4)
            ti.setFont(font)
            ti.setPos(sp)
            self.scene().addItem(ti)
            self.active_text_item = ti
            ti.setSelected(True)
            ti.setEditable(True)
            self._first_click_after_activation = False
            self.history.push(AddItemCommand(self.scene(), ti))
            e.accept()
            return

        super().mouseDoubleClickEvent(e)

    # ==============================================================
    # Клавиатура
    # ==============================================================
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_A and e.modifiers() & Qt.ControlModifier:
            if self.active_text_item and self.active_text_item._editable:
                super().keyPressEvent(e)
                return
            self.select_all_items()
            e.accept()
            return

        if e.key() == Qt.Key_Delete:
            self.delete_selected()
            e.accept()
            return

        if e.key() == Qt.Key_Escape:
            if self.image_editor.crop_mode:
                self.image_editor.cancel_crop_mode()
                e.accept()
                return
            if self.image_editor.blur_mode:
                self.image_editor.handle_blur_escape()
                e.accept()
                return
            self.scene().clearSelection()
            self._deactivate_active_text()
            self._restore_tool_if_needed()
            e.accept()
            return

        if e.key() == Qt.Key_Control:
            self.ctrl_pressed = True
            if self.current_tool:
                self._activate_temp_pointer('modifier')
            e.accept()
            return

        if e.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            if self.active_text_item and self.active_text_item._editable:
                super().keyPressEvent(e)
                return

            if self.image_editor.active_blur_index is not None:
                idx = self.image_editor.active_blur_index
                old_rect = self.image_editor.blur_regions[idx]
                dx = dy = 0
                step = 10 if (e.modifiers() & Qt.ShiftModifier) else 1
                if e.key() == Qt.Key_Left: dx = -step
                elif e.key() == Qt.Key_Right: dx = step
                elif e.key() == Qt.Key_Up: dy = -step
                elif e.key() == Qt.Key_Down: dy = step

                new_rect = self.image_editor._constrain_move(old_rect, QPointF(dx, dy))
                if new_rect != old_rect:
                    self.image_editor.blur_regions[idx] = new_rect
                    self.image_editor.blur_region_items[idx].update_rect(new_rect)
                    self.image_editor._force_blur_recompute()
                    self.history.push(MoveBlurRegionCommand(
                        self.image_editor, idx, old_rect, new_rect))
                e.accept()
                return

            selected = self.scene().selectedItems()
            items = [it for it in selected if not self._is_background_item(it)]
            if items:
                dx = dy = 0
                step = 10 if (e.modifiers() & Qt.ShiftModifier) else 1
                if e.key() == Qt.Key_Left: dx = -step
                elif e.key() == Qt.Key_Right: dx = step
                elif e.key() == Qt.Key_Up: dy = -step
                elif e.key() == Qt.Key_Down: dy = step

                normal_items = []
                normal_old = []
                normal_new = []

                for it in items:
                    old_pos = it.pos()
                    new_pos = old_pos + QPointF(dx, dy)
                    if self.image_editor.background_item is not None:
                        image_rect = QRectF(
                            self.image_editor.background_item.pixmap().rect())
                        item_rect = it.boundingRect()
                        proposed = QRectF(new_pos + item_rect.topLeft(),
                                          new_pos + item_rect.bottomRight())
                        if proposed.left() < image_rect.left():
                            new_pos.setX(new_pos.x() + (
                                image_rect.left() - proposed.left()))
                        elif proposed.right() > image_rect.right():
                            new_pos.setX(new_pos.x() - (
                                proposed.right() - image_rect.right()))
                        proposed = QRectF(new_pos + item_rect.topLeft(),
                                          new_pos + item_rect.bottomRight())
                        if proposed.top() < image_rect.top():
                            new_pos.setY(new_pos.y() + (
                                image_rect.top() - proposed.top()))
                        elif proposed.bottom() > image_rect.bottom():
                            new_pos.setY(new_pos.y() - (
                                proposed.bottom() - image_rect.bottom()))

                    if isinstance(it, BlurRegionItem):
                        old_rect = it.rect()
                        new_rect = old_rect.translated(dx, dy)
                        if old_rect != new_rect:
                            try:
                                idx_blur = self.image_editor.blur_region_items.index(it)
                                self.history.push(MoveBlurRegionCommand(
                                    self.image_editor, idx_blur, old_rect, new_rect))
                            except ValueError:
                                pass
                    else:
                        normal_items.append(it)
                        normal_old.append(old_pos)
                        normal_new.append(new_pos)

                if normal_items:
                    for i_n, nit in enumerate(normal_items):
                        nit.setPos(normal_new[i_n])
                    self.history.push(
                        MoveItemsCommand(normal_items, normal_old, normal_new))

                self._update_pasted_image_handles()
                self._update_blur_region_handles()
                e.accept()
                return

        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Control:
            self.ctrl_pressed = False
            if not self.ctrl_pressed:
                self._restore_tool_if_needed()
            e.accept()
            return
        super().keyReleaseEvent(e)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ShiftModifier:
            d = e.angleDelta().y()
            if d != 0:
                cur = self.transform().m11()
                factor = 1.1 if d > 0 else 0.9
                new_scale = cur * factor
                new_percent = max(10, min(400, int(new_scale * 100)))
                self.resetTransform()
                self.scale(new_percent / 100, new_percent / 100)
                self.auto_fit = False
                self.zoomChangedByWheel.emit(new_percent)
                e.accept()
                return
            e.accept()
            return
        super().wheelEvent(e)

    # ==============================================================
    # Выделение / Удаление
    # ==============================================================
    def select_all_items(self):
        self.scene().clearSelection()
        for item in self.scene().items():
            if item.parentItem() is None and not self._is_background_item(item):
                item.setSelected(True)

    def delete_selected(self):
        if self.image_editor.active_blur_index is not None:
            self.image_editor.delete_active_blur_region()
            return

        items = self.scene().selectedItems()
        if not items:
            return

        pasted_items = [it for it in items if isinstance(it, PastedImageItem)]
        other_items = [it for it in items
                       if not isinstance(it, PastedImageItem)
                       and not isinstance(it, BlurRegionItem)
                       and not self._is_background_item(it)]

        blur_indices = []
        for idx, blur_item in enumerate(self.image_editor.blur_region_items):
            if blur_item.scene() is self.scene() and blur_item.isSelected():
                blur_indices.append(idx)

        if pasted_items or other_items or blur_indices:
            command = RemoveSelectedItemsCommand(
                self.scene(), other_items, pasted_items, blur_indices, self)
            self.history.push(command)

        self.scene().clearSelection()
        self._restore_tool_if_needed()

    def apply_current_style_to_selected(self, pen_color=None, pen_width=None):
        for item in self.scene().selectedItems():
            if isinstance(item, DimensionItem):
                if pen_color:
                    item.setPen(QPen(pen_color, item._pen.widthF()))
                if pen_width:
                    item.setPen(QPen(item._pen.color(), pen_width))
                continue
            if isinstance(item, TextItem):
                if pen_color:
                    item.setDefaultTextColor(pen_color)
                if pen_width:
                    font = item.font()
                    font.setPointSize(max(1, pen_width * 4))
                    item.setFont(font)
                item.update()
                continue
            if isinstance(item, FilledRectItem):
                if pen_color:
                    item.setBrush(QColor(pen_color.red(), pen_color.green(),
                                         pen_color.blue(), 80))
                continue
            if isinstance(item, (RectangleItem, EllipseItem, ArrowItem,
                                 CurvedArrowItem, CloudItem, LineItem, WavyLineItem)):
                current_pen = item.pen()
                new_color = pen_color if pen_color else current_pen.color()
                new_width = pen_width if pen_width else current_pen.widthF()
                new_pen = QPen(new_color, new_width)
                if isinstance(item, (RectangleItem, EllipseItem, CloudItem,
                                     LineItem, WavyLineItem)):
                    new_pen.setCapStyle(Qt.RoundCap)
                    new_pen.setJoinStyle(Qt.RoundJoin)
                    if isinstance(item, LineItem) and self.line_mode == 'dashed':
                        new_pen.setStyle(Qt.DashLine)
                elif isinstance(item, CurvedArrowItem):
                    new_pen.setCapStyle(Qt.RoundCap)
                    new_pen.setJoinStyle(Qt.RoundJoin)
                self.history.push(ChangePenCommand(item, current_pen, new_pen))

    # ==============================================================
    # Видимость виджетов
    # ==============================================================
    def _update_info_widget_content(self, color, thickness):
        self.info_widget.set_info(color, thickness)
        QTimer.singleShot(0, self.layout_manager.update_info_widget_position)

    def _sync_selection_properties(self):
        sel = self.scene().selectedItems()
        if not sel:
            self._update_info_widget_content(self.current_pen_color, self.pen_width)
            return
        item = sel[0]
        color = None
        width = None
        if isinstance(item, QGraphicsTextItem):
            color = item.defaultTextColor()
            if isinstance(item, TextItem):
                width = max(1, int(round(item.font().pointSize() / 4)))
        elif isinstance(item, (RectangleItem, EllipseItem, ArrowItem,
                               CurvedArrowItem, CloudItem, LineItem, WavyLineItem)):
            if hasattr(item, 'pen'):
                pen = item.pen()
                color = pen.color()
                width = int(pen.widthF())
            elif hasattr(item, '_pen'):
                color = item._pen.color()
                width = int(item._pen.widthF())
        elif isinstance(item, FilledRectItem):
            brush = item.brush()
            color = brush.color() if brush.style() == Qt.SolidPattern else QColor(255, 0, 0)
            width = 2
        elif isinstance(item, DimensionItem):
            color = item._pen.color()
            width = int(item._pen.widthF())
        else:
            return
        if color and color.isValid():
            self._update_info_widget_content(color, width if width is not None else 0)
        else:
            self._update_info_widget_content(QColor(0, 0, 0), 0)

    def _update_floating_widgets_visibility(self):
        self.shape_mode_widget.setVisible(False)
        self.ellipse_mode_widget.setVisible(False)
        self.arrow_mode_widget.setVisible(False)
        self.line_mode_widget.setVisible(False)
        self.text_format_widget.setVisible(False)

        if self.image_editor.crop_mode or self.image_editor.blur_mode:
            self.layout_manager.update_all()
            return

        if self.active_text_item is not None:
            self.text_format_widget.setVisible(True)
            self.layout_manager.update_all()
            return

        if self.current_tool == 'text':
            self.text_format_widget.setVisible(True)
            self.layout_manager.update_all()
            return

        selected = self.scene().selectedItems()
        if selected:
            all_text = all(isinstance(item, TextItem) for item in selected)
            if all_text:
                self.text_format_widget.setVisible(True)
                self.layout_manager.update_all()
                return
            self.layout_manager.update_all()
            return

        if self.current_tool == 'rect':
            self.shape_mode_widget.setVisible(True)
        elif self.current_tool == 'ellipse':
            self.ellipse_mode_widget.setVisible(True)
        elif self.current_tool == 'arrow':
            self.arrow_mode_widget.setVisible(True)
        elif self.current_tool == 'line':
            self.line_mode_widget.setVisible(True)

        self._update_pasted_image_handles()
        self.layout_manager.update_all()

    # ==============================================================
    # Обработчики сигналов виджетов
    # ==============================================================
    def _on_zoom_widget_changed(self, p):
        self.zoomChangedByWheel.emit(p)

    def _fit_to_view(self):
        bg = self.image_editor.background_item
        if bg is not None and not sip.isdeleted(bg) and bg.scene() is self.scene():
            self.fitInView(bg, Qt.KeepAspectRatio)
        elif self.scene() and self.scene().items():
            self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)
        else:
            self.resetTransform()
        self.auto_fit = False
        scale = self.transform().m11() * 100
        self.zoom_widget.set_zoom(scale)

    def _on_text_bg_changed(self, m):
        self.current_text_bg = (
            QColor(255, 255, 255, 200) if m == 'white' else
            QColor(0, 0, 0, 200) if m == 'black' else None)
        if self.active_text_item:
            self.active_text_item.bg_color = self.current_text_bg
            self.active_text_item.update()
        else:
            for item in self.scene().selectedItems():
                if isinstance(item, TextItem):
                    item.bg_color = self.current_text_bg
                    item.update()

    def _on_shape_mode_changed(self, m):
        self.shape_mode = m

    def _on_ellipse_mode_changed(self, m):
        self.ellipse_mode = m

    def _on_arrow_mode_changed(self, m):
        self.arrow_mode = m

    def _on_line_mode_changed(self, m):
        self.line_mode = m

    def update_text_format_widget_visibility(self):
        self._update_floating_widgets_visibility()

    # ==============================================================
    # Временный указатель / инструменты
    # ==============================================================
    def _activate_temp_pointer(self, src):
        if self.current_tool:
            if src == 'right_click' and not self.right_click_temp_pointer:
                self.right_click_temp_pointer = True
                self.previous_tool_for_right_click = self.current_tool
            elif src == 'modifier' and not self.modifier_temp_pointer:
                self.modifier_temp_pointer = True
                self.previous_tool_for_modifier = self.current_tool
        self.current_tool = None
        self.setDragMode(QGraphicsView.NoDrag)

    def _restore_tool_if_needed(self):
        if self.right_click_temp_pointer and not self.modifier_temp_pointer:
            self._apply_tool(self.previous_tool_for_right_click)
            self.right_click_temp_pointer = False
            self.previous_tool_for_right_click = None
            self._update_floating_widgets_visibility()
        elif self.modifier_temp_pointer and not self.right_click_temp_pointer:
            self._apply_tool(self.previous_tool_for_modifier)
            self.modifier_temp_pointer = False
            self.previous_tool_for_modifier = None
            self._update_floating_widgets_visibility()

    def _apply_tool(self, t):
        self.current_tool = t
        self.setDragMode(QGraphicsView.NoDrag if t else QGraphicsView.RubberBandDrag)

    def set_tool(self, t):
        self._deactivate_active_text()

        if self.image_editor.crop_mode:
            self.image_editor.cancel_crop_mode()
        if self.image_editor.blur_mode:
            self.image_editor.cancel_blur_mode()

        self.scene().clearSelection()

        self.right_click_temp_pointer = False
        self.previous_tool_for_right_click = None
        self.modifier_temp_pointer = False
        self.previous_tool_for_modifier = None

        self._apply_tool(t)
        self._first_click_after_activation = (t == 'text')

        if t == 'rect':
            self._tool = RectTool(self)
        elif t == 'ellipse':
            self._tool = EllipseTool(self)
        elif t == 'line':
            self._tool = LineTool(self)
        elif t == 'arrow':
            self._tool = ArrowTool(self)
        elif t == 'text':
            self._tool = TextTool(self)
        else:
            self._tool = None

        if t == 'rect':
            self.shape_mode = 'rect'
            self.shape_mode_widget.set_current_mode('rect')
        if t == 'ellipse':
            self.ellipse_mode = 'ellipse'
            self.ellipse_mode_widget.set_current_mode('ellipse')
        if t == 'arrow':
            self.arrow_mode = 'straight'
            self.arrow_mode_widget.set_current_mode('straight')
        if t == 'line':
            self.line_mode = 'straight'
            self.line_mode_widget.set_current_mode('straight')

        if not self.scene().selectedItems():
            self._update_info_widget_content(
                self.current_pen_color, self.get_current_width())

        QTimer.singleShot(0, self._refresh_cursor)
        self._update_floating_widgets_visibility()

    def set_pen_color(self, c):
        if self.scene().selectedItems():
            self.apply_current_style_to_selected(pen_color=c)
            self._sync_selection_properties()
        else:
            self.current_pen_color = c
            self._update_info_widget_content(self.current_pen_color, self.pen_width)

    def set_pen_width(self, w):
        w = max(1, min(100, int(w)))
        if self.scene().selectedItems() or self.active_text_item:
            self.apply_current_style_to_selected(pen_width=w)
            self._sync_selection_properties()
        else:
            self.pen_width = w
            self.text_size = w
            self._update_info_widget_content(self.current_pen_color, self.pen_width)

    # ==============================================================
    # Работа с элементами
    # ==============================================================
    def _item_for_manipulation(self, item):
        d = self._dimension_parent(item)
        return d if d else item

    def _dimension_parent(self, item):
        while item:
            if isinstance(item, DimensionItem):
                return item
            item = item.parentItem()
        return None

    def get_selected_text_item(self):
        for item in self.scene().selectedItems():
            if isinstance(item, TextItem):
                return item
        return None

    def get_selected_dimension_item(self):
        for item in self.scene().selectedItems():
            if isinstance(item, DimensionItem):
                return item
        return None

    def get_current_width(self):
        sd = self.get_selected_dimension_item()
        if sd:
            return max(1, int(round(sd._pen.widthF())))
        st = self.get_selected_text_item()
        if st:
            return max(1, int(round(st.font().pointSize() / 4)))
        if self.active_text_item:
            return max(1, int(round(self.active_text_item.font().pointSize() / 4)))
        if self.current_tool == 'text':
            return self.text_size
        return self.pen_width

    def set_text_size(self, v):
        v = max(1, min(100, int(v)))
        self.text_size = v
        st = self.get_selected_text_item()
        if st:
            font = st.font()
            font.setPointSize(max(1, v * 4))
            st.setFont(font)
            st.update()
        if self.active_text_item and isinstance(self.active_text_item, TextItem):
            font = self.active_text_item.font()
            font.setPointSize(max(1, v * 4))
            self.active_text_item.setFont(font)
            self.active_text_item.update()

    def set_text_bg(self, bg):
        self.current_text_bg = bg

    def _remove_empty_text(self, item):
        if item.scene():
            item.scene().removeItem(item)
        if self.active_text_item is item:
            self.active_text_item = None
        self._update_floating_widgets_visibility()

    def _text_editing_finished(self, item):
        if self.active_text_item is item:
            self.active_text_item = None
        if isinstance(item, TextItem):
            item._editable = False
            item.setTextInteractionFlags(Qt.NoTextInteraction)
        self._update_floating_widgets_visibility()

    # ==============================================================
    # Курсор
    # ==============================================================
    def _update_cursor(self, pos):
        sp = self.mapToScene(pos)

        # 1. Маркеры вставленных изображений
        for item in self.pasted_images:
            if item.isSelected() and item.handles:
                handle_id = item.handles.hit_test(pos)
                if handle_id:
                    self.viewport().setCursor(
                        item.handles.get_cursor_for_handle(handle_id))
                    return

        # 2. Маркеры активной зоны размытия (ПЕРЕД itemAt!)
        if (self.image_editor.active_blur_index is not None and
                self.image_editor.active_blur_index < len(
                    self.image_editor.blur_region_items)):
            active_blur = self.image_editor.blur_region_items[
                self.image_editor.active_blur_index]
            if active_blur.handles:
                handle_id = active_blur.handles.hit_test(pos)
                if handle_id:
                    self.viewport().setCursor(
                        active_blur.handles.get_cursor_for_handle(handle_id))
                    return

        # 3. Элемент под курсором
        item = self.scene().itemAt(sp, self.transform())

        if (self.active_text_item and item is self.active_text_item
                and self.active_text_item._editable):
            self.viewport().setCursor(Qt.IBeamCursor)
            return

        # Зоны размытия — курсор перемещения
        if item and isinstance(item, BlurRegionItem):
            self.viewport().setCursor(Qt.SizeAllCursor)
            return

        # Обычные перемещаемые объекты
        if item and not self._is_background_item(item):
            li = self._item_for_manipulation(item)
            if li is not None and li.flags() & QGraphicsItem.ItemIsMovable:
                self.viewport().setCursor(Qt.SizeAllCursor)
                return

        # Вставленные изображения
        if item and isinstance(item, PastedImageItem):
            self.viewport().setCursor(Qt.SizeAllCursor)
            return

        # Инструменты рисования
        if self.current_tool in ('rect', 'ellipse', 'arrow', 'line', 'text'):
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            self.viewport().setCursor(Qt.ArrowCursor)

    def _refresh_cursor(self):
        lp = self.viewport().mapFromGlobal(QCursor.pos())
        if self.viewport().rect().contains(lp):
            self._update_cursor(lp)
        else:
            self.viewport().setCursor(Qt.ArrowCursor)

    # ==============================================================
    # Resize / Show
    # ==============================================================
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.layout_manager.update_all()
        if self.auto_fit:
            bg = self.image_editor.background_item
            if bg is not None and not sip.isdeleted(bg) and bg.scene() is self.scene():
                self.fitInView(bg, Qt.KeepAspectRatio)

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self.layout_manager.update_all)