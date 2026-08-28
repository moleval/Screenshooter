"""
Модуль: controllers/status_bar_manager.py
Описание: Управление статусной строкой редактора.
          Управляет текстом, стилем, видимостью и позиционированием.
"""

from PyQt5 import sip

from ..constants import STATUS_STYLE_CROP, STATUS_STYLE_NORMAL
from ..items.pasted_image_item import PastedImageItem


class StatusBarManager:
    """Управляет статусной строкой: текст, стиль, видимость, позиция."""

    def __init__(self, view):
        self.view = view

    # --------------------------------------------------------------
    # Доступ к status_label
    # --------------------------------------------------------------
    @property
    def _label(self):
        """Возвращает status_label из view, или None если не существует."""
        if hasattr(self.view, 'status_label') and self.view.status_label is not None:
            return self.view.status_label
        return None

    # --------------------------------------------------------------
    # Разрешение подложки
    # --------------------------------------------------------------
    def get_background_resolution(self):
        """Возвращает разрешение подложки в формате 'WxH'."""
        bg = self.view.background_item
        if bg is not None and not self._is_deleted(bg):
            pixmap = bg.pixmap()
            if not pixmap.isNull():
                return f"{pixmap.width()}×{pixmap.height()}"
        return "?"

    # --------------------------------------------------------------
    # Установка статуса для режима обрезки
    # --------------------------------------------------------------
    def set_crop_status(self, crop_target_item):
        """Устанавливает статусную строку для режима обрезки.

        Для вставленных изображений: разрешение_подложки / разрешение_картинки.
        Для подложки: только разрешение подложки.

        Полный цикл: текст + стиль + видимость + позиция + перерисовка.
        """
        if isinstance(crop_target_item, PastedImageItem):
            bg_resolution = self.get_background_resolution()
            if hasattr(crop_target_item, 'original_pixmap') and crop_target_item.original_pixmap is not None:
                pixmap = crop_target_item.original_pixmap
                img_resolution = f"{pixmap.width()}×{pixmap.height()}"
            else:
                img_resolution = "?"
            text = f"{bg_resolution} / {img_resolution}"
        else:
            text = self.get_background_resolution()

        label = self._label
        if label:
            label.setText(text)
            label.setVisible(True)
            label.setStyleSheet(STATUS_STYLE_CROP)
            self._update_position()
            label.raise_()
            label.update()
            label.repaint()

    def update_crop_status_text(self, text):
        """Обновляет текст статусной строки в режиме обрезки.

        Используется при изменении размера рамки обрезки.
        """
        label = self._label
        if label:
            label.setText(text)
            label.setVisible(True)
            label.setStyleSheet(STATUS_STYLE_CROP)
            self._update_position()
            label.raise_()
            label.update()
            label.repaint()

    # --------------------------------------------------------------
    # Сброс статусной строки
    # --------------------------------------------------------------
    def reset_to_normal(self):
        """Возвращает статусную строку в обычное состояние."""
        label = self._label
        if label:
            label.setStyleSheet(STATUS_STYLE_NORMAL)
            label.repaint()

    # --------------------------------------------------------------
    # Перерисовка
    # --------------------------------------------------------------
    def repaint(self):
        """Принудительно перерисовывает статусную строку."""
        label = self._label
        if label:
            label.update()
            label.repaint()
            self.view.viewport().update()

    # --------------------------------------------------------------
    # Внутренние методы
    # --------------------------------------------------------------
    def _update_position(self):
        """Обновляет позицию статусной строки."""
        if hasattr(self.view, 'layout_manager'):
            self.view.layout_manager.update_status_label_position()

    @staticmethod
    def _is_deleted(obj):
        return obj is None or sip.isdeleted(obj)