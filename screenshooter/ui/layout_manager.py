"""
Модуль: ui/layout_manager.py
Описание: Менеджер позиционирования плавающих виджетов (ZoomWidget, InfoWidget,
          панели режимов, TextFormatWidget, статусная метка).
          Централизует вычисление координат, чтобы разгрузить EditorView.
"""

from PyQt5.QtCore import QTimer


class LayoutManager:
    """
    Управляет расположением всех плавающих элементов интерфейса в EditorView.
    Содержит методы для обновления позиций каждого виджета с учётом
    размеров viewport и полос прокрутки.
    """

    # Константы, ранее определённые в EditorView
    TEXT_FORMAT_TOP_OFFSET = 10
    TEXT_FORMAT_RIGHT_OFFSET = 8

    def __init__(self, view):
        """
        :param view: ссылка на EditorView (QGraphicsView)
        """
        self.view = view

        # Сохраняем ссылки на виджеты для удобства
        self.zoom_widget = view.zoom_widget
        self.text_format_widget = view.text_format_widget
        self.shape_mode_widget = view.shape_mode_widget
        self.ellipse_mode_widget = view.ellipse_mode_widget
        self.arrow_mode_widget = view.arrow_mode_widget
        self.line_mode_widget = view.line_mode_widget
        self.info_widget = view.info_widget
        self.status_label = view.status_label

        # ЭТАП 3: таймер дебаунса для update_all()
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(16)  # ~60 fps
        self._update_timer.timeout.connect(self._do_update_all)

    def update_all(self):
        """Запускает отложенное обновление позиций виджетов.
        Если вызывается несколько раз подряд, реальное обновление
        произойдёт только один раз за 16 мс."""
        if not self._update_timer.isActive():
            self._update_timer.start()

    def _do_update_all(self):
        """Реальное обновление позиций всех виджетов."""
        self.update_zoom_widget_position()
        self.update_text_format_widget_position()
        self.update_shape_mode_widget_position()
        self.update_ellipse_mode_widget_position()
        self.update_arrow_mode_widget_position()
        self.update_line_mode_widget_position()
        self.update_info_widget_position()
        self.update_status_label_position()

    # ---- Вспомогательные методы для получения размеров viewport и полос прокрутки ----

    def _viewport_rect(self):
        """Возвращает QRect viewport с учётом возможного отсутствия viewport."""
        vp = self.view.viewport()
        if not vp:
            return None
        return vp.rect()

    def _scrollbar_width(self):
        """Ширина вертикальной полосы прокрутки, если она видима."""
        sb = self.view.verticalScrollBar()
        return sb.width() if sb and sb.isVisible() else 0

    def _scrollbar_height(self):
        """Высота горизонтальной полосы прокрутки, если она видима."""
        sb = self.view.horizontalScrollBar()
        return sb.height() if sb and sb.isVisible() else 0

    # ---- Позиционирование отдельных виджетов ----

    def update_zoom_widget_position(self):
        """
        Размещает ZoomWidget в правом нижнем углу viewport,
        с отступом от краёв и от полос прокрутки.
        """
        zw = self.zoom_widget
        if not zw:
            return
        vp_rect = self._viewport_rect()
        if not vp_rect:
            return
        vw, vh = vp_rect.width(), vp_rect.height()
        sw = self._scrollbar_width()
        sh = self._scrollbar_height()
        x = vw - zw.width() - sw - 4
        y = vh - zw.height() - sh - 4
        x = max(0, x)
        y = max(0, y)
        zw.move(x, y)
        zw.raise_()

    def update_text_format_widget_position(self):
        """
        Размещает TextFormatWidget в правом верхнем углу viewport,
        если он видим.
        """
        tfw = self.text_format_widget
        if not tfw or not tfw.isVisible():
            return
        vp_rect = self._viewport_rect()
        if not vp_rect:
            return
        vw, vh = vp_rect.width(), vp_rect.height()
        sw = self._scrollbar_width()
        sh = self._scrollbar_height()
        x = vw - tfw.width() - sw - self.TEXT_FORMAT_RIGHT_OFFSET
        y = self.TEXT_FORMAT_TOP_OFFSET
        x = max(0, x)
        y = max(0, y)
        tfw.move(x, y)
        tfw.raise_()

    def update_shape_mode_widget_position(self):
        """
        Размещает ShapeModeWidget (режимы прямоугольника) в правом верхнем углу,
        если он видим.
        """
        smw = self.shape_mode_widget
        if not smw or not smw.isVisible():
            return
        vp_rect = self._viewport_rect()
        if not vp_rect:
            return
        vw, vh = vp_rect.width(), vp_rect.height()
        sw = self._scrollbar_width()
        sh = self._scrollbar_height()
        x = vw - smw.width() - sw - self.TEXT_FORMAT_RIGHT_OFFSET
        y = self.TEXT_FORMAT_TOP_OFFSET
        x = max(0, x)
        y = max(0, y)
        smw.move(x, y)
        smw.raise_()

    def update_ellipse_mode_widget_position(self):
        """
        Размещает ShapeModeWidgetEllipse (режимы эллипса) в правом верхнем углу,
        если он видим.
        """
        emw = self.ellipse_mode_widget
        if not emw or not emw.isVisible():
            return
        vp_rect = self._viewport_rect()
        if not vp_rect:
            return
        vw, vh = vp_rect.width(), vp_rect.height()
        sw = self._scrollbar_width()
        sh = self._scrollbar_height()
        x = vw - emw.width() - sw - self.TEXT_FORMAT_RIGHT_OFFSET
        y = self.TEXT_FORMAT_TOP_OFFSET
        x = max(0, x)
        y = max(0, y)
        emw.move(x, y)
        emw.raise_()

    def update_arrow_mode_widget_position(self):
        """
        Размещает ShapeModeWidgetArrow (режимы стрелок) в правом верхнем углу,
        если он видим.
        """
        amw = self.arrow_mode_widget
        if not amw or not amw.isVisible():
            return
        vp_rect = self._viewport_rect()
        if not vp_rect:
            return
        vw, vh = vp_rect.width(), vp_rect.height()
        sw = self._scrollbar_width()
        sh = self._scrollbar_height()
        x = vw - amw.width() - sw - self.TEXT_FORMAT_RIGHT_OFFSET
        y = self.TEXT_FORMAT_TOP_OFFSET
        x = max(0, x)
        y = max(0, y)
        amw.move(x, y)
        amw.raise_()

    def update_line_mode_widget_position(self):
        """
        Размещает LineModeWidget (режимы линий) в правом верхнем углу,
        если он видим.
        """
        lmw = self.line_mode_widget
        if not lmw or not lmw.isVisible():
            return
        vp_rect = self._viewport_rect()
        if not vp_rect:
            return
        vw, vh = vp_rect.width(), vp_rect.height()
        sw = self._scrollbar_width()
        sh = self._scrollbar_height()
        x = vw - lmw.width() - sw - self.TEXT_FORMAT_RIGHT_OFFSET
        y = self.TEXT_FORMAT_TOP_OFFSET
        x = max(0, x)
        y = max(0, y)
        lmw.move(x, y)
        lmw.raise_()

    def update_info_widget_position(self):
        """
        Размещает InfoWidget (индикатор цвета/толщины) над ZoomWidget,
        пристыкованным к его правому краю, чтобы не перекрывать поле ввода процентов.
        """
        iw = self.info_widget
        if not iw:
            return
        vp_rect = self._viewport_rect()
        if not vp_rect:
            return
        vw, vh = vp_rect.width(), vp_rect.height()
        sw = self._scrollbar_width()
        sh = self._scrollbar_height()

        # Позиционируем InfoWidget относительно ZoomWidget
        zw = self.zoom_widget
        if zw:
            # Берём позицию поля ввода процентов внутри ZoomWidget
            percent_edit = zw.percent_edit
            # Правый край поля ввода процентов (в глобальных координатах виджета zw)
            zoom_right = zw.x() + percent_edit.x() + percent_edit.width()
            zy = zw.y()
            x = zoom_right - iw.width()
            y = zy - iw.height() - 4
        else:
            # fallback – правый верхний угол
            x = vw - iw.width() - sw - 4
            y = 4

        x = max(0, x)
        y = max(0, y)
        iw.move(x, y)
        iw.raise_()

    def update_status_label_position(self):
        """
        Размещает статусную метку (разрешение/сообщения) в левом нижнем углу viewport.
        """
        sl = self.status_label
        if not sl or not sl.isVisible():
            return
        vp_rect = self._viewport_rect()
        if not vp_rect:
            return
        vw, vh = vp_rect.width(), vp_rect.height()
        sh = self._scrollbar_height()
        max_width = vw - 8
        sl.setMaximumWidth(max_width)
        sl.adjustSize()
        x = 4
        y = vh - sl.sizeHint().height() - sh - 4
        y = max(0, y)
        sl.move(x, y)
        sl.raise_()