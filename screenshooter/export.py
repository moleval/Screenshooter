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
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PyQt5.QtWidgets import QFileDialog, QMenu, QApplication

from .adaptive_enhancer import EnhancerOptions, enhance_image


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

        # Все служебные элементы должны быть скрыты на время рендера.
        # Ручки аннотаций являются обычными QGraphicsItem, поэтому без
        # временного скрытия они физически попадают в экспортируемое изображение.
        # Контур выделения рисуется самим QGraphicsItem, поэтому одного
        # скрытия ручек недостаточно.
        selection_states = [
            (item, item.isSelected())
            for item in self.scene.selectedItems()
            if not sip.isdeleted(item)
        ]

        annotation_controller = getattr(
            self.view, "annotation_resize_controller", None
        )
        annotation_item = getattr(annotation_controller, "_item", None)
        if (
            annotation_item is not None
            and (
                sip.isdeleted(annotation_item)
                or annotation_item.scene() is not self.scene
            )
        ):
            annotation_item = None

        crop_overlay = getattr(
            getattr(self.view, "image_editor", None), "overlay", None)
        snap_guides = getattr(
            getattr(self.view, "manipulation_controller", None),
            "snap_guides", None,
        )

        self.view.blur_controller.hide_blur_regions_for_render()
        self.view.hide_pasted_image_handles_for_render()
        crop_states = crop_overlay.hide_for_render() if crop_overlay is not None else []
        if snap_guides is not None:
            snap_guides.clear_guides()
        if annotation_controller is not None:
            annotation_controller.remove_handles()

        # На время рендера убираем контуры выделения.
        self.scene.clearSelection()

        try:
            target = bg.sceneBoundingRect()
            target_rect = target.toAlignedRect()
            img = QImage(target_rect.size(), QImage.Format_ARGB32)
            img.fill(Qt.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            self.scene.render(p, QRectF(img.rect()), QRectF(target_rect))
            p.end()

            window = self.view.window()
            autocad_monochrome = (
                getattr(self.settings, "enhancer_color_mode", "auto") == "monochrome"
                and getattr(window, "_captured_window_is_autocad", False)
            )
            if (
                (getattr(self.settings, "enhancer_enabled", False) or autocad_monochrome)
                and not getattr(window, "_background_enhanced", False)
                and not getattr(window, "_captured_image_is_pdf", False)
            ):
                options = EnhancerOptions(
                    enabled=True,
                    scale=getattr(self.settings, "enhancer_scale", "auto"),
                    text=getattr(self.settings, "enhancer_text", True),
                    lines=getattr(self.settings, "enhancer_lines", True),
                    ui=getattr(self.settings, "enhancer_ui", True),
                    geometry=getattr(self.settings, "enhancer_geometry", True),
                    color_mode=getattr(
                        self.settings, "enhancer_color_mode", "auto"
                    ),
                )
                img = enhance_image(img, options)

            return img
        finally:
            # Восстанавливаем служебные элементы даже при ошибке рендера.
            self.view.blur_controller.show_blur_regions_after_render()
            self.view.show_pasted_image_handles_after_render()
            if crop_overlay is not None:
                crop_overlay.show_after_render(crop_states)
            # Сначала восстанавливаем исходное состояние выделения.
            self.scene.clearSelection()
            restored_annotation = False
            for item, selected in selection_states:
                try:
                    if selected and not sip.isdeleted(item) and item.scene() is self.scene:
                        item.setSelected(True)
                        restored_annotation = restored_annotation or item is annotation_item
                except RuntimeError:
                    pass

            if annotation_controller is not None:
                if annotation_item is not None and not restored_annotation:
                    try:
                        annotation_item.setSelected(True)
                    except RuntimeError:
                        annotation_item = None
                annotation_controller.sync_handles(force=True)

    def print_image(self):
        """Печатает текущий результат через стандартный диалог Windows/Qt."""
        img = self.render_scene_to_image()
        if img is None:
            self.view.show_status_message("Нет изображения для печати.", 5000)
            return False

        printer = QPrinter(QPrinter.HighResolution)
        if img.width() > img.height():
            printer.setOrientation(QPrinter.Landscape)
        else:
            printer.setOrientation(QPrinter.Portrait)

        dialog = QPrintDialog(printer, self.view)
        dialog.setWindowTitle("Печать")
        if dialog.exec_() != QPrintDialog.Accepted:
            return False

        page_rect = printer.pageRect(QPrinter.DevicePixel)
        if page_rect.isEmpty():
            return False

        scale = min(
            page_rect.width() / float(img.width()),
            page_rect.height() / float(img.height()),
        )
        target_width = img.width() * scale
        target_height = img.height() * scale
        target_x = page_rect.x() + (page_rect.width() - target_width) / 2.0
        target_y = page_rect.y() + (page_rect.height() - target_height) / 2.0

        painter = QPainter(printer)
        if not painter.isActive():
            return False
        try:
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.fillRect(page_rect, Qt.white)
            painter.drawImage(
                QRectF(target_x, target_y, target_width, target_height),
                img,
            )
        finally:
            painter.end()

        return True

    def save_image(self):
        """Сохраняет изображение в файл через диалог выбора."""
        img = self.render_scene_to_image()
        if img is None:
            return
        default_path = self.save_directory or os.path.expanduser("~")
        if os.path.isdir(default_path):
            default_path = os.path.join(default_path, "скриншот.png")
        path, _ = QFileDialog.getSaveFileName(
            None, "Сохранить изображение", default_path,
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

        try:
            os.makedirs(self.save_directory, exist_ok=True)
        except OSError:
            self.view.show_status_message(
                "Не удалось создать папку для сохранения.", 15000
            )
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
            # Сохраняем путь из настроек даже если папка временно отсутствует.
            # При быстром сохранении она будет создана автоматически.
            self.save_directory = self.settings.save_directory
        else:
            self.save_directory = ""