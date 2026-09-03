"""
Модуль: controllers/clipboard_controller.py
Описание: Контроллер копирования/вставки элементов редактора.
          Управляет внутренним буфером обмена (не системным).
          Сериализует выделенные элементы в словари и создаёт
          новые элементы при вставке со смещением.
          При копировании во внутренний буфер также помещает
          в системный буфер MIME-маркер, чтобы при вставке
          можно было отличить наше копирование от внешнего.
"""

from PyQt5.QtCore import Qt, QPointF, QRectF, QByteArray, QBuffer, QIODevice, QMimeData
from PyQt5.QtGui import QPen, QColor, QFont, QPixmap
from PyQt5.QtWidgets import QApplication

from ..items import (RectangleItem, EllipseItem, FilledRectItem, CloudItem,
                     LineItem, WavyLineItem, ArrowItem, CurvedArrowItem,
                     DimensionItem, TextItem)
from ..items.pasted_image_item import PastedImageItem
from ..items.blur_region_item import BlurRegionItem
from ..history import PasteItemsCommand

# Кастомный MIME-тип для маркера внутреннего копирования
INTERNAL_MIME_TYPE = "application/x-screenshooter-internal"


class ClipboardController:
    """
    Управляет копированием и вставкой элементов в пределах приложения.
    Использует внутренний буфер (список сериализованных данных),
    а не системный буфер обмена.
    """

    PASTE_OFFSET = 20  # Смещение при вставке в пикселях
    _shared_clipboard = []
    _shared_paste_count = 0

    def __init__(self, view):
        """
        :param view: ссылка на EditorView (QGraphicsView)
        """
        self.view = view

    # --------------------------------------------------------------
    # Публичные методы
    # --------------------------------------------------------------
    def copy_selected(self):
        """Сериализует выделенные элементы во внутренний буфер."""
        items = [it for it in self.view.scene().selectedItems()
                 if not self.view._is_background_item(it)]
        if not items:
            return False

        ClipboardController._shared_clipboard = []
        ClipboardController._shared_paste_count = 0

        for item in items:
            data = self._serialize_item(item)
            if data:
                ClipboardController._shared_clipboard.append(data)

        if ClipboardController._shared_clipboard:
            # Помечаем системный буфер нашим маркером
            mime = QMimeData()
            mime.setData(INTERNAL_MIME_TYPE, b"1")
            QApplication.clipboard().setMimeData(mime)

            self.view.show_status_message(
                f"Скопировано элементов: {len(ClipboardController._shared_clipboard)}", 3000)
            return True
        return False

    def cut_selected(self):
        """Копирует выделенные элементы и удаляет их."""
        copied = self.copy_selected()
        if copied:
            self.view.delete_selected()
        return copied

    def paste(self):
        """Создаёт элементы из внутреннего буфера со смещением."""
        if not ClipboardController._shared_clipboard:
            return

        self.view.scene().clearSelection()
        new_items = []
        ClipboardController._shared_paste_count += 1
        offset = QPointF(self.PASTE_OFFSET * ClipboardController._shared_paste_count,
                         self.PASTE_OFFSET * ClipboardController._shared_paste_count)
        blur_added = False

        for data in ClipboardController._shared_clipboard:
            item = self._deserialize_item(data, offset)
            if item is not None:
                new_items.append(item)
                if isinstance(item, BlurRegionItem):
                    blur_added = True

        if not new_items:
            return

        # Выделяем вставленные элементы (кроме зон размытия)
        for item in new_items:
            item.setSelected(True)

        # Пересчитываем размытие, если были добавлены зоны
        if blur_added:
            self.view.blur_controller._invalidate_blur_cache()
            self.view.blur_controller._recompute_blurred_pixmap()

        # Добавляем в историю для Undo/Redo
        self.view.history.push(PasteItemsCommand(self.view.scene(), new_items))

        self.view._update_pasted_image_handles()
        self.view._invalidate_cursor_cache()
        self.view.viewport().update()

    @property
    def has_clipboard(self):
        """Есть ли данные в буфере."""
        return len(ClipboardController._shared_clipboard) > 0

    # --------------------------------------------------------------
    # Сериализация пера
    # --------------------------------------------------------------
    @staticmethod
    def _serialize_pen(pen):
        """Сериализует QPen в словарь."""
        color = pen.color()
        return {
            'color': [color.red(), color.green(), color.blue(), color.alpha()],
            'width': pen.widthF(),
            'style': int(pen.style()),
        }

    @staticmethod
    def _deserialize_pen(data):
        """Создаёт QPen из словаря."""
        color = QColor(*data['color'])
        pen = QPen(color, data['width'])
        pen.setStyle(Qt.PenStyle(data['style']))
        return pen

    # --------------------------------------------------------------
    # Сериализация элементов
    # --------------------------------------------------------------
    def _serialize_item(self, item):
        """Сериализует элемент в словарь. Возвращает None, если тип не поддерживается."""
        pos = item.pos()

        if isinstance(item, BlurRegionItem):
            rect = item.rect()
            return {
                'type': 'blur_region',
                'rect': [rect.x(), rect.y(), rect.width(), rect.height()],
            }

        if isinstance(item, PastedImageItem):
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QIODevice.WriteOnly)
            item.original_pixmap.save(buffer, 'PNG')
            buffer.close()
            return {
                'type': 'pasted_image',
                'pos': [pos.x(), pos.y()],
                'image_data': bytes(byte_array.data()),
                'scale': item.scale,
            }

        if isinstance(item, TextItem):
            font = item.font()
            text_color = item.defaultTextColor()
            bg = item.bg_color
            return {
                'type': 'text',
                'pos': [pos.x(), pos.y()],
                'text': item.toPlainText(),
                'font_family': font.family(),
                'font_size': font.pointSize(),
                'font_bold': font.bold(),
                'font_italic': font.italic(),
                'text_color': [text_color.red(), text_color.green(),
                               text_color.blue(), text_color.alpha()],
                'bg_color': ([bg.red(), bg.green(), bg.blue(), bg.alpha()]
                             if bg is not None else None),
            }

        if isinstance(item, RectangleItem):
            rect = item.rect()
            return {
                'type': 'rect',
                'pos': [pos.x(), pos.y()],
                'rect': [rect.x(), rect.y(), rect.width(), rect.height()],
                'pen': self._serialize_pen(item.pen()),
            }

        if isinstance(item, EllipseItem):
            rect = item.rect()
            return {
                'type': 'ellipse',
                'pos': [pos.x(), pos.y()],
                'rect': [rect.x(), rect.y(), rect.width(), rect.height()],
                'pen': self._serialize_pen(item.pen()),
            }

        if isinstance(item, FilledRectItem):
            rect = item.rect()
            brush_color = item.brush().color()
            return {
                'type': 'filled_rect',
                'pos': [pos.x(), pos.y()],
                'rect': [rect.x(), rect.y(), rect.width(), rect.height()],
                'color': [brush_color.red(), brush_color.green(), brush_color.blue()],
            }

        if isinstance(item, CloudItem):
            rect = item.rect()
            return {
                'type': 'cloud',
                'pos': [pos.x(), pos.y()],
                'rect': [rect.x(), rect.y(), rect.width(), rect.height()],
                'pen': self._serialize_pen(item._pen),
            }

        if isinstance(item, LineItem):
            line = item.line()
            return {
                'type': 'line',
                'pos': [pos.x(), pos.y()],
                'x1': line.x1(), 'y1': line.y1(),
                'x2': line.x2(), 'y2': line.y2(),
                'pen': self._serialize_pen(item.pen()),
            }

        if isinstance(item, WavyLineItem):
            return {
                'type': 'wavy_line',
                'pos': [pos.x(), pos.y()],
                'x1': item._x1, 'y1': item._y1,
                'x2': item._x2, 'y2': item._y2,
                'pen': self._serialize_pen(item._pen),
            }

        if isinstance(item, CurvedArrowItem):
            return {
                'type': 'curved_arrow',
                'pos': [pos.x(), pos.y()],
                'start': [item._start.x(), item._start.y()],
                'end': [item._end.x(), item._end.y()],
                'ctrl': [item._ctrl.x(), item._ctrl.y()],
                'pen': self._serialize_pen(item._pen),
            }

        if isinstance(item, ArrowItem):
            return {
                'type': 'arrow',
                'pos': [pos.x(), pos.y()],
                'start': [item._start.x(), item._start.y()],
                'end': [item._end.x(), item._end.y()],
                'pen': self._serialize_pen(item._pen),
            }

        if isinstance(item, DimensionItem):
            return {
                'type': 'dimension',
                'pos': [pos.x(), pos.y()],
                'start': [item._start.x(), item._start.y()],
                'end': [item._end.x(), item._end.y()],
                'pen': self._serialize_pen(item._pen),
            }

        return None

    # --------------------------------------------------------------
    # Десериализация элементов
    # --------------------------------------------------------------
    def _deserialize_item(self, data, offset):
        """Создаёт элемент из словаря. Возвращает None при ошибке."""
        item_type = data.get('type')
        scene = self.view.scene()
        try:
            if item_type == 'blur_region':
                rect = QRectF(*data['rect']).translated(offset)
                item = BlurRegionItem(rect, self.view, mode='inactive')
                scene.addItem(item)
                self.view.blur_controller.blur_regions.append(rect)
                self.view.blur_controller.blur_region_items.append(item)
                return item

            if item_type == 'pasted_image':
                pixmap = QPixmap()
                pixmap.loadFromData(data['image_data'])
                if pixmap.isNull():
                    return None
                item = PastedImageItem(pixmap, self.view)
                item.set_image_scale(data['scale'])
                item.setPos(QPointF(*data['pos']) + offset)
                scene.addItem(item)
                self.view.pasted_images.append(item)
                return item

            if item_type == 'text':
                bg = QColor(*data['bg_color']) if data['bg_color'] else None
                item = TextItem(self.view, bg_color=bg)
                item.setPlainText(data['text'])
                font = QFont(data['font_family'], data['font_size'])
                font.setBold(data['font_bold'])
                font.setItalic(data['font_italic'])
                item.setFont(font)
                item.setDefaultTextColor(QColor(*data['text_color']))
                item.setPos(QPointF(*data['pos']) + offset)
                scene.addItem(item)
                return item

            if item_type == 'rect':
                rect = QRectF(*data['rect'])
                pen = self._deserialize_pen(data['pen'])
                item = RectangleItem(rect, pen)
                item.setPos(QPointF(*data['pos']) + offset)
                scene.addItem(item)
                return item

            if item_type == 'ellipse':
                rect = QRectF(*data['rect'])
                pen = self._deserialize_pen(data['pen'])
                item = EllipseItem(rect, pen)
                item.setPos(QPointF(*data['pos']) + offset)
                scene.addItem(item)
                return item

            if item_type == 'filled_rect':
                rect = QRectF(*data['rect'])
                color = QColor(*data['color'])
                item = FilledRectItem(rect, color)
                item.setPos(QPointF(*data['pos']) + offset)
                scene.addItem(item)
                return item

            if item_type == 'cloud':
                rect = QRectF(*data['rect'])
                pen = self._deserialize_pen(data['pen'])
                item = CloudItem(rect, pen)
                item.setPos(QPointF(*data['pos']) + offset)
                scene.addItem(item)
                return item

            if item_type == 'line':
                pen = self._deserialize_pen(data['pen'])
                item = LineItem(data['x1'], data['y1'],
                                data['x2'], data['y2'], pen)
                item.setPos(QPointF(*data['pos']) + offset)
                scene.addItem(item)
                return item

            if item_type == 'wavy_line':
                pen = self._deserialize_pen(data['pen'])
                item = WavyLineItem(data['x1'], data['y1'],
                                    data['x2'], data['y2'], pen)
                item.setPos(QPointF(*data['pos']) + offset)
                scene.addItem(item)
                return item

            if item_type == 'curved_arrow':
                pen = self._deserialize_pen(data['pen'])
                item = CurvedArrowItem(
                    QPointF(*data['start']),
                    QPointF(*data['end']),
                    QPointF(*data['ctrl']), pen)
                item.setPos(QPointF(*data['pos']) + offset)
                scene.addItem(item)
                return item

            if item_type == 'arrow':
                pen = self._deserialize_pen(data['pen'])
                item = ArrowItem(
                    QPointF(*data['start']),
                    QPointF(*data['end']), pen)
                item.setPos(QPointF(*data['pos']) + offset)
                scene.addItem(item)
                return item

            if item_type == 'dimension':
                pen = self._deserialize_pen(data['pen'])
                item = DimensionItem(
                    QPointF(*data['start']),
                    QPointF(*data['end']), pen)
                item.setPos(QPointF(*data['pos']) + offset)
                scene.addItem(item)
                return item

        except Exception as e:
            print(f"Ошибка десериализации {item_type}: {e}")
            return None

        return None