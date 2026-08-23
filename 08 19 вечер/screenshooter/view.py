"""Основной виджет редактора (холст)."""

import math
from PyQt5.QtCore import Qt, QRectF, QPointF, QPoint, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QPolygonF, QFont, QImage, QIcon, QPainterPath, QCursor
from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsPixmapItem,
                             QStyle, QInputDialog)

from .constants import MIN_RECT_SIZE, MIN_ARROW_LENGTH
from .items import (TextItem, DimensionTextItem, RectangleItem, EllipseItem, FilledRectItem,
                    LineItem, WavyLineItem, ArrowItem, CurvedArrowItem, DimensionItem, CloudItem)
from .widgets.zoom_widget import ZoomWidget
from .widgets.text_format_widget import TextFormatWidget
from .widgets.info_widget import InfoWidget
from .widgets.mode_widgets import (ShapeModeWidget, ShapeModeWidgetEllipse,
                                   ShapeModeWidgetArrow, LineModeWidget)


class EditorView(QGraphicsView):
    TEXT_FORMAT_TOP_OFFSET = 10
    TEXT_FORMAT_RIGHT_OFFSET = 8
    zoomChangedByWheel = pyqtSignal(int)

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
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor(235, 242, 250))
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
        self.shape_mode = 'rect'
        self.ellipse_mode = 'ellipse'
        self.arrow_mode = 'straight'
        self.line_mode = 'straight'
        self.setCursor(Qt.CrossCursor)
        self._pan_active = False
        self._pan_start_pos = QPoint()
        self._pan_start_scroll = QPoint()

        # Виджеты
        self.zoom_widget = ZoomWidget(self)
        self.zoom_widget.zoomChanged.connect(self._on_zoom_widget_changed)
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

        self.scene().selectionChanged.connect(self._sync_selection_properties)

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
            color = item._text_item.defaultTextColor() if item._text_item else QColor(160, 0, 0)
            width = int(item._pen.widthF())
        else:
            return
        if color and color.isValid():
            self._update_info_widget_content(color, width if width is not None else 0)
        else:
            self._update_info_widget_content(QColor(0, 0, 0), 0)

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
        zy = zw.y() if zw else vh - sh - zw.height() - 4
        x = vw - iw.width() - sw - 4
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

    def _on_text_bg_changed(self, m):
        if self.active_text_item:
            self.active_text_item.bg_color = QColor(255, 255, 255, 200) if m == 'white' else QColor(0, 0, 0, 200) if m == 'black' else None
            self.active_text_item.update()
        else:
            for item in self.scene().selectedItems():
                if isinstance(item, TextItem):
                    item.bg_color = QColor(255, 255, 255, 200) if m == 'white' else QColor(0, 0, 0, 200) if m == 'black' else None
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
        selected_text = self.get_selected_text_item()
        show = (self.current_tool == 'text') or (selected_text is not None) or (self.active_text_item is not None)
        self.text_format_widget.setVisible(show)
        if show:
            self._update_text_format_widget_position()
            if selected_text and selected_text.bg_color:
                if selected_text.bg_color == QColor(255, 255, 255, 200):
                    self.text_format_widget.set_current_bg('white')
                elif selected_text.bg_color == QColor(0, 0, 0, 200):
                    self.text_format_widget.set_current_bg('black')
                else:
                    self.text_format_widget.set_current_bg(None)
            elif self.active_text_item and self.active_text_item.bg_color:
                if self.active_text_item.bg_color == QColor(255, 255, 255, 200):
                    self.text_format_widget.set_current_bg('white')
                elif self.active_text_item.bg_color == QColor(0, 0, 0, 200):
                    self.text_format_widget.set_current_bg('black')
                else:
                    self.text_format_widget.set_current_bg(None)
            else:
                self.text_format_widget.set_current_bg(None)

    def _update_cursor(self, pos):
        sp = self.mapToScene(pos)
        item = self.scene().itemAt(sp, self.transform())
        if self.active_text_item and item is self.active_text_item and self.active_text_item._editable:
            self.viewport().setCursor(Qt.IBeamCursor)
            return
        if item and not isinstance(item, QGraphicsPixmapItem) and (item.flags() & QGraphicsItem.ItemIsMovable):
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

    def mousePressEvent(self, e):
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

        if e.button() == Qt.LeftButton:
            sp = self.mapToScene(e.pos())
            item = self.scene().itemAt(sp, self.transform())
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
        if self._pan_active:
            dx = e.pos().x() - self._pan_start_pos.x()
            dy = e.pos().y() - self._pan_start_pos.y()
            scale = self.transform().m11()
            if scale != 0:
                self.horizontalScrollBar().setValue(int(self._pan_start_scroll.x() - dx / scale))
                self.verticalScrollBar().setValue(int(self._pan_start_scroll.y() - dy / scale))
            e.accept()
            return

        if self._drag_item:
            sp = self.mapToScene(e.pos())
            self._drag_item.setPos(sp + self._drag_offset)
            self.scene().update()
            e.accept()
            return

        self._update_cursor(e.pos())

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

        if self.rubber_band_active and self.rubber_band_item:
            cp = self.mapToScene(e.pos())
            self.rubber_band_item.setRect(QRectF(self.rubber_band_start, cp).normalized())
            e.accept()
            return

        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MiddleButton and self._pan_active:
            self._pan_active = False
            self._refresh_cursor()
            e.accept()
            return

        if self._drag_item:
            self._drag_item = None
            e.accept()
            return

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
            if isinstance(self.temp_item, DimensionItem) and self.temp_item._text_item:
                self.temp_item._text_item.begin_editing()
                self._update_info_widget_content(self.temp_item._text_item.defaultTextColor(), max(1, int(round(self.temp_item._pen.widthF()))))
            self.temp_item = None
            self.start_point = None
            e.accept()
            return

        super().mouseReleaseEvent(e)

    def set_text_bg(self, bg):
        self.current_text_bg = bg

    def _remove_empty_text(self, item):
        if item.scene():
            item.scene().removeItem(item)
        if self.active_text_item is item:
            self.active_text_item = None

    def _text_editing_finished(self, item):
        if self.active_text_item is item:
            self.active_text_item = None
        if isinstance(item, TextItem):
            item._editable = False
            item.setTextInteractionFlags(Qt.NoTextInteraction)

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
            if isinstance(item, DimensionTextItem) and isinstance(item.parentItem(), DimensionItem):
                return item.parentItem()
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
        self.right_click_temp_pointer = False
        self.previous_tool_for_right_click = None
        self.modifier_temp_pointer = False
        self.previous_tool_for_modifier = None
        self._apply_tool(t)
        self._first_click_after_activation = (t == 'text')
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
        self.shape_mode_widget.setVisible(t == 'rect')
        self.ellipse_mode_widget.setVisible(t == 'ellipse')
        self.arrow_mode_widget.setVisible(t == 'arrow')
        self.line_mode_widget.setVisible(t == 'line')
        if not self.scene().selectedItems():
            self._update_info_widget_content(self.current_pen_color, self.get_current_width())
        QTimer.singleShot(0, self._refresh_cursor)

    def set_pen_color(self, c):
        self.current_pen_color = c

    def set_pen_width(self, w):
        sd = self.get_selected_dimension_item()
        if sd:
            sd.setDimensionWidth(w)
            self._update_info_widget_content(sd._text_item.defaultTextColor() if sd._text_item else self.current_pen_color, int(round(sd._pen.widthF())))
            return
        if self.get_selected_text_item() or self.active_text_item or self.current_tool == 'text':
            self.set_text_size(w)
            return
        self.pen_width = w
        self.apply_current_style_to_selected()
        if not self.scene().selectedItems():
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
        elif self.modifier_temp_pointer and not self.right_click_temp_pointer:
            self._apply_tool(self.previous_tool_for_modifier)
            self.modifier_temp_pointer = False
            self.previous_tool_for_modifier = None

    def delete_selected(self):
        for item in self.scene().selectedItems():
            if isinstance(item, QGraphicsPixmapItem):
                continue
            self.scene().removeItem(item)
            if item is self.active_text_item:
                self.active_text_item = None
        self.scene().clearSelection()

    def apply_current_style_to_selected(self):
        for item in self.scene().selectedItems():
            if isinstance(item, (RectangleItem, EllipseItem, ArrowItem, CurvedArrowItem, FilledRectItem, CloudItem, DimensionItem, LineItem, WavyLineItem)):
                if isinstance(item, DimensionItem):
                    item.setTextColor(self.current_pen_color)
                    continue
                pen = QPen(self.current_pen_color, self.pen_width)
                if isinstance(item, (RectangleItem, EllipseItem, CloudItem, LineItem, WavyLineItem)):
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setJoinStyle(Qt.RoundJoin)
                    if isinstance(item, LineItem) and self.line_mode == 'dashed':
                        pen.setStyle(Qt.DashLine)
                elif isinstance(item, ArrowItem):
                    pass
                elif isinstance(item, CurvedArrowItem):
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setJoinStyle(Qt.RoundJoin)
                item.setPen(pen)
                if isinstance(item, FilledRectItem):
                    item.setBrush(QColor(self.current_pen_color.red(), self.current_pen_color.green(), self.current_pen_color.blue(), 80))
            elif isinstance(item, QGraphicsTextItem):
                item.setDefaultTextColor(self.current_pen_color)
                item.update()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete:
            self.delete_selected()
            e.accept()
            return
        if e.key() == Qt.Key_Escape:
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
        text_item = None
        dimension = None
        for cand in self.scene().items(sp):
            if isinstance(cand, DimensionTextItem):
                text_item = cand
                dimension = cand.parent_dimension
                break
            d = self._dimension_parent(cand)
            if isinstance(d, DimensionItem):
                dimension = d
                if dimension and dimension._text_item:
                    text_item = dimension._text_item
                    break
        if text_item:
            if dimension is None and isinstance(text_item.parentItem(), DimensionItem):
                dimension = text_item.parentItem()
            text_item.begin_editing()
            if dimension:
                self._update_info_widget_content(text_item.defaultTextColor(), max(1, int(round(dimension._pen.widthF()))))
            e.accept()
            return
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