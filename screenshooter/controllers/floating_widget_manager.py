"""
Модуль: controllers/floating_widget_manager.py
Описание: Контроллер управления плавающими виджетами редактора.
          Управляет видимостью виджетов режимов, синхронизацией свойств
          выделенных элементов и применением стиля.
"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPen, QColor, QFont
from PyQt5.QtWidgets import QGraphicsTextItem

from ..items import (RectangleItem, EllipseItem, FilledRectItem, CloudItem,
                     LineItem, WavyLineItem, ArrowItem, CurvedArrowItem,
                     DimensionItem, TextItem)
from ..history import ChangePenCommand


class FloatingWidgetManager:
    """
    Управляет плавающими виджетами редактора:
    видимость, синхронизация свойств, применение стиля.
    """

    def __init__(self, view):
        self.view = view

        # Подключаем сигналы виджетов
        view.text_format_widget.bgChanged.connect(self._on_text_bg_changed)
        view.shape_mode_widget.modeChanged.connect(self._on_shape_mode_changed)
        view.ellipse_mode_widget.modeChanged.connect(self._on_ellipse_mode_changed)
        view.arrow_mode_widget.modeChanged.connect(self._on_arrow_mode_changed)
        view.line_mode_widget.modeChanged.connect(self._on_line_mode_changed)

    # ==============================================================
    # Видимость и синхронизация
    # ==============================================================

    def sync_selection_properties(self):
        """Синхронизирует свойства выделенного элемента с виджетами."""
        view = self.view
        sel = view.scene().selectedItems()
        if not sel:
            self.update_info_widget_content(view.current_pen_color, view.pen_width)
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
            self.update_info_widget_content(color, width if width is not None else 0)
        else:
            self.update_info_widget_content(QColor(0, 0, 0), 0)

    def update_floating_widgets_visibility(self):
        """Обновляет видимость плавающих виджетов."""
        view = self.view
        view.shape_mode_widget.setVisible(False)
        view.ellipse_mode_widget.setVisible(False)
        view.arrow_mode_widget.setVisible(False)
        view.line_mode_widget.setVisible(False)
        view.text_format_widget.setVisible(False)

        # Текст выделен или активен — показываем виджет фона
        # (работает во всех режимах, включая Размыть)
        if view.current_tool == 'text':
            view.text_format_widget.setVisible(True)
            view.text_format_widget.raise_()
            view.layout_manager.update_all()
            return

        selected = view.scene().selectedItems()
        if selected:
            all_text = all(isinstance(item, TextItem) for item in selected)
            if all_text:
                view.text_format_widget.setVisible(True)
                view.layout_manager.update_all()
                return

        # Режимы обрезки/размытия — виджеты инструментов скрыты
        if view.image_editor.crop_mode or view.image_editor.blur_mode:
            view.layout_manager.update_all()
            return

        if view.current_tool == 'text':
            view.text_format_widget.setVisible(True)
            view.layout_manager.update_all()
            return

        if selected:
            view.layout_manager.update_all()
            return

        # Определяем активный инструмент с учётом временного указателя
        active_tool = view.current_tool
        if active_tool is None:
            mc = view.manipulation_controller
            if mc.right_click_temp_pointer and mc.previous_tool_for_right_click:
                active_tool = mc.previous_tool_for_right_click
            elif mc.modifier_temp_pointer and mc.previous_tool_for_modifier:
                active_tool = mc.previous_tool_for_modifier

        if active_tool == 'rect':
            view.shape_mode_widget.setVisible(True)
            view.shape_mode_widget.raise_()
        elif active_tool == 'ellipse':
            view.ellipse_mode_widget.setVisible(True)
            view.ellipse_mode_widget.raise_()
        elif active_tool == 'arrow':
            view.arrow_mode_widget.setVisible(True)
            view.arrow_mode_widget.raise_()
        elif active_tool == 'line':
            view.line_mode_widget.setVisible(True)
            view.line_mode_widget.raise_()

        view._update_pasted_image_handles()
        view.layout_manager.update_all()

    def update_info_widget_content(self, color, thickness):
        """Устанавливает цвет и толщину в виджет информации."""
        self.view.info_widget.set_info(color, thickness)
        QTimer.singleShot(0, self.view.layout_manager.update_info_widget_position)

    def update_text_format_widget_visibility(self):
        """Обновляет видимость виджета формата текста."""
        self.update_floating_widgets_visibility()

    # ==============================================================
    # Обработчики сигналов виджетов
    # ==============================================================

    def _on_text_bg_changed(self, m):
        """Обработчик смены фона текста."""
        view = self.view
        view.current_text_bg = (
            QColor(255, 255, 255, 200) if m == 'white' else
            QColor(0, 0, 0, 200) if m == 'black' else None)
        if view.active_text_item:
            view.active_text_item.bg_color = view.current_text_bg
            view.active_text_item.update()
        else:
            for item in view.scene().selectedItems():
                if isinstance(item, TextItem):
                    item.bg_color = view.current_text_bg
                    item.update()

    def _on_shape_mode_changed(self, m):
        self.view.shape_mode = m

    def _on_ellipse_mode_changed(self, m):
        self.view.ellipse_mode = m

    def _on_arrow_mode_changed(self, m):
        self.view.arrow_mode = m

    def _on_line_mode_changed(self, m):
        self.view.line_mode = m

    # ==============================================================
    # Применение стиля и сеттеры
    # ==============================================================

    def apply_current_style_to_selected(self, pen_color=None, pen_width=None):
        """Применяет цвет/толщину к выделенным элементам."""
        view = self.view
        for item in view.scene().selectedItems():
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
                    if isinstance(item, LineItem) and view.line_mode == 'dashed':
                        new_pen.setStyle(Qt.DashLine)
                elif isinstance(item, CurvedArrowItem):
                    new_pen.setCapStyle(Qt.RoundCap)
                    new_pen.setJoinStyle(Qt.RoundJoin)
                view.history.push(ChangePenCommand(item, current_pen, new_pen))

    def set_pen_color(self, c):
        """Устанавливает цвет пера."""
        view = self.view
        if view.scene().selectedItems():
            self.apply_current_style_to_selected(pen_color=c)
            self.sync_selection_properties()
        else:
            view.current_pen_color = c
            self.update_info_widget_content(view.current_pen_color, view.pen_width)

    def set_pen_width(self, w):
        """Устанавливает толщину пера."""
        view = self.view
        w = max(1, min(100, int(w)))
        if view.scene().selectedItems() or view.active_text_item:
            self.apply_current_style_to_selected(pen_width=w)
            self.sync_selection_properties()
        else:
            view.pen_width = w
            view.text_size = w
            self.update_info_widget_content(view.current_pen_color, view.pen_width)

    def set_text_size(self, v):
        """Устанавливает размер текста."""
        view = self.view
        v = max(1, min(100, int(v)))
        view.text_size = v
        st = self.get_selected_text_item()
        if st:
            font = st.font()
            font.setPointSize(max(1, v * 4))
            st.setFont(font)
            st.update()
        if view.active_text_item and isinstance(view.active_text_item, TextItem):
            font = view.active_text_item.font()
            font.setPointSize(max(1, v * 4))
            view.active_text_item.setFont(font)
            view.active_text_item.update()

    def set_text_bg(self, bg):
        """Устанавливает фон текста."""
        self.view.current_text_bg = bg

    # ==============================================================
    # Геттеры
    # ==============================================================

    def get_selected_text_item(self):
        """Возвращает выделенный текстовый элемент."""
        for item in self.view.scene().selectedItems():
            if isinstance(item, TextItem):
                return item
        return None

    def get_selected_dimension_item(self):
        """Возвращает выделенную размерную линию."""
        for item in self.view.scene().selectedItems():
            if isinstance(item, DimensionItem):
                return item
        return None

    def get_current_width(self):
        """Возвращает текущую толщину."""
        view = self.view
        sd = self.get_selected_dimension_item()
        if sd:
            return max(1, int(round(sd._pen.widthF())))
        st = self.get_selected_text_item()
        if st:
            return max(1, int(round(st.font().pointSize() / 4)))
        if view.active_text_item:
            return max(1, int(round(view.active_text_item.font().pointSize() / 4)))
        if view.current_tool == 'text':
            return view.text_size
        return view.pen_width

    # ==============================================================
    # Работа с текстом
    # ==============================================================

    def remove_empty_text(self, item):
        """Удаляет пустой текст со сцены."""
        view = self.view
        if item.scene():
            item.scene().removeItem(item)
        if view.active_text_item is item:
            view.active_text_item = None
        self.update_floating_widgets_visibility()

    def text_editing_finished(self, item):
        """Завершает редактирование текста."""
        view = self.view
        if view.active_text_item is item:
            view.active_text_item = None
        if isinstance(item, TextItem):
            item._editable = False
            item.setTextInteractionFlags(Qt.NoTextInteraction)
        self.update_floating_widgets_visibility()