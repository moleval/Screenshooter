"""
Модуль: controllers/status_bar_manager.py
Описание: Управление статусной строкой редактора.
"""

from PyQt5 import sip

from ..theme import theme_manager
from ..items.pasted_image_item import PastedImageItem


class StatusBarManager:
    def __init__(self, view):
        self.view = view

    @property
    def _label(self):
        if hasattr(self.view, 'status_label') and self.view.status_label is not None:
            return self.view.status_label
        return None

    def _crop_style(self):
        bg = theme_manager.get_color('status_crop_bg')
        text = theme_manager.get_color('status_crop_text')
        return (
            f"background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {bg.alpha()});"
            f" color: rgba({text.red()}, {text.green()}, {text.blue()}, {text.alpha()});"
            " font-size: 14px; font-weight: bold; border-radius: 4px; padding: 4px 8px;"
        )

    def _normal_style(self):
        bg = theme_manager.get_color('status_normal_bg')
        text = theme_manager.get_color('status_normal_text')
        return (
            f"background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {bg.alpha()});"
            f" color: rgba({text.red()}, {text.green()}, {text.blue()}, {text.alpha()});"
            " border-radius: 6px; padding: 4px 8px;"
        )

    def get_background_resolution(self):
        bg = self.view.background_item
        if bg is not None and not self._is_deleted(bg):
            pixmap = bg.pixmap()
            if not pixmap.isNull():
                return f"{pixmap.width()}×{pixmap.height()}"
        return "?"

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
            label.setStyleSheet(self._crop_style())
            self._update_position()
            label.raise_()
            label.update()
            label.repaint()

    def update_crop_status_text(self, text):
        label = self._label
        if label:
            label.setText(text)
            label.setVisible(True)
            label.setStyleSheet(self._crop_style())
            self._update_position()
            label.raise_()
            label.update()
            label.repaint()

    def reset_to_normal(self):
        label = self._label
        if label:
            label.setStyleSheet(self._normal_style())
            label.repaint()

    def repaint(self):
        label = self._label
        if label:
            label.update()
            label.repaint()
            self.view.viewport().update()

    def _update_position(self):
        if hasattr(self.view, 'layout_manager'):
            self.view.layout_manager.update_status_label_position()

    @staticmethod
    def _is_deleted(obj):
        return obj is None or sip.isdeleted(obj)