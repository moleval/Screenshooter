"""
Модуль: controllers/status_bar_manager.py
Описание: Управление статусной строкой редактора.
          Управляет текстом, стилем, видимостью и позиционированием.
"""

from PyQt5 import sip
from PyQt5.QtGui import QColor

from ..items.pasted_image_item import PastedImageItem
from ..theme import theme_manager


class StatusBarManager:
    """Управляет статусной строкой: текст, стиль, видимость, позиция."""

    def __init__(self, view):
        self.view = view

    # --------------------------------------------------------------
    # Доступ к status_label
    # --------------------------------------------------------------
    @property
    def _label(self):
        if hasattr(self.view, 'status_label') and self.view.status_label is not None:
            return self.view.status_label
        return None

    # --------------------------------------------------------------
    # Стили (формируются из активной темы)
    # --------------------------------------------------------------
    def _get_normal_style(self):
        bg = theme_manager.get_color('status_normal_bg')
        text = theme_manager.get_color('status_normal_text')
        return (
            f"background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {bg.alpha()}); "
            f"color: {text.name()}; "
            "border-radius: 6px; padding: 4px 8px;"
        )

    def _get_crop_style(self):
        bg = theme_manager.get_color('status_crop_bg')
        text = theme_manager.get_color('status_crop_text')
        return (
            f"background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {bg.alpha()}); "
            f"color: {text.name()}; "
            "font-size: 14px; font-weight: bold; "
            "border-radius: 4px; padding: 4px 8px;"
        )

    # --------------------------------------------------------------
    # Разрешение подложки
    # --------------------------------------------------------------
    def get_background_resolution(self):
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
            label.setStyleSheet(self._get_crop_style())
            self._update_position()
            label.raise_()
            label.update()
            label.repaint()

    def update_crop_status_text(self, text):
        label = self._label
        if label:
            label.setText(text)
            label.setVisible(True)
            label.setStyleSheet(self._get_crop_style())
            self._update_position()
            label.raise_()
            label.update()
            label.repaint()

    # --------------------------------------------------------------
    # Сброс статусной строки
    # --------------------------------------------------------------
    def reset_to_normal(self):
        label = self._label
        if label:
            label.setStyleSheet(self._get_normal_style())
            label.repaint()

    # --------------------------------------------------------------
    # Перерисовка
    # --------------------------------------------------------------
    def repaint(self):
        label = self._label
        if label:
            label.update()
            label.repaint()
            self.view.viewport().update()

    # --------------------------------------------------------------
    # Внутренние методы
    # --------------------------------------------------------------
    def _update_position(self):
        if hasattr(self.view, 'layout_manager'):
            self.view.layout_manager.update_status_label_position()

    @staticmethod
    def _is_deleted(obj):
        return obj is None or sip.isdeleted(obj)