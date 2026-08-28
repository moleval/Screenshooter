"""
Модуль: controllers/pasted_image_controller.py
Описание: Контроллер вставленных изображений.
          Управляет добавлением, удалением, масштабированием вставленных изображений.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF

from ..items.pasted_image_item import PastedImageItem
from ..history import AddPastedImageCommand


class PastedImageController:
    """
    Управляет вставленными изображениями:
    добавление, удаление, масштабирование, позиционирование.
    """

    # --------------------------------------------------------------
    # Настройки автоматического масштабирования при вставке
    # --------------------------------------------------------------
    # Если картинка меньше этого процента подложки — оставляем оригинальный размер
    KEEP_ORIGINAL_THRESHOLD = 0.3   # 30% подложки

    # Целевой размер при уменьшении (в долях от подложки)
    SCALE_TARGET = 0.8              # Для маленьких подложек: уменьшаем до 80%
    LARGE_IMG_TARGET = 0.5          # Для больших подложек: уменьшаем до 50%

    # Порог большой подложки (в пикселях)
    LARGE_BG_PIXELS = 1920 * 1080   # Full HD (~2 Мп)

    # Минимальный размер картинки после масштабирования (в пикселях)
    MIN_SIZE_PX = 100               # Не меньше 100×100 пикселей

    def __init__(self, view):
        self.view = view
        self.pasted_images = []

    # --------------------------------------------------------------
    # Добавление изображения
    # --------------------------------------------------------------

    def add_image(self, pixmap):
        """Добавляет изображение на сцену с автоматическим масштабированием."""
        if pixmap.isNull():
            return None

        # Вычисляем масштаб относительно подложки (без изменения физического разрешения)
        scale = self._compute_auto_scale(pixmap)

        # Создаём элемент с оригинальным пиксмапом
        item = PastedImageItem(pixmap, self.view)
        self.view.scene().addItem(item)
        self.pasted_images.append(item)

        # Применяем визуальный масштаб (не меняем физическое разрешение)
        if scale != 1.0:
            item.set_image_scale(scale)

        # Позиционируем по центру подложки
        self._center_item_on_background(item)

        item.setSelected(True)
        item.show_handles()
        item.update_handles()

        self.view.history.push(AddPastedImageCommand(self.view.scene(), item, self.view))
        return item

    def _compute_auto_scale(self, pixmap):
        """Вычисляет масштаб изображения относительно подложки.

        Не меняет физическое разрешение — только возвращает коэффициент масштаба.

        Логика:
        1. Если картинка <= 30% подложки — масштаб 1.0 (оригинальный размер).
        2. Если картинка > 30% подложки:
           - Для больших подложек (Full HD+) — масштаб до 50% подложки.
           - Для маленьких подложек — масштаб до 80% подложки.
        """
        bg = self.view.image_editor.background_item
        if bg is None or sip.isdeleted(bg):
            return 1.0

        bg_pixmap = bg.pixmap()
        if bg_pixmap is None or bg_pixmap.isNull():
            return 1.0

        bg_size = bg_pixmap.size()
        img_size = pixmap.size()

        if bg_size.width() == 0 or bg_size.height() == 0:
            return 1.0

        # Коэффициент вписания картинки в подложку (по наибольшей стороне)
        scale_to_fit_w = bg_size.width() / img_size.width()
        scale_to_fit_h = bg_size.height() / img_size.height()
        scale_to_fit = min(scale_to_fit_w, scale_to_fit_h)

        # Если картинка <= 30% подложки — оставляем оригинальный размер
        # (картинка в 1/0.3 = 3.33 раза меньше подложки)
        if scale_to_fit >= 1.0 / self.KEEP_ORIGINAL_THRESHOLD:
            return 1.0

        # Картинка > 30% подложки — вычисляем масштаб для уменьшения
        bg_pixels = bg_size.width() * bg_size.height()
        is_large_bg = bg_pixels >= self.LARGE_BG_PIXELS

        if is_large_bg:
            # Большая подложка: уменьшаем до 50%
            target = self.LARGE_IMG_TARGET
        else:
            # Маленькая подложка: уменьшаем до 80%
            target = self.SCALE_TARGET

        # Масштаб относительно оригинального размера картинки
        scale_w = (target * bg_size.width()) / img_size.width()
        scale_h = (target * bg_size.height()) / img_size.height()
        scale = min(scale_w, scale_h)

        # Ограничиваем: не увеличиваем больше оригинала
        scale = min(scale, 1.0)

        return scale

    def _center_item_on_background(self, item):
        """Позиционирует элемент по центру подложки."""
        bg = self.view.image_editor.background_item
        if bg is None or sip.isdeleted(bg):
            return

        bg_rect = bg.mapRectToScene(QRectF(bg.pixmap().rect()))
        item_rect = item.mapRectToScene(item.boundingRect())

        dx = bg_rect.center().x() - item_rect.center().x()
        dy = bg_rect.center().y() - item_rect.center().y()
        item.setPos(item.pos() + QPointF(dx, dy))

    # --------------------------------------------------------------
    # Удаление изображения
    # --------------------------------------------------------------

    def remove_image(self, item):
        """Удаляет изображение со сцены."""
        if item in self.pasted_images:
            self.pasted_images.remove(item)
        item.hide_handles()
        if item.scene() is self.view.scene():
            self.view.scene().removeItem(item)

    def clear_all(self):
        """Удаляет все вставленные изображения."""
        for item in self.pasted_images[:]:
            self.remove_image(item)
        self.pasted_images.clear()

    # --------------------------------------------------------------
    # Обновление маркеров
    # --------------------------------------------------------------

    def update_handles(self):
        """Обновляет маркеры всех вставленных изображений."""
        for item in self.pasted_images:
            if item.isSelected() and not sip.isdeleted(item):
                item.show_handles()
                item.update_handles()
            else:
                item.hide_handles()

    def hide_handles_for_render(self):
        """Скрывает маркеры перед рендером."""
        for item in self.pasted_images:
            if not sip.isdeleted(item):
                item.hide_handles()

    def show_handles_after_render(self):
        """Показывает маркеры после рендера."""
        for item in self.pasted_images:
            if not sip.isdeleted(item) and item.isSelected():
                item.show_handles()
                item.update_handles()