"""
Модуль: export.py
Описание: Экспорт изображения из редактора.
          Рендеринг сцены, сохранение в файл, копирование в буфер обмена.
"""

import os
import time
from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QDir
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QFileDialog, QMenu, QApplication


class Exporter:
    """
    Управляет экспортом изображения:
    - рендеринг сцены в QImage
    - сохранение в файл
    - копирование в буфер обмена
    - быстрое сохранение в папку
    """

    def __init__(self, view, scene, settings=None):
        self.view = view
        self.scene = scene
        self.settings = settings

        # Если настройки не переданы, создаём локально (для обратной совместимости)
        if self.settings is None:
            from .settings import AppSettings
            self.settings = AppSettings()

        # Загружаем папку быстрого сохранения из настроек
        self.load_save_directory_from_settings()

    def render_scene_to_image(self):
        """Рендерит сцену в QImage без служебных элементов."""
        bg = self.view.background_item
        if bg is None or sip.isdeleted(bg):
            return None
        bg_pixmap = bg.pixmap()
        if bg_pixmap.isNull():
            return None

        # Скрываем служебные элементы перед рендером
        self.view.blur_controller.hide_blur_regions_for_render()
        self.view.hide_pasted_image_handles_for_render()

        target = bg_pixmap.rect()
        img = QImage(target.size(), QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        self.scene.render(p, QRectF(img.rect()), QRectF(target))
        p.end()

        # Возвращаем служебные элементы после рендера
        self.view.blur_controller.show_blur_regions_after_render()
        self.view.show_pasted_image_handles_after_render()
        return img

    def save_image(self):
        """Сохраняет изображение в файл через диалог выбора."""
        img = self.render_scene_to_image()
        if img is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            None, "Сохранить изображение", "",
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp)")
        if path:
            img.save(path)

    def copy_to_clipboard(self):
        """Копирует изображение в системный буфер обмена."""
        img = self.render_scene_to_image()
        if img is not None:
            QApplication.clipboard().setImage(img)

    def quick_save(self):
        """Быстрое сохранение в выбранную папку с именем по времени."""
        img = self.render_scene_to_image()
        if img is None:
            self.view.show_status_message("Нет изображения для сохранения.", 15000)
            return

        if not self.save_directory:
            if not self.choose_save_directory():
                return

        timestamp = time.strftime("%Y-%m-%d %H-%M-%S")
        filename = f"{timestamp}.png"
        full_path = os.path.join(self.save_directory, filename)

        if img.save(full_path, "PNG"):
            try:
                os.startfile(self.save_directory)
            except Exception:
                pass

            native_path = QDir.toNativeSeparators(full_path)
            self.view.show_status_message(native_path, 15000)
        else:
            self.view.show_status_message("Не удалось сохранить файл.", 15000)

    def choose_save_directory(self):
        """Открывает диалог выбора папки для быстрого сохранения."""
        directory = QFileDialog.getExistingDirectory(
            None,
            "Выберите папку для сохранения скриншотов",
            self.save_directory or os.path.expanduser("~")
        )
        if directory:
            self.save_directory = directory
            if self.settings:
                self.settings.set_save_directory(directory)
            return True
        return False

    def show_quick_save_menu(self, pos, button):
        """Показывает контекстное меню кнопки быстрого сохранения."""
        menu = QMenu()
        choose_action = menu.addAction("Выбрать папку...")
        chosen = menu.exec_(button.mapToGlobal(pos))
        if chosen == choose_action:
            self.choose_save_directory()

    def load_save_directory_from_settings(self):
        """Загружает папку быстрого сохранения из настроек."""
        if self.settings:
            self.save_directory = self.settings.save_directory
            if self.save_directory and not os.path.isdir(self.save_directory):
                self.save_directory = ""
        else:
            self.save_directory = ""