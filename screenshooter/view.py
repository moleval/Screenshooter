"""
Модуль: view.py
Описание: Основной виджет редактора (EditorView) на базе QGraphicsView.
"""

import math
from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF, QPoint, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import (QPainter, QPen, QColor, QPolygonF, QFont, QImage,
                         QIcon, QPainterPath, QCursor, QBrush, QPixmap, QKeySequence)
from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsRectItem,
                             QGraphicsEllipseItem, QGraphicsPixmapItem,
                             QGraphicsTextItem, QGraphicsItem, QStyle,
                             QInputDialog, QLabel, QApplication, QShortcut)

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
                                   ShapeModeWidgetArrow, LineModeWidget,
                                   LayerModeWidget, ImageOpacityWidget)
from .history import (HistoryManager, AddItemCommand, RemoveItemCommand,
                      MoveItemCommand, MoveItemsCommand, ChangePenCommand,
                      AddPastedImageCommand, RemovePastedImageCommand,
                      ResizePastedImageCommand, CropPastedImageCommand,
                      RotatePastedImageCommand, RemoveSelectedItemsCommand, ChangeImageOpacityCommand,
                      MoveBlurRegionCommand, ResizeBlurRegionCommand)
from .history import ChangeLayerCommand
from .image_edit_controller import ImageEditController
from .ui.layout_manager import LayoutManager
from .tools import RectTool, EllipseTool, LineTool, ArrowTool, TextTool
from .controllers import (ClipboardController, ManipulationController,
                          KeyboardManager, FloatingWidgetManager,
                          PastedImageController, BlurController)
from .controllers.mouse_interaction_manager import MouseInteractionManager
from .theme import theme_manager


class EditorView(QGraphicsView):
    TEXT_FORMAT_TOP_OFFSET = 10
    TEXT_FORMAT_RIGHT_OFFSET = 8
    zoomChangedByWheel = pyqtSignal(float, object)
    crop_mode_changed = pyqtSignal(bool)
    blur_mode_changed = pyqtSignal(bool)
    background_changed = pyqtSignal()

    def __init__(self, scene):
        super().__init__(scene)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        # Полосы появляются только когда реальная подложка/масштаб
        # требуют прокрутки. Временное расширение sceneRect не используется
        # при захвате объекта, поэтому ложного появления быть не должно.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Полосы прокрутки — отдельные дочерние виджеты QGraphicsView.
        # Курсор редактора (крест) не должен наследоваться ими.
        self.horizontalScrollBar().setCursor(Qt.ArrowCursor)
        self.verticalScrollBar().setCursor(Qt.ArrowCursor)

        self._interaction_dragging = False
        self.current_tool = None
        self.start_point = None
        self.temp_item = None
        self.current_pen_color = QColor("#D25145")   # красный из палитры
        self.pen_width = 2
        self.text_size = 10
        self.auto_fit = True
        self.normal_background_color = theme_manager.get_color('editor_bg')
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

        self.layer_widget = LayerModeWidget(self)
        self.layer_widget.setVisible(False)

        self.image_opacity_widget = ImageOpacityWidget(
            self, width=self.layer_widget.width() * 3)
        self.image_opacity_widget.setVisible(False)
        self.layer_widget.layerChanged.connect(self._on_layer_widget_changed)
        # Прозрачность шириной в три панели слоёв.
        self.image_opacity_widget.setFixedWidth(self.layer_widget.width() * 3)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAttribute(Qt.WA_TranslucentBackground)
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

        # Создаём диспетчер событий мыши
        self.mouse_manager = MouseInteractionManager(
            self,
            self.blur_controller,
            self.image_editor,
            self.manipulation_controller,
        )

        self.widget_manager.update_info_widget_content(
            self.current_pen_color, self.pen_width)

        for w in (self.zoom_widget, self.text_format_widget,
                  self.shape_mode_widget, self.ellipse_mode_widget,
                  self.arrow_mode_widget, self.line_mode_widget,
                  self.info_widget, self.layer_widget, self.image_opacity_widget,
                  self.status_label):
            w.setCursor(Qt.ArrowCursor)

        self.scene().selectionChanged.connect(self._schedule_selection_update)

        self._selection_update_timer = QTimer(self)
        self._selection_update_timer.setSingleShot(True)
        self._selection_update_timer.setInterval(0)
        self._selection_update_timer.timeout.connect(self._do_selection_update)

        self.crop_mode_changed.connect(self._on_crop_mode_changed)

        # Горячие клавиши масштабирования (+/-)
        self.zoom_in_shortcut = QShortcut(QKeySequence(Qt.Key_Plus), self)
        self.zoom_in_shortcut.activated.connect(self._on_zoom_in_shortcut)
        self.zoom_out_shortcut = QShortcut(QKeySequence(Qt.Key_Minus), self)
        self.zoom_out_shortcut.activated.connect(self._on_zoom_out_shortcut)

        # Горячая клавиша разворачивания/восстановления окна.
        # Shift+Enter не должен зависеть от состояния фокуса дочерних виджетов.
        self.fullscreen_shortcut = QShortcut(
            QKeySequence(Qt.SHIFT + Qt.Key_Return), self)
        self.fullscreen_shortcut.setContext(Qt.ApplicationShortcut)
        self.fullscreen_shortcut.activated.connect(self._on_fullscreen_shortcut)

        # Горячая клавиша вписывания изображения в окно
        self.fit_shortcut = QShortcut(QKeySequence(Qt.ALT + Qt.Key_Return), self)
        self.fit_shortcut.activated.connect(self._on_fit_shortcut)

    def _on_fullscreen_shortcut(self):
        """Разворачивает окно или возвращает его к прежнему размеру."""
        window = self.window()
        if window.isMaximized():
            window.showNormal()
        else:
            window.showMaximized()

    # ==============================================================
    # Вспомогательные
    # ==============================================================
    def set_scene_rect_preserving_view(self, rect):
        """Меняет sceneRect синхронно, сохраняя точку под центром viewport."""
        rect = QRectF(rect)
        if rect.isEmpty():
            self.setSceneRect(rect)
            return

        try:
            center = self.mapToScene(self.viewport().rect().center())
            self.setSceneRect(rect)
            self.centerOn(center)
        except (RuntimeError, AttributeError):
            self.setSceneRect(rect)

    def _is_point_inside_background(self, scene_pos):
        """Проверяет, попадает ли точка в пределы подложки."""
        bg = self.image_editor.background_item
        if bg is None or sip.isdeleted(bg):
            return False
        bg_rect = bg.mapRectToScene(QRectF(bg.pixmap().rect()))
        return bg_rect.contains(scene_pos)

    def _schedule_selection_update(self):
        if not self._selection_update_timer.isActive():
            self._selection_update_timer.start()

    def _do_selection_update(self):
        try:
            self.widget_manager.sync_selection_properties()
            self.update_layer_widget()
            self.widget_manager.update_floating_widgets_visibility()
            self.widget_manager.update_resolution_for_selection()
            self._update_blur_region_handles()
        except RuntimeError:
            pass

    def _on_crop_mode_changed(self, active):
        if active:
            self._enable_crop_status_style()
        else:
            self._disable_crop_status_style()

    def _enable_crop_status_style(self):
        if hasattr(self, 'status_label') and self.status_label is not None:
            self.image_editor.status_bar_manager.set_crop_status(self.image_editor.crop_target_item)
            self.status_label.setVisible(True)

    def _disable_crop_status_style(self):
        if hasattr(self, 'status_label') and self.status_label is not None:
            self.image_editor.status_bar_manager.reset_to_normal()
            self.status_label.setVisible(False)

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

        # Завершение текста может происходить не только через явный
        # обработчик редактирования, поэтому здесь тоже фиксируем выход
        # текста за пределы подложки.
        self.expand_background_to_content(margin=0)

    # ==============================================================
    # Undo / Redo
    # ==============================================================
    def undo(self):
        # История не должна принудительно вписывать подложку в окно.
        # Особенно это заметно после поворота: изменение размеров pixmap
        # не означает, что пользователь просил менять масштаб/позицию вида.
        self.history.undo()
        self._update_after_history_change()
        self._invalidate_cursor_cache()

    def redo(self):
        self.history.redo()
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
            self.set_scene_rect_preserving_view(
                self.image_editor.background_item.sceneBoundingRect())
            self.update_resolution_from_background()
        self.widget_manager.update_floating_widgets_visibility()
        self._update_pasted_image_handles()
        self._update_blur_region_handles()
        self.update_layer_widget()

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

    def set_background_from_pixmap(self, pixmap):
        self.clear_pasted_images()
        self.scene().clear()
        self.active_text_item = None
        self.history.clear()

        # Сбрасываем ссылку на предыдущий фон
        self.image_editor.background_item = None
        self.image_editor.crop_target_item = None

        item = QGraphicsPixmapItem(pixmap)
        item.setTransformationMode(Qt.SmoothTransformation)
        item.setAcceptedMouseButtons(Qt.NoButton)
        item.setZValue(-1000)

        self.scene().addItem(item)
        self.set_background_item(item)

        self.setSceneRect(QRectF(pixmap.rect()))
        self.auto_fit = True
        self.fitInView(item, Qt.KeepAspectRatio)
        scale = self.transform().m11() * 100
        self.zoom_widget.set_zoom(scale)

        self.set_resolution_text(f"{pixmap.width()}×{pixmap.height()}")

        self.image_editor.crop_mode = False
        self.blur_controller.blur_mode = False

        self.crop_mode_changed.emit(False)
        self.blur_mode_changed.emit(False)
        self.layer_widget.setVisible(False)
        self._update_floating_widgets_visibility()

        self.background_changed.emit()

    def clear_scene(self):
        self.clear_pasted_images()
        self.scene().clear()
        self.active_text_item = None
        self.history.clear()

        # Сбрасываем ссылки на фоновое изображение
        self.image_editor.background_item = None
        self.image_editor.crop_target_item = None

        self.image_editor.reset_state()
        self.blur_controller.reset_state()

        self.set_resolution_text("")
        self.layer_widget.setVisible(False)
        self._update_floating_widgets_visibility()

        self.background_changed.emit()

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
    # Вставленные изображения
    # ==============================================================
    @property
    def pasted_images(self):
        return self.pasted_image_controller.pasted_images

    def expand_interaction_scene_rect(self):
        """Расширяет только рабочую область сцены вокруг подложки."""
        bg = self.image_editor.background_item
        if bg is None or sip.isdeleted(bg) or bg.scene() is not self.scene():
            return

        bg_rect = bg.sceneBoundingRect()
        scale = abs(self.transform().m11())
        if scale < 0.001:
            scale = 1.0
        visible_w = max(1.0, self.viewport().width() / scale)
        visible_h = max(1.0, self.viewport().height() / scale)
        pad_x = max(1000.0, visible_w * 2.0)
        pad_y = max(1000.0, visible_h * 2.0)
        work_rect = bg_rect.adjusted(-pad_x, -pad_y, pad_x, pad_y)
        self.set_scene_rect_preserving_view(self.sceneRect().united(work_rect))

    def prepare_drag_scene_rect(self, cursor_pos=None):
        """Расширяет временную рабочую область для перетаскивания.

        При переданной позиции курсора сохраняется именно точка сцены под
        курсором. Это предотвращает скачок при изменении scrollbars, особенно
        при начале движения объекта влево или вверх.
        """
        bg = self.image_editor.background_item
        if bg is None or sip.isdeleted(bg) or bg.scene() is not self.scene():
            return

        bg_rect = bg.sceneBoundingRect()
        scale = abs(self.transform().m11())
        if scale < 0.001:
            scale = 1.0

        visible_w = max(1.0, self.viewport().width() / scale)
        visible_h = max(1.0, self.viewport().height() / scale)
        pad_x = max(5000.0, visible_w * 4.0)
        pad_y = max(5000.0, visible_h * 4.0)
        work_rect = bg_rect.adjusted(-pad_x, -pad_y, pad_x, pad_y)
        new_rect = self.sceneRect().united(work_rect)

        if cursor_pos is None:
            self.set_scene_rect_preserving_view(new_rect)
            return

        anchor_before = self.mapToScene(cursor_pos)
        self.setSceneRect(new_rect)
        anchor_after = self.mapToScene(cursor_pos)

        dx = anchor_before.x() - anchor_after.x()
        dy = anchor_before.y() - anchor_after.y()
        if abs(dx) > 0.0001 or abs(dy) > 0.0001:
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() + int(round(dx * scale))
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() + int(round(dy * scale))
            )

    def expand_background_to_content(self, margin=50, threshold=1):
        """Расширяет подложку белыми полями под вышедшие за неё объекты.

        Подложка расширяется именно в сторону выхода объекта:
        при выходе влево/вверх двигается сама подложка, а объект остаётся
        в прежних координатах сцены. Это не даёт левому/верхнему расширению
        превращаться в рост canvas вправо/вниз.
        """
        bg = self.image_editor.background_item
        if bg is None or sip.isdeleted(bg) or bg.scene() is not self.scene():
            return False

        old_pixmap = bg.pixmap()
        if old_pixmap.isNull():
            return False

        old_bg_rect = bg.sceneBoundingRect()
        content_rect = QRectF(old_bg_rect)

        for item in self.scene().items():
            if item is bg or self._is_background_item(item):
                continue
            try:
                if not item.isVisible():
                    continue
                item_rect = item.sceneBoundingRect()
                if item_rect.isValid() and not item_rect.isEmpty():
                    content_rect = content_rect.united(item_rect)
            except RuntimeError:
                continue

        left_extra = max(0.0, old_bg_rect.left() - content_rect.left())
        top_extra = max(0.0, old_bg_rect.top() - content_rect.top())
        right_extra = max(0.0, content_rect.right() - old_bg_rect.right())
        bottom_extra = max(0.0, content_rect.bottom() - old_bg_rect.bottom())

        extras = [left_extra, top_extra, right_extra, bottom_extra]
        extras = [0.0 if value <= threshold else value + margin for value in extras]
        left_extra, top_extra, right_extra, bottom_extra = extras

        if not any(extras):
            self.set_scene_rect_preserving_view(old_bg_rect)
            return False

        new_width = max(
            1, int(round(old_pixmap.width() + left_extra + right_extra))
        )
        new_height = max(
            1, int(round(old_pixmap.height() + top_extra + bottom_extra))
        )

        new_pixmap = QPixmap(new_width, new_height)
        new_pixmap.fill(Qt.white)

        painter = QPainter(new_pixmap)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(
            int(round(left_extra)),
            int(round(top_extra)),
            old_pixmap,
        )
        painter.end()

        if self.blur_controller.blur_base_pixmap is not None:
            blur_base = QPixmap(new_width, new_height)
            blur_base.fill(Qt.white)
            bp = QPainter(blur_base)
            bp.setRenderHint(QPainter.SmoothPixmapTransform)
            bp.drawPixmap(
                int(round(left_extra)),
                int(round(top_extra)),
                self.blur_controller.blur_base_pixmap,
            )
            bp.end()
            self.blur_controller.blur_base_pixmap = blur_base

        # При расширении слева/сверху двигаем только подложку.
        # Все объекты остаются в своих сценовых координатах, поэтому их
        # положение относительно курсора/экрана не меняется.
        bg.setPos(
            bg.pos() + QPointF(-left_extra, -top_extra)
        )

        bg.setPixmap(new_pixmap)
        bg.update()
        self.blur_controller._invalidate_blur_cache()
        self.blur_controller._recompute_blurred_pixmap()

        new_bg_rect = bg.sceneBoundingRect()
        self.set_scene_rect_preserving_view(new_bg_rect)
        self.update_resolution_from_background()
        self.scene().update()
        return True

    def get_background_canvas_state(self):
        bg = self.image_editor.background_item
        if bg is None or sip.isdeleted(bg):
            return None
        return bg.pixmap(), bg.pos()

    def add_pasted_image(self, pixmap, scene_pos=None):
        """Добавляет изображение на сцену."""
        if self.background_item is None or sip.isdeleted(self.background_item):
            self.set_background_from_pixmap(pixmap)
            return None

        item = PastedImageItem(pixmap, self)
        self.scene().addItem(item)
        self.pasted_images.append(item)

        if scene_pos is None:
            center = self.mapToScene(self.viewport().rect().center())
            scene_pos = center - QPointF(pixmap.width() / 2, pixmap.height() / 2)

        item.setPos(scene_pos)

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
                        scene_pos = self.mapToScene(e.pos())
                        scene_pos -= QPointF(pixmap.width() / 2, pixmap.height() / 2)
                        if self.background_item is None or sip.isdeleted(self.background_item):
                            self.set_background_from_pixmap(pixmap)
                        else:
                            self.add_pasted_image(pixmap, scene_pos)
            e.acceptProposedAction()
        else:
            e.ignore()

    # ==============================================================
    # Статусный виджет
    # ==============================================================
    def set_resolution_text(self, text):
        self.widget_manager.set_resolution_text(text)

    def show_status_message(self, message, duration=15000):
        self.widget_manager.show_status_message(message, duration)

    # ==============================================================
    # Мышь
    # ==============================================================
    def mousePressEvent(self, e):
        if self.mouse_manager.handle_press(e):
            e.accept()
            return
        super().mousePressEvent(e)
        e.accept()

    def mouseMoveEvent(self, e):
        if self.mouse_manager.handle_move(e):
            e.accept()
            return
        self._update_cursor(e.pos())
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self.mouse_manager.handle_release(e):
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() != Qt.LeftButton:
            super().mouseDoubleClickEvent(e)
            return
        sp = self.mapToScene(e.pos())
        item = self._interactive_item_at(sp)
        li = item

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
            ti.setDefaultTextColor(QColor("#F9D556"))
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
            if self.blur_controller.blur_regions:
                self.blur_controller._force_blur_recompute()
            e.accept()
            return

        super().mouseDoubleClickEvent(e)

    # ==============================================================
    # Клавиатура
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
            delta = e.angleDelta().y()
            if delta != 0:
                cur_percent = self.transform().m11() * 100.0
                # Масштаб меняется пропорционально величине wheel delta,
                # без округления до целых процентов. Один обычный "щелчок"
                # даёт небольшой шаг, а быстрый прокрут — пропорционально больше.
                factor = math.pow(1.0005, delta)
                new_percent = max(10.0, min(400.0, cur_percent * factor))
                self.auto_fit = False
                self.zoomChangedByWheel.emit(new_percent, e.pos())
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

        # Удаление/отмена аннотации не должно оставлять старый результат
        # размытия после её пересечения с blur.
        if self.blur_controller.blur_regions:
            self.blur_controller._force_blur_recompute()
        self.manipulation_controller._restore_tool_if_needed()
        self._invalidate_cursor_cache()
        self._update_pasted_image_handles()
        self._update_blur_region_handles()
        self.viewport().update()


    # ==============================================================
    # Слои изображений и размытия
    # ==============================================================
    def _is_layerable_item(self, item):
        return isinstance(item, (PastedImageItem, BlurRegionItem))

    def _on_layer_widget_changed(self, layer):
        selected = [
            item for item in self.scene().selectedItems()
            if self._is_layerable_item(item)
        ]
        if not selected:
            return

        old_layers = [getattr(item, 'layer', 1) for item in selected]
        layer = 1 if int(layer) == 1 else 2
        if all(old == layer for old in old_layers):
            return

        self.history.push(ChangeLayerCommand(selected, old_layers, layer))
        self.layer_widget.set_current_mode(layer)
        # После смены z-порядка курсор и выбор должны немедленно
        # использовать новый верхний объект.
        self._invalidate_cursor_cache()
        if any(isinstance(item, (PastedImageItem, BlurRegionItem)) for item in selected):
            self.blur_controller._force_blur_recompute()
            self._update_blur_region_handles()

    def update_layer_widget(self):
        selected = [
            item for item in self.scene().selectedItems()
            if self._is_layerable_item(item)
        ]
        if not selected:
            self.layer_widget.setVisible(False)
            return

        layer = getattr(selected[0], 'layer', 1)
        self.layer_widget.set_current_mode(layer)
        self.layer_widget.setVisible(True)
        self.layer_widget.raise_()
        self.layout_manager.update_all(immediate=True)

    # ==============================================================
    # Обёртки для совместимости
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

        # Временное рабочее поле вокруг подложки: элементы можно свободно
        # создавать и перемещать за её пределами. Сама подложка меняется
        # только после завершения операции.
        if t:
            self.expand_interaction_scene_rect()
        else:
            bg = self.image_editor.background_item
            if (bg is not None and not sip.isdeleted(bg)
                    and bg.scene() is self.scene()):
                self.set_scene_rect_preserving_view(bg.sceneBoundingRect())

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
    def _interactive_item_at(self, scene_pos):
        """Возвращает объект, с которым должен взаимодействовать курсор.

        Сначала учитывается уже выбранная зона размытия: аннотация поверх
        blur не должна внезапно перехватывать его перетаскивание/выделение.
        Для нового выбора сохраняется обычный z-order: аннотации (z=0)
        остаются выше изображений/blur.
        """
        items = []
        for item in self.scene().items(QPointF(scene_pos)):
            if self._is_background_item(item):
                continue
            if not (item.flags() & QGraphicsItem.ItemIsSelectable):
                continue
            items.append(self._item_for_manipulation(item))

        # Выбранный blur не должен блокировать выбор объекта, который
        # находится визуально выше него. Раньше выбранный blur получал
        # безусловный приоритет, из-за чего аннотацию, полностью лежащую
        # внутри blur, было невозможно снова выбрать.
        #
        # Сохраняем обычный z-order: если верхний selectable-объект —
        # аннотация или картинка, выбираем именно его. Выбранный blur
        # получает приоритет только когда сам является верхним объектом
        # в точке клика (либо когда выше него ничего selectable нет).
        if items:
            top_item = items[0]
            if not isinstance(top_item, BlurRegionItem):
                return top_item

            for item in items:
                if isinstance(item, BlurRegionItem):
                    return item

        return None

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
    # Обновление цветов темы
    # ==============================================================
    def update_theme_colors(self):
        self.normal_background_color = theme_manager.get_color('editor_bg')
        self.setBackgroundBrush(self.normal_background_color)
        self.viewport().update()
        from .controllers.crop_cursor_factory import CropCursorFactory
        CropCursorFactory.reset()

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

    # ==============================================================
    # Горячие клавиши масштабирования (+/-)
    # ==============================================================
    def _on_zoom_in_shortcut(self):
        if self.active_text_item and self.active_text_item._editable:
            return
        self.zoom_widget.zoom_in()

    def _on_zoom_out_shortcut(self):
        if self.active_text_item and self.active_text_item._editable:
            return
        self.zoom_widget.zoom_out()

    def _on_fit_shortcut(self):
        """Обработчик Alt+Enter: вписать изображение в окно."""
        if self.active_text_item and self.active_text_item._editable:
            return
        self.zoom_widget.fitRequested.emit()