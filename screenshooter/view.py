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
                             QInputDialog, QLabel, QApplication)

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
from .controllers import (ClipboardController, ManipulationController,
                          KeyboardManager, FloatingWidgetManager,
                          PastedImageController, BlurController)


class EditorView(QGraphicsView):
    TEXT_FORMAT_TOP_OFFSET = 10
    TEXT_FORMAT_RIGHT_OFFSET = 8
    zoomChangedByWheel = pyqtSignal(int)
    crop_mode_changed = pyqtSignal(bool)
    blur_mode_changed = pyqtSignal(bool)

    def __init__(self, scene):
        super().__init__(scene)
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
        self.active_text_item = None
        self.current_text_bg = None
        self._first_click_after_activation = True
        self.shape_mode = 'rect'
        self.ellipse_mode = 'ellipse'
        self.arrow_mode = 'straight'
        self.line_mode = 'straight'
        self.setCursor(Qt.CrossCursor)

        self.history = HistoryManager()
        self.image_editor = ImageEditController(self)

        self.zoom_widget = ZoomWidget(self)

        self.text_format_widget = TextFormatWidget(self)
        self.text_format_widget.setVisible(False)

        self.shape_mode_widget = ShapeModeWidget(self)
        self.shape_mode_widget.setVisible(False)

        self.ellipse_mode_widget = ShapeModeWidgetEllipse(self)
        self.ellipse_mode_widget.setVisible(False)

        self.arrow_mode_widget = ShapeModeWidgetArrow(self)
        self.arrow_mode_widget.setVisible(False)

        self.line_mode_widget = LineModeWidget(self)
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

        self.layout_manager = LayoutManager(self)
        self._tool = None

        # Контроллеры
        self.pasted_image_controller = PastedImageController(self)
        self.blur_controller = BlurController(self)
        self.clipboard_controller = ClipboardController(self)
        self.manipulation_controller = ManipulationController(self)
        self.keyboard_manager = KeyboardManager(self)
        self.widget_manager = FloatingWidgetManager(self)

        self.widget_manager.update_info_widget_content(
            self.current_pen_color, self.pen_width)

        for w in (self.zoom_widget, self.text_format_widget,
                  self.shape_mode_widget, self.ellipse_mode_widget,
                  self.arrow_mode_widget, self.line_mode_widget,
                  self.info_widget, self.status_label):
            w.setCursor(Qt.ArrowCursor)

        # ЭТАП 3: батчинг selectionChanged через таймер
        self.scene().selectionChanged.connect(self._schedule_selection_update)

        self._selection_update_timer = QTimer(self)
        self._selection_update_timer.setSingleShot(True)
        self._selection_update_timer.setInterval(0)
        self._selection_update_timer.timeout.connect(self._do_selection_update)

        # Обработка смены режима обрезки (стиль статусной строки)
        self.crop_mode_changed.connect(self._on_crop_mode_changed)

    # ==============================================================
    # ЭТАП 3: батчинг изменений выделения
    # ==============================================================
    def _schedule_selection_update(self):
        if not self._selection_update_timer.isActive():
            self._selection_update_timer.start()

    def _do_selection_update(self):
        try:
            self.widget_manager.sync_selection_properties()
            self.widget_manager.update_floating_widgets_visibility()
            self.widget_manager.update_resolution_for_selection()
            self._update_blur_region_handles()
        except RuntimeError:
            pass

    # ==============================================================
    # Стиль статусной строки для режима обрезки
    # ==============================================================
    def _on_crop_mode_changed(self, active):
        """Обработчик смены режима обрезки."""
        if active:
            self._enable_crop_status_style()
        else:
            self._disable_crop_status_style()

    def _enable_crop_status_style(self):
        """Включает стиль статусной строки для режима обрезки.

        Добавляет полупрозрачный чёрный фон и увеличивает шрифт,
        чтобы текст был читаем на затемнённом экране.
        """
        if hasattr(self, 'status_label') and self.status_label is not None:
            self.status_label.setStyleSheet(
                "QLabel {"
                "  background-color: rgba(0, 0, 0, 180);"
                "  color: white;"
                "  font-size: 14px;"
                "  font-weight: bold;"
                "  padding: 4px 8px;"
                "  border-radius: 4px;"
                "}"
            )
            self.status_label.setVisible(True)

    def _disable_crop_status_style(self):
        """Выключает стиль статусной строки для режима обрезки.

        Возвращает обычный стиль и скрывает label.
        """
        if hasattr(self, 'status_label') and self.status_label is not None:
            self.status_label.setStyleSheet(
                "background-color: rgba(255,255,255,180); color: #333; "
                "border-radius: 6px; padding: 4px 8px;"
            )
            self.status_label.setVisible(False)

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
        self._invalidate_cursor_cache()

    def redo(self):
        old = self._get_background_pixmap_size()
        self.history.redo()
        new = self._get_background_pixmap_size()
        if old != new:
            self.fit_background_to_view()
        self._update_after_history_change()
        self._invalidate_cursor_cache()

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
        self.widget_manager.update_floating_widgets_visibility()
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
        return self.blur_controller.blur_mode

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
        self.blur_controller.start_blur_mode()

    def cancel_blur_mode(self):
        self.blur_controller.cancel_blur_mode()

    def rotate_image(self, angle):
        self.image_editor.rotate_image(angle)

    # ==============================================================
    # Вставленные изображения — делегирование в PastedImageController
    # ==============================================================
    @property
    def pasted_images(self):
        return self.pasted_image_controller.pasted_images

    def add_pasted_image(self, pixmap):
        return self.pasted_image_controller.add_image(pixmap)

    def remove_pasted_image(self, item):
        self.pasted_image_controller.remove_image(item)

    def clear_pasted_images(self):
        self.pasted_image_controller.clear_all()

    def _update_pasted_image_handles(self):
        self.pasted_image_controller.update_handles()

    def hide_pasted_image_handles_for_render(self):
        self.pasted_image_controller.hide_handles_for_render()

    def show_pasted_image_handles_after_render(self):
        self.pasted_image_controller.show_handles_after_render()

    # ==============================================================
    # Ручки зон размытия при множественном выделении
    # ==============================================================
    def _update_blur_region_handles(self):
        try:
            if self.blur_controller.blur_outside_mode:
                return
            if self.blur_controller.blur_interaction is not None:
                return

            selected = self.scene().selectedItems()
            non_bg_selected = [it for it in selected if not self._is_background_item(it)]

            if len(non_bg_selected) > 1:
                self.blur_controller._clear_active_blur()
            elif len(non_bg_selected) == 1:
                item = non_bg_selected[0]
                if isinstance(item, BlurRegionItem) and not sip.isdeleted(item):
                    try:
                        idx = self.blur_controller.blur_region_items.index(item)
                        self.blur_controller._set_active_blur(idx)
                    except ValueError:
                        pass
                else:
                    self.blur_controller._clear_active_blur()
            else:
                self.blur_controller._clear_active_blur()
        except RuntimeError:
            pass

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
    # Статусный виджет — делегирование в FloatingWidgetManager
    # ==============================================================
    def set_resolution_text(self, text):
        self.widget_manager.set_resolution_text(text)

    def show_status_message(self, message, duration=15000):
        self.widget_manager.show_status_message(message, duration)

    # ==============================================================
    # Мышь — делегирование в контроллеры
    # ==============================================================
    def mousePressEvent(self, e):
        # 1. Режим Размыть
        if self.blur_controller.blur_mode:
            sp = self.mapToScene(e.pos())
            item = self.scene().itemAt(sp, self.transform())
            li = self._item_for_manipulation(item) if item else None

            is_blur_handle = False
            if (self.blur_controller.active_blur_index is not None and
                    self.blur_controller.active_blur_index < len(
                        self.blur_controller.blur_region_items)):
                active_blur = self.blur_controller.blur_region_items[
                    self.blur_controller.active_blur_index]
                if active_blur.handles:
                    hid = active_blur.handles.hit_test(QPointF(e.pos()))
                    if hid:
                        is_blur_handle = True

            delegate_to_manipulation = False

            if is_blur_handle:
                pass
            elif li is not None and not self._is_background_item(li):
                if isinstance(li, BlurRegionItem):
                    modifiers = e.modifiers()
                    is_ctrl = bool(modifiers & Qt.ControlModifier)
                    is_shift = bool(modifiers & Qt.ShiftModifier)

                    if is_ctrl or is_shift:
                        delegate_to_manipulation = True
                    else:
                        selected = self.scene().selectedItems()
                        non_bg_selected = [it for it in selected
                                           if not self._is_background_item(it)]
                        if len(non_bg_selected) > 1 and li.isSelected():
                            delegate_to_manipulation = True
                else:
                    delegate_to_manipulation = True

            if delegate_to_manipulation:
                if self.manipulation_controller.handle_mouse_press(e):
                    e.accept()
                    return

            if self.blur_controller.handle_mouse_press(e):
                e.accept()
                return

        # 2. Режим Обрезки
        elif self.image_editor.crop_mode:
            if self.image_editor.handle_mouse_press(e):
                e.accept()
                return

        # 3. Манипуляции
        if self.manipulation_controller.handle_mouse_press(e):
            e.accept()
            return

        # 4. Текст
        if self.current_tool == 'text':
            sp = self.mapToScene(e.pos())
            item = self.scene().itemAt(sp, self.transform())
            li = self._item_for_manipulation(item) if item else None

            if isinstance(item, TextItem) and item._editable:
                super().mousePressEvent(e)
                e.accept()
                return

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

        # 5. Рисование инструментами
        if self.current_tool in ('rect', 'ellipse', 'arrow', 'line'):
            if self._tool is not None:
                sp = self.mapToScene(e.pos())
                self.start_point = sp
                self.temp_item = self._tool.start_draw(sp)
                if self.temp_item:
                    self.scene().addItem(self.temp_item)
            e.accept()
            return

        super().mousePressEvent(e)
        e.accept()

    def mouseMoveEvent(self, e):
        if not self.manipulation_controller._drag_items:
            if self.blur_controller.blur_mode:
                if self.blur_controller.handle_mouse_move(e):
                    e.accept()
                    return
            elif self.image_editor.crop_mode:
                if self.image_editor.handle_mouse_move(e):
                    e.accept()
                    return

        if not self.manipulation_controller._drag_items:
            if not self.image_editor.crop_mode and not self.blur_controller.blur_mode:
                if self.blur_controller.handle_blur_region_move_outside(e):
                    e.accept()
                    return

        if self.manipulation_controller.handle_mouse_move(e):
            e.accept()
            return

        self._update_cursor(e.pos())

        if self.temp_item and self._tool is not None and self.current_tool not in ('text',):
            sp = self.mapToScene(e.pos())
            self._tool.update_draw(self.temp_item, sp, e.modifiers())
            e.accept()
            return

        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if not self.manipulation_controller._drag_items:
            if self.blur_controller.blur_mode:
                if self.blur_controller.handle_mouse_release(e):
                    e.accept()
                    return
            elif self.image_editor.crop_mode:
                if self.image_editor.handle_mouse_release(e):
                    e.accept()
                    return

        if not self.manipulation_controller._drag_items:
            if (e.button() == Qt.LeftButton and
                    not self.image_editor.crop_mode and
                    not self.blur_controller.blur_mode):
                if self.blur_controller.handle_blur_region_release_outside(e):
                    e.accept()
                    return

        if self.manipulation_controller.handle_mouse_release(e):
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
    # Клавиатура — делегирование в KeyboardManager
    # ==============================================================
    def keyPressEvent(self, e):
        if self.keyboard_manager.handle_key_press(e):
            e.accept()
            return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if self.keyboard_manager.handle_key_release(e):
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
        if self.blur_controller.active_blur_index is not None:
            self.blur_controller.delete_active_blur_region()
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
        for idx, blur_item in enumerate(self.blur_controller.blur_region_items):
            if blur_item.scene() is self.scene() and blur_item.isSelected():
                blur_indices.append(idx)

        if pasted_items or other_items or blur_indices:
            command = RemoveSelectedItemsCommand(
                self.scene(), other_items, pasted_items, blur_indices, self)
            self.history.push(command)

        self.scene().clearSelection()
        self.manipulation_controller._restore_tool_if_needed()

    # ==============================================================
    # Обёртки для совместимости с app.py и text_item.py
    # ==============================================================
    def _update_floating_widgets_visibility(self):
        self.widget_manager.update_floating_widgets_visibility()

    def _invalidate_cursor_cache(self):
        self.manipulation_controller.invalidate_cursor_cache()

    def _update_cursor(self, pos):
        self.manipulation_controller.update_cursor(pos)

    def apply_current_style_to_selected(self, pen_color=None, pen_width=None):
        self.widget_manager.apply_current_style_to_selected(pen_color, pen_width)

    def set_pen_color(self, c):
        self.widget_manager.set_pen_color(c)

    def set_pen_width(self, w):
        self.widget_manager.set_pen_width(w)

    def set_text_size(self, v):
        self.widget_manager.set_text_size(v)

    def set_text_bg(self, bg):
        self.widget_manager.set_text_bg(bg)

    def get_current_width(self):
        return self.widget_manager.get_current_width()

    def update_text_format_widget_visibility(self):
        self.widget_manager.update_text_format_widget_visibility()

    def _remove_empty_text(self, item):
        self.widget_manager.remove_empty_text(item)

    def _text_editing_finished(self, item):
        self.widget_manager.text_editing_finished(item)

    # ==============================================================
    # Временный указатель / инструменты
    # ==============================================================
    def _apply_tool(self, t):
        self.current_tool = t
        self.setDragMode(QGraphicsView.NoDrag if t else QGraphicsView.RubberBandDrag)

    def set_tool(self, t):
        self._deactivate_active_text()

        if self.image_editor.crop_mode:
            self.image_editor.cancel_crop_mode()
        if self.blur_controller.blur_mode:
            self.blur_controller.cancel_blur_mode()

        self.scene().clearSelection()

        mc = self.manipulation_controller
        mc.right_click_temp_pointer = False
        mc.previous_tool_for_right_click = None
        mc.modifier_temp_pointer = False
        mc.previous_tool_for_modifier = None

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
            self.widget_manager.update_info_widget_content(
                self.current_pen_color, self.get_current_width())

        self._invalidate_cursor_cache()
        QTimer.singleShot(0, self.manipulation_controller._refresh_cursor)
        self.widget_manager.update_floating_widgets_visibility()

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