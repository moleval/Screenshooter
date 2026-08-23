"""Основной виджет редактора (холст)."""

import math
from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF, QPoint, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QPolygonF, QFont, QImage, QIcon, QPainterPath, QCursor, QBrush, QPixmap
from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsEllipseItem,
                             QGraphicsPixmapItem, QGraphicsTextItem, QGraphicsItem,
                             QStyle, QInputDialog, QLabel)

from .constants import MIN_RECT_SIZE, MIN_ARROW_LENGTH
from .items import (TextItem, DimensionTextItem, RectangleItem, EllipseItem, FilledRectItem,
                    LineItem, WavyLineItem, ArrowItem, CurvedArrowItem, DimensionItem, CloudItem)
from .widgets.zoom_widget import ZoomWidget
from .widgets.text_format_widget import TextFormatWidget
from .widgets.info_widget import InfoWidget
from .widgets.mode_widgets import (ShapeModeWidget, ShapeModeWidgetEllipse,
                                   ShapeModeWidgetArrow, LineModeWidget)
from .history import (HistoryManager, AddItemCommand, RemoveItemCommand,
                      MoveItemCommand, ChangePenCommand)
from .image_edit_controller import ImageEditController


class EditorView(QGraphicsView):
    TEXT_FORMAT_TOP_OFFSET = 10
    TEXT_FORMAT_RIGHT_OFFSET = 8
    zoomChangedByWheel = pyqtSignal(int)
    crop_mode_changed = pyqtSignal(bool)
    blur_mode_changed = pyqtSignal(bool)

    def __init__(self, scene):
        super().__init__(scene)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
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
        self._drag_item = None
        self._drag_offset = QPointF()
        self._drag_old_pos = None
        self.shape_mode = 'rect'
        self.ellipse_mode = 'ellipse'
        self.arrow_mode = 'straight'
        self.line_mode = 'straight'
        self.setCursor(Qt.CrossCursor)
        self._pan_active = False
        self._pan_start_pos = QPoint()
        self._pan_start_scroll = QPoint()

        self.history = HistoryManager()
        self.image_editor = ImageEditController(self)

        self.zoom_widget = ZoomWidget(self)
        self.zoom_widget.zoomChanged.connect(self._on_zoom_widget_changed)
        self.zoom_widget.fitRequested.connect(self._fit_to_view)
        self._update_zoom_widget_position()

        self.text_format_widget = TextFormatWidget(self)
        self.text_format_widget.bgChanged.connect(self._on_text_bg_changed)
        self.text_format_widget.setVisible(False)
        self._update_text_format_widget_position()

        self.shape_mode_widget = ShapeModeWidget(self)
        self.shape_mode_widget.modeChanged.connect(self._on_shape_mode_changed)
        self.shape_mode_widget.setVisible(False)
        self._update_shape_mode_widget_position()

        self.ellipse_mode_widget = ShapeModeWidgetEllipse(self)
        self.ellipse_mode_widget.modeChanged.connect(self._on_ellipse_mode_changed)
        self.ellipse_mode_widget.setVisible(False)
        self._update_ellipse_mode_widget_position()

        self.arrow_mode_widget = ShapeModeWidgetArrow(self)
        self.arrow_mode_widget.modeChanged.connect(self._on_arrow_mode_changed)
        self.arrow_mode_widget.setVisible(False)
        self._update_arrow_mode_widget_position()

        self.line_mode_widget = LineModeWidget(self)
        self.line_mode_widget.modeChanged.connect(self._on_line_mode_changed)
        self.line_mode_widget.setVisible(False)
        self._update_line_mode_widget_position()

        self.info_widget = InfoWidget(self)
        self.info_widget.setVisible(True)
        self._update_info_widget_content(self.current_pen_color, self.pen_width)
        self._update_info_widget_position()

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
        self._update_status_label_position()

        for w in (self.zoom_widget, self.text_format_widget, self.shape_mode_widget,
                  self.ellipse_mode_widget, self.arrow_mode_widget, self.line_mode_widget,
                  self.info_widget, self.status_label):
            w.setCursor(Qt.ArrowCursor)

        self.scene().selectionChanged.connect(self._sync_selection_properties)
        self.scene().selectionChanged.connect(self._update_floating_widgets_visibility)

    # --------------------------------------------------------------
    # Undo/Redo
    # --------------------------------------------------------------
    def undo(self):
        old_pixmap_size = self._get_background_pixmap_size()
        self.history.undo()
        new_pixmap_size = self._get_background_pixmap_size()
        if old_pixmap_size != new_pixmap_size:
            self.fit_background_to_view()
        self._update_after_history_change()

    def redo(self):
        old_pixmap_size = self._get_background_pixmap_size()
        self.history.redo()
        new_pixmap_size = self._get_background_pixmap_size()
        if old_pixmap_size != new_pixmap_size:
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

    # --------------------------------------------------------------
    # Свойства и делегаты
    # --------------------------------------------------------------
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

    # --------------------------------------------------------------
    # Плавающий статусный виджет
    # --------------------------------------------------------------
    def set_resolution_text(self, text):
        self._resolution_text = text
        self.status_label.setText(text)
        self.status_label.setToolTip(text if text else "")
        self.status_label.setVisible(bool(text))
        self._update_status_label_position()

    def show_status_message(self, message, duration=15000):
        self.status_label.setText(message)
        self.status_label.setToolTip(message)
        self.status_label.setVisible(True)
        self._update_status_label_position()
        self._status_timer.start(duration)

    def _restore_status_label(self):
        if self._resolution_text:
            self.status_label.setText(self._resolution_text)
        else:
            self.status_label.setVisible(False)

    def _update_status_label_position(self):
        if not hasattr(self, 'status_label'):
            return
        vp = self.viewport()
        if not vp:
            return
        max_width = vp.width() - 8
        self.status_label.setMaximumWidth(max_width)
        self.status_label.adjustSize()
        sh = self.horizontalScrollBar().height() if self.horizontalScrollBar().isVisible() else 0
        x = 4
        y = vp.height() - self.status_label.sizeHint().height() - sh - 4
        self.status_label.move(x, y)
        self.status_label.raise_()

    # --------------------------------------------------------------
    # Обработчики мыши
    # --------------------------------------------------------------
    def mousePressEvent(self, e):
        # 1. Режимы обрезки/размытия
        if self.image_editor.handle_mouse_press(e):
            e.accept()
            return

        # 2. Приоритет зон размытия (если не активны crop/blur)
        if (e.button() == Qt.LeftButton and
            not self.image_editor.crop_mode and
            not self.image_editor.blur_mode):
            if self.image_editor.handle_blur_region_press_outside(e):
                e.accept()
                return

        # 3. Панорамирование
        if e.button() == Qt.MiddleButton:
            if self.active_text_item and self.active_text_item._editable:
                e.accept()
                return
            self._pan_active = True
            self._pan_start_pos = e.pos()
            self._pan_start_scroll = QPoint(self.horizontalScrollBar().value(), self.verticalScrollBar().value())
            self.viewport().setCursor(Qt.ClosedHandCursor)
            e.accept()
            return

        # 4. Правая кнопка мыши
        if e.button() == Qt.RightButton:
            if self.active_text_item and self.active_text_item._editable:
                e.accept()
                return
            sp = self.mapToScene(e.pos())
            item = None
            for it in self.scene().items(sp):
                if not isinstance(it, QGraphicsPixmapItem):
                    item = it
                    break
            if item:
                li = self._item_for_manipulation(item)
                self.scene().clearSelection()
                li.setSelected(True)
                self._activate_temp_pointer('right_click')
            else:
                self.scene().clearSelection()
                self._activate_temp_pointer('right_click')
                self.rubber_band_active = True
                self.rubber_band_start = sp
                pen = QPen(QColor(0, 120, 215), 1, Qt.DashLine)
                self.rubber_band_item = QGraphicsRectItem(QRectF(sp, sp))
                self.rubber_band_item.setPen(pen)
                self.rubber_band_item.setFlag(QGraphicsRectItem.ItemIsMovable, False)
                self.rubber_band_item.setFlag(QGraphicsRectItem.ItemIsSelectable, False)
                self.scene().addItem(self.rubber_band_item)
            e.accept()
            return

        # 5. Левая кнопка мыши — инструменты аннотаций и т.д.
        if e.button() == Qt.LeftButton:
            sp = self.mapToScene(e.pos())
            item = self.scene().itemAt(sp, self.transform())

            if isinstance(item, TextItem) and item._editable:
                super().mousePressEvent(e)
                e.accept()
                return

            li = self._item_for_manipulation(item) if item else None

            if self.current_tool is not None and li is not None and not isinstance(li, QGraphicsPixmapItem):
                if isinstance(item, DimensionTextItem) and item.textInteractionFlags() != Qt.NoTextInteraction:
                    super().mousePressEvent(e)
                    e.accept()
                    return
                elif isinstance(item, TextItem) and item._editable:
                    super().mousePressEvent(e)
                    e.accept()
                    return
                else:
                    self._drag_item = li
                    self._drag_old_pos = li.pos()
                    self._drag_offset = li.scenePos() - sp
                    self.scene().clearSelection()
                    li.setSelected(True)
                    e.accept()
                    return

            if self.current_tool == 'text':
                if isinstance(item, TextItem):
                    self.scene().clearSelection()
                    item.setSelected(True)
                    if self.active_text_item is not None and self.active_text_item is not item:
                        old = self.active_text_item
                        self.active_text_item = None
                        old.setEditable(False)
                    self._first_click_after_activation = False
                    e.accept()
                    return
                else:
                    if self.active_text_item:
                        old = self.active_text_item
                        self.active_text_item = None
                        old.setEditable(False)
                        e.accept()
                        return
                    else:
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
                            e.accept()
                            return
                        else:
                            self.scene().clearSelection()
                            e.accept()
                            return

            if (self.right_click_temp_pointer or self.modifier_temp_pointer) and self.current_tool is None:
                item = self.scene().itemAt(sp, self.transform())
                if isinstance(item, QGraphicsPixmapItem):
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

            if self.current_tool in ('rect', 'ellipse', 'arrow', 'line'):
                self.start_point = sp
                pen = QPen(self.current_pen_color, self.pen_width)
                if self.current_tool == 'rect':
                    if self.shape_mode == 'filled':
                        self.temp_item = FilledRectItem(QRectF(sp, sp), self.current_pen_color)
                    else:
                        self.temp_item = RectangleItem(QRectF(sp, sp), pen)
                elif self.current_tool == 'ellipse':
                    if self.ellipse_mode == 'cloud':
                        self.temp_item = CloudItem(QRectF(sp, sp), pen)
                    else:
                        self.temp_item = EllipseItem(QRectF(sp, sp), pen)
                elif self.current_tool == 'arrow':
                    if self.arrow_mode == 'straight':
                        self.temp_item = ArrowItem(sp, sp, pen)
                    elif self.arrow_mode == 'curved':
                        self.temp_item = CurvedArrowItem(sp, sp, (sp + sp) / 2, pen)
                    elif self.arrow_mode == 'dimension':
                        self.temp_item = DimensionItem(sp, sp, pen, self.current_pen_color)
                elif self.current_tool == 'line':
                    if self.line_mode == 'straight':
                        self.temp_item = LineItem(sp.x(), sp.y(), sp.x(), sp.y(), pen)
                    elif self.line_mode == 'dashed':
                        dpen = QPen(pen)
                        dpen.setStyle(Qt.DashLine)
                        self.temp_item = LineItem(sp.x(), sp.y(), sp.x(), sp.y(), dpen)
                    elif self.line_mode == 'wavy':
                        self.temp_item = WavyLineItem(sp.x(), sp.y(), sp.x(), sp.y(), pen)
                if self.temp_item:
                    self.scene().addItem(self.temp_item)
                e.accept()
                return

            super().mousePressEvent(e)
            e.accept()
            return

        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        # 1. Режимы обрезки/размытия
        if self.image_editor.handle_mouse_move(e):
            e.accept()
            return

        # 2. Приоритет зон размытия (если не активны crop/blur)
        if not self.image_editor.crop_mode and not self.image_editor.blur_mode:
            if self.image_editor.handle_blur_region_move_outside(e):
                e.accept()
                return

        # 3. Панорамирование
        if self._pan_active:
            dx = e.pos().x() - self._pan_start_pos.x()
            dy = e.pos().y() - self._pan_start_pos.y()
            scale = self.transform().m11()
            if scale != 0:
                self.horizontalScrollBar().setValue(int(self._pan_start_scroll.x() - dx / scale))
                self.verticalScrollBar().setValue(int(self._pan_start_scroll.y() - dy / scale))
            e.accept()
            return

        # 4. Перетаскивание аннотаций
        if self._drag_item:
            sp = self.mapToScene(e.pos())
            self._drag_item.setPos(sp + self._drag_offset)
            self.scene().update()
            e.accept()
            return

        # 5. Обновление курсора
        self._update_cursor(e.pos())

        # 6. Рисование временных аннотаций
        if self.temp_item:
            cp = self.mapToScene(e.pos())
            if e.modifiers() & Qt.ShiftModifier:
                dx = cp.x() - self.start_point.x()
                dy = cp.y() - self.start_point.y()
                if abs(dx) > abs(dy):
                    cp.setY(self.start_point.y())
                else:
                    cp.setX(self.start_point.x())

            if isinstance(self.temp_item, QGraphicsRectItem):
                dx = cp.x() - self.start_point.x()
                dy = cp.y() - self.start_point.y()
                if self.current_tool == 'rect' and self.shape_mode == 'square':
                    side = max(abs(dx), abs(dy))
                    x = self.start_point.x() if dx >= 0 else self.start_point.x() - side
                    y = self.start_point.y() if dy >= 0 else self.start_point.y() - side
                    rect = QRectF(x, y, side, side)
                else:
                    rect = QRectF(self.start_point, cp).normalized()
                self.temp_item.setRect(rect)
            elif isinstance(self.temp_item, QGraphicsEllipseItem):
                dx = cp.x() - self.start_point.x()
                dy = cp.y() - self.start_point.y()
                if self.current_tool == 'ellipse' and self.ellipse_mode == 'circle':
                    r = max(abs(dx), abs(dy))
                    x = self.start_point.x() if dx >= 0 else self.start_point.x() - r
                    y = self.start_point.y() if dy >= 0 else self.start_point.y() - r
                    rect = QRectF(x, y, r, r)
                else:
                    rect = QRectF(self.start_point, cp).normalized()
                self.temp_item.setRect(rect)
            elif isinstance(self.temp_item, CloudItem):
                self.temp_item.setRect(QRectF(self.start_point, cp).normalized())
            elif isinstance(self.temp_item, ArrowItem):
                self.temp_item.set_line(self.start_point, cp)
            elif isinstance(self.temp_item, CurvedArrowItem):
                start = self.start_point
                end = cp
                mid = (start + end) / 2
                dx = end.x() - start.x()
                dy = end.y() - start.y()
                if math.hypot(dx, dy) > 0:
                    perp_x = -dy
                    perp_y = dx
                    norm = math.hypot(perp_x, perp_y)
                    if norm > 0:
                        perp_x /= norm
                        perp_y /= norm
                        length = math.hypot(dx, dy)
                        bend = 0.3
                        ctrl = mid + QPointF(perp_x * length * bend, perp_y * length * bend)
                        cross = dx * (cp.y() - start.y()) - dy * (cp.x() - start.x())
                        if cross < 0:
                            ctrl = mid - QPointF(perp_x * length * bend, perp_y * length * bend)
                        self.temp_item.set_curve(start, end, ctrl)
            elif isinstance(self.temp_item, DimensionItem):
                self.temp_item.setRect(self.start_point, cp)
            elif isinstance(self.temp_item, LineItem):
                self.temp_item.setLine(self.start_point.x(), self.start_point.y(), cp.x(), cp.y())
            elif isinstance(self.temp_item, WavyLineItem):
                self.temp_item.set_points(self.start_point.x(), self.start_point.y(), cp.x(), cp.y())
            e.accept()
            return

        # 7. Растягивание рамки выделения (правая кнопка)
        if self.rubber_band_active and self.rubber_band_item:
            cp = self.mapToScene(e.pos())
            self.rubber_band_item.setRect(QRectF(self.rubber_band_start, cp).normalized())
            e.accept()
            return

        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        # 1. Режимы обрезки/размытия
        if self.image_editor.handle_mouse_release(e):
            e.accept()
            return

        # 2. Приоритет зон размытия (если не активны crop/blur)
        if (e.button() == Qt.LeftButton and
            not self.image_editor.crop_mode and
            not self.image_editor.blur_mode):
            if self.image_editor.handle_blur_region_release_outside(e):
                e.accept()
                return

        # 3. Панорамирование
        if e.button() == Qt.MiddleButton and self._pan_active:
            self._pan_active = False
            self._refresh_cursor()
            e.accept()
            return

        # 4. Перетаскивание аннотаций
        if self._drag_item:
            item = self._drag_item
            old_pos = self._drag_old_pos
            self._drag_item = None
            self._drag_old_pos = None
            self.history.push(MoveItemCommand(item, old_pos, item.pos()))
            e.accept()
            return

        # 5. Растягивание рамки выделения
        if self.rubber_band_active and e.button() == Qt.RightButton:
            if self.rubber_band_item:
                self.scene().removeItem(self.rubber_band_item)
                rect = self.rubber_band_item.rect()
                self.rubber_band_item = None
                for item in self.scene().items():
                    if isinstance(item, QGraphicsPixmapItem):
                        continue
                    if item.sceneBoundingRect().intersects(rect):
                        item.setSelected(True)
            self.rubber_band_active = False
            self.rubber_band_start = None
            e.accept()
            return

        # 6. Завершение рисования аннотации
        if self.temp_item and e.button() == Qt.LeftButton:
            should_remove = False
            if isinstance(self.temp_item, (RectangleItem, FilledRectItem, EllipseItem, CloudItem)):
                r = self.temp_item.rect()
                if r.width() < MIN_RECT_SIZE or r.height() < MIN_RECT_SIZE:
                    should_remove = True
            elif isinstance(self.temp_item, (LineItem, WavyLineItem)):
                if isinstance(self.temp_item, LineItem):
                    line = self.temp_item.line()
                    length = math.hypot(line.x2() - line.x1(), line.y2() - line.y1())
                else:
                    length = math.hypot(self.temp_item._x2 - self.temp_item._x1, self.temp_item._y2 - self.temp_item._y1)
                if length < MIN_ARROW_LENGTH:
                    should_remove = True
            elif isinstance(self.temp_item, (ArrowItem, CurvedArrowItem, DimensionItem)):
                start = self.temp_item._start
                end = self.temp_item._end
                length = math.hypot(end.x() - start.x(), end.y() - start.y())
                if length < MIN_ARROW_LENGTH:
                    should_remove = True

            if should_remove:
                self.scene().removeItem(self.temp_item)
                self.temp_item = None
                self.start_point = None
                e.accept()
                return

            if isinstance(self.temp_item, CurvedArrowItem) and self.temp_item.isEmpty():
                self.scene().removeItem(self.temp_item)
                self.temp_item = None
                self.start_point = None
                e.accept()
                return

            self.scene().clearSelection()
            self.temp_item.setSelected(True)

            if isinstance(self.temp_item, DimensionItem):
                start = self.start_point
                end = self.temp_item._end
                dx = end.x() - start.x()
                dy = end.y() - start.y()
                length = math.hypot(dx, dy)
                if length > 0:
                    mid = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
                    angle_deg = math.degrees(math.atan2(dy, dx))
                    if angle_deg > 90 or angle_deg < -90:
                        angle_deg += 180
                    angle_deg = (angle_deg + 180) % 360 - 180
                    rad = math.radians(angle_deg)
                    normal = QPointF(math.sin(rad), -math.cos(rad))

                    ti = TextItem(self, bg_color=self.current_text_bg)
                    ti.setDefaultTextColor(self.current_pen_color)
                    font = QFont()
                    font.setPointSize(self.text_size * 4)
                    ti.setFont(font)
                    self.scene().addItem(ti)

                    def update_text_pos():
                        rect = ti.boundingRect()
                        gap = 8
                        center = mid + normal * (gap + rect.height() / 2)
                        ti.setPos(center - rect.center())
                        ti.setTransformOriginPoint(rect.center())
                        ti.setRotation(angle_deg)

                    ti.document().contentsChanged.connect(update_text_pos)
                    update_text_pos()
                    ti.setSelected(True)
                    ti.setEditable(True)
                    self.active_text_item = ti
                    self._update_floating_widgets_visibility()

            self.history.push(AddItemCommand(self.scene(), self.temp_item))
            self.temp_item = None
            self.start_point = None
            e.accept()
            return

        super().mouseReleaseEvent(e)

    # --------------------------------------------------------------
    # Остальные методы (управление инструментами, клавиши)
    # --------------------------------------------------------------
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

    def get_selected_text_item(self):
        for item in self.scene().selectedItems():
            if isinstance(item, TextItem):
                return item
        return None

    def _dimension_parent(self, item):
        while item:
            if isinstance(item, DimensionItem):
                return item
            item = item.parentItem()
        return None

    def _item_for_manipulation(self, item):
        d = self._dimension_parent(item)
        return d if d else item

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

    def _apply_tool(self, t):
        self.current_tool = t
        self.setDragMode(QGraphicsView.NoDrag if t else QGraphicsView.RubberBandDrag)

    def set_tool(self, t):
        if self.active_text_item:
            self.active_text_item.setEditable(False)
            self.active_text_item = None

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

        # Зоны размытия всегда видимы и редактируемы, поэтому здесь ничего не меняем

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
            self._update_info_widget_content(self.current_pen_color, self.get_current_width())

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

    def delete_selected(self):
        if self.image_editor.blur_mode and self.image_editor.active_blur_index is not None:
            self.image_editor.delete_active_blur_region()
            return
        for item in self.scene().selectedItems():
            if isinstance(item, QGraphicsPixmapItem):
                continue
            self.history.push(RemoveItemCommand(self.scene(), item))
            if item is self.active_text_item:
                self.active_text_item = None
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
                    item.setBrush(QColor(pen_color.red(), pen_color.green(), pen_color.blue(), 80))
                continue
            if isinstance(item, (RectangleItem, EllipseItem, ArrowItem, CurvedArrowItem,
                                 CloudItem, LineItem, WavyLineItem)):
                current_pen = item.pen()
                new_color = pen_color if pen_color else current_pen.color()
                new_width = pen_width if pen_width else current_pen.widthF()
                new_pen = QPen(new_color, new_width)
                if isinstance(item, (RectangleItem, EllipseItem, CloudItem, LineItem, WavyLineItem)):
                    new_pen.setCapStyle(Qt.RoundCap)
                    new_pen.setJoinStyle(Qt.RoundJoin)
                    if isinstance(item, LineItem) and self.line_mode == 'dashed':
                        new_pen.setStyle(Qt.DashLine)
                elif isinstance(item, CurvedArrowItem):
                    new_pen.setCapStyle(Qt.RoundCap)
                    new_pen.setJoinStyle(Qt.RoundJoin)
                self.history.push(ChangePenCommand(item, current_pen, new_pen))

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
            if self.active_text_item:
                self.active_text_item.setEditable(False)
                self.active_text_item = None
            self._restore_tool_if_needed()
            e.accept()
            return
        if e.key() == Qt.Key_Control:
            self.ctrl_pressed = True
            if self.current_tool:
                self._activate_temp_pointer('modifier')
            e.accept()
            return
        super().keyPressEvent(e)

    def select_all_items(self):
        self.scene().clearSelection()
        for item in self.scene().items():
            if item.parentItem() is None and not isinstance(item, QGraphicsPixmapItem):
                item.setSelected(True)

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

    def mouseDoubleClickEvent(self, e):
        sp = self.mapToScene(e.pos())
        item = self.scene().itemAt(sp, self.transform())
        if isinstance(item, TextItem):
            if self.active_text_item is not None and self.active_text_item is not item:
                self.active_text_item.setEditable(False)
            self.active_text_item = item
            item.setEditable(True)
            if self.current_tool == 'text':
                self._first_click_after_activation = False
            e.accept()
            return
        if self.current_tool == 'text' and (item is None or isinstance(item, QGraphicsPixmapItem)):
            if self.active_text_item:
                self.active_text_item.setEditable(False)
                self.active_text_item = None
            else:
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
            e.accept()
            return
        super().mouseDoubleClickEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_zoom_widget_position()
        self._update_text_format_widget_position()
        self._update_shape_mode_widget_position()
        self._update_ellipse_mode_widget_position()
        self._update_arrow_mode_widget_position()
        self._update_line_mode_widget_position()
        self._update_info_widget_position()
        self._update_status_label_position()
        if self.auto_fit and self.scene() and self.scene().items():
            bg = self.scene().items()[0]
            if isinstance(bg, QGraphicsPixmapItem):
                self.fitInView(bg, Qt.KeepAspectRatio)

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._update_zoom_widget_position)
        QTimer.singleShot(0, self._update_text_format_widget_position)
        QTimer.singleShot(0, self._update_shape_mode_widget_position)
        QTimer.singleShot(0, self._update_ellipse_mode_widget_position)
        QTimer.singleShot(0, self._update_arrow_mode_widget_position)
        QTimer.singleShot(0, self._update_line_mode_widget_position)
        QTimer.singleShot(0, self._update_info_widget_position)
        QTimer.singleShot(0, self._update_status_label_position)

    # --------------------------------------------------------------
    # Вспомогательные методы
    # --------------------------------------------------------------
    def _update_info_widget_content(self, color, thickness):
        self.info_widget.set_info(color, thickness)
        QTimer.singleShot(0, self._update_info_widget_position)

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
        elif isinstance(item, (RectangleItem, EllipseItem, ArrowItem, CurvedArrowItem, CloudItem, LineItem, WavyLineItem)):
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
            return

        if self.active_text_item is not None:
            self.text_format_widget.setVisible(True)
            self._update_text_format_widget_position()
            return

        if self.current_tool == 'text':
            self.text_format_widget.setVisible(True)
            self._update_text_format_widget_position()
            return

        selected = self.scene().selectedItems()
        if selected:
            all_text = all(isinstance(item, TextItem) for item in selected)
            if all_text:
                self.text_format_widget.setVisible(True)
                self._update_text_format_widget_position()
                return
            return

        if self.current_tool == 'rect':
            self.shape_mode_widget.setVisible(True)
        elif self.current_tool == 'ellipse':
            self.ellipse_mode_widget.setVisible(True)
        elif self.current_tool == 'arrow':
            self.arrow_mode_widget.setVisible(True)
        elif self.current_tool == 'line':
            self.line_mode_widget.setVisible(True)

    def _update_info_widget_position(self):
        if not self.info_widget:
            return
        vp = self.viewport()
        if not vp:
            return
        vw, vh = vp.width(), vp.height()
        sw = self.verticalScrollBar().width() if self.verticalScrollBar().isVisible() else 0
        sh = self.horizontalScrollBar().height() if self.horizontalScrollBar().isVisible() else 0
        iw = self.info_widget
        zw = self.zoom_widget

        percent_edit = zw.percent_edit
        zoom_right = zw.x() + percent_edit.x() + percent_edit.width()
        zy = zw.y()

        x = zoom_right - iw.width()
        y = zy - iw.height() - 4
        x = max(0, x)
        y = max(0, y)
        iw.move(x, y)
        iw.raise_()

    def _update_zoom_widget_position(self):
        if not self.zoom_widget:
            return
        vp = self.viewport()
        if not vp:
            return
        vw, vh = vp.width(), vp.height()
        sw = self.verticalScrollBar().width() if self.verticalScrollBar().isVisible() else 0
        sh = self.horizontalScrollBar().height() if self.horizontalScrollBar().isVisible() else 0
        zw = self.zoom_widget
        x = vw - zw.width() - sw - 4
        y = vh - zw.height() - sh - 4
        x = max(0, x)
        y = max(0, y)
        zw.move(x, y)
        zw.raise_()

    def _update_text_format_widget_position(self):
        if not self.text_format_widget:
            return
        vp = self.viewport()
        if not vp:
            return
        vw, vh = vp.width(), vp.height()
        sw = self.verticalScrollBar().width() if self.verticalScrollBar().isVisible() else 0
        sh = self.horizontalScrollBar().height() if self.horizontalScrollBar().isVisible() else 0
        tfw = self.text_format_widget
        x = vw - tfw.width() - sw - self.TEXT_FORMAT_RIGHT_OFFSET
        y = self.TEXT_FORMAT_TOP_OFFSET
        x = max(0, x)
        y = max(0, y)
        tfw.move(x, y)
        tfw.raise_()

    def _update_shape_mode_widget_position(self):
        if not self.shape_mode_widget:
            return
        vp = self.viewport()
        if not vp:
            return
        vw, vh = vp.width(), vp.height()
        sw = self.verticalScrollBar().width() if self.verticalScrollBar().isVisible() else 0
        sh = self.horizontalScrollBar().height() if self.horizontalScrollBar().isVisible() else 0
        smw = self.shape_mode_widget
        x = vw - smw.width() - sw - self.TEXT_FORMAT_RIGHT_OFFSET
        y = self.TEXT_FORMAT_TOP_OFFSET
        x = max(0, x)
        y = max(0, y)
        smw.move(x, y)
        smw.raise_()

    def _update_ellipse_mode_widget_position(self):
        if not self.ellipse_mode_widget:
            return
        vp = self.viewport()
        if not vp:
            return
        vw, vh = vp.width(), vp.height()
        sw = self.verticalScrollBar().width() if self.verticalScrollBar().isVisible() else 0
        sh = self.horizontalScrollBar().height() if self.horizontalScrollBar().isVisible() else 0
        emw = self.ellipse_mode_widget
        x = vw - emw.width() - sw - self.TEXT_FORMAT_RIGHT_OFFSET
        y = self.TEXT_FORMAT_TOP_OFFSET
        x = max(0, x)
        y = max(0, y)
        emw.move(x, y)
        emw.raise_()

    def _update_arrow_mode_widget_position(self):
        if not self.arrow_mode_widget:
            return
        vp = self.viewport()
        if not vp:
            return
        vw, vh = vp.width(), vp.height()
        sw = self.verticalScrollBar().width() if self.verticalScrollBar().isVisible() else 0
        sh = self.horizontalScrollBar().height() if self.horizontalScrollBar().isVisible() else 0
        amw = self.arrow_mode_widget
        x = vw - amw.width() - sw - self.TEXT_FORMAT_RIGHT_OFFSET
        y = self.TEXT_FORMAT_TOP_OFFSET
        x = max(0, x)
        y = max(0, y)
        amw.move(x, y)
        amw.raise_()

    def _update_line_mode_widget_position(self):
        if not self.line_mode_widget:
            return
        vp = self.viewport()
        if not vp:
            return
        vw, vh = vp.width(), vp.height()
        sw = self.verticalScrollBar().width() if self.verticalScrollBar().isVisible() else 0
        sh = self.horizontalScrollBar().height() if self.horizontalScrollBar().isVisible() else 0
        lmw = self.line_mode_widget
        x = vw - lmw.width() - sw - self.TEXT_FORMAT_RIGHT_OFFSET
        y = self.TEXT_FORMAT_TOP_OFFSET
        x = max(0, x)
        y = max(0, y)
        lmw.move(x, y)
        lmw.raise_()

    def _on_zoom_widget_changed(self, p):
        self.zoomChangedByWheel.emit(p)

    def _fit_to_view(self):
        if self.scene() and self.scene().items():
            bg = None
            for item in self.scene().items():
                if isinstance(item, QGraphicsPixmapItem):
                    bg = item
                    break
            if bg:
                self.fitInView(bg, Qt.KeepAspectRatio)
            else:
                self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)
        else:
            self.resetTransform()
        self.auto_fit = False
        scale = self.transform().m11() * 100
        self.zoom_widget.set_zoom(scale)

    def _on_text_bg_changed(self, m):
        self.current_text_bg = (
            QColor(255, 255, 255, 200) if m == 'white' else
            QColor(0, 0, 0, 200) if m == 'black' else
            None
        )
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

    def _update_cursor(self, pos):
        sp = self.mapToScene(pos)
        item = self.scene().itemAt(sp, self.transform())
        if self.active_text_item and item is self.active_text_item and self.active_text_item._editable:
            self.viewport().setCursor(Qt.IBeamCursor)
            return
        if item and not isinstance(item, QGraphicsPixmapItem):
            li = self._item_for_manipulation(item)
            if li.flags() & QGraphicsItem.ItemIsMovable:
                self.viewport().setCursor(Qt.SizeAllCursor)
                return
        if self.current_tool in ('rect', 'ellipse', 'arrow', 'line', 'text'):
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            self.viewport().setCursor(Qt.CrossCursor)

    def _refresh_cursor(self):
        lp = self.viewport().mapFromGlobal(QCursor.pos())
        if self.viewport().rect().contains(lp):
            self._update_cursor(lp)
        else:
            self.viewport().setCursor(Qt.ArrowCursor)