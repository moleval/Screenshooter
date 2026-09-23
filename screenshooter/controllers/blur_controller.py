"""
Модуль: controllers/blur_controller.py
Описание: Контроллер размытия фонового изображения.
          Управляет режимом размытия, созданием/перемещением/изменением
          размеров зон размытия, а также пересчётом пиксмапа.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt5.QtGui import QPixmap, QImage, QPainter

from ..constants import MIN_RECT_SIZE
from ..items.blur_region_item import BlurRegionItem
from ..items.pasted_image_item import PastedImageItem
from ..image_processing import blur_region


class BlurController:
    """
    Управляет размытием фонового изображения:
    - режим размытия (вход/выход)
    - список зон размытия
    - активная зона размытия
    - адаптивный пересчёт с таймером
    - кэш неизменных зон
    """

    # Адаптивные настройки пересчёта
    PREVIEW_RADIUS = 4.0    # Радиус при перетаскивании (быстрый режим)
    FULL_RADIUS = 10.0      # Радиус при отпускании (полное качество)
    PREVIEW_SCALE = 4       # Уменьшение в 4 раза (быстрый режим)

    # ВРЕМЕННО: полное качество для всех разрешений (для проверки)
    FORCE_FULL_QUALITY = True

    def __init__(self, view):
        self.view = view

        # Состояние режима размытия
        self.blur_mode = False
        self.blur_interaction = None
        self.blur_temp_item = None
        self.blur_start_point = None
        self.blur_move_start = None
        self.blur_resize_handle = None
        self.blur_old_rect = None

        # Зоны размытия
        self.blur_base_pixmap = None
        self.blur_regions = []
        self.blur_region_items = []
        self.active_blur_index = None

        # Внешнее взаимодействие (вне режима blur_mode)
        self.blur_outside_mode = False
        self.blur_outside_interaction = None

        # Таймер троттлинга перерисовки
        self._blur_recompute_timer = QTimer()
        self._blur_recompute_timer.setInterval(16)  # ~60 fps
        self._blur_recompute_timer.timeout.connect(self._on_blur_timer)

        # Кэш для неизменных зон
        self._blur_cache_pixmap = None
        self._blur_cache_index = None
        self._pending_moving_index = None

    # ==============================================================
    # Сброс состояния
    # ==============================================================

    def reset_state(self):
        """Полный сброс: все зоны, режим, кэш."""
        self._clear_all_blur_regions()

    # ==============================================================
    # Вспомогательные
    # ==============================================================

    @staticmethod
    def _is_deleted(obj):
        return obj is None or sip.isdeleted(obj)

    def _scene_rect_to_pixmap_rect(self, rect):
        """Преобразует прямоугольник из координат сцены в координаты pixmap."""
        background_item = self.view.image_editor.background_item
        if background_item is None or self._is_deleted(background_item):
            return QRectF()
        return background_item.mapRectFromScene(QRectF(rect))

    # ==============================================================
    # Внутренние методы управления зонами
    # ==============================================================

    def _clear_all_blur_regions(self):
        for item in self.blur_region_items:
            # Проверяем, что элемент ещё в сцене, прежде чем удалять
            if not self._is_deleted(item) and item.scene() is not None:
                item.remove()
        for it in self.view.scene().items():
            if isinstance(it, BlurRegionItem):
                it.remove()
        self.blur_region_items.clear()
        self.blur_regions.clear()
        self.active_blur_index = None
        self.blur_interaction = None
        self.blur_temp_item = None
        self.blur_base_pixmap = None
        self.blur_outside_mode = False
        self.blur_outside_interaction = None
        self._blur_recompute_timer.stop()
        self._invalidate_blur_cache()

    def _clear_blur_regions(self):
        self._clear_all_blur_regions()

    def _get_blur_state(self):
        return {
            'rects': [QRectF(r) for r in self.blur_regions],
            'layers': [
                int(getattr(item, 'layer', 1))
                for item in self.blur_region_items
                if not self._is_deleted(item)
            ],
            'base_pixmap': self.blur_base_pixmap.copy() if self.blur_base_pixmap else None,
            'active_index': self.active_blur_index,
        }

    def _restore_blur_state(self, state):
        self._clear_all_blur_regions()
        self.blur_regions = [QRectF(r) for r in state.get('rects', [])]
        self.blur_base_pixmap = state.get('base_pixmap')
        self.active_blur_index = None
        self.blur_region_items = []

        layers = state.get('layers', [])
        for index, rect in enumerate(self.blur_regions):
            item = BlurRegionItem(rect, self.view, mode='inactive')
            if index < len(layers):
                item.set_layer(layers[index])
            self.view.scene().addItem(item)
            self.blur_region_items.append(item)
        for it in self.view.scene().items():
            if isinstance(it, BlurRegionItem) and it not in self.blur_region_items:
                it.remove()

    def _apply_crop_to_blur_regions(self, crop_rect: QRectF):
        """Обновляет зоны размытия после обрезки фона."""
        if self.blur_base_pixmap is not None:
            from ..image_processing import crop_pixmap_with_padding
            local_crop_rect = self._scene_rect_to_pixmap_rect(crop_rect)
            self.blur_base_pixmap = crop_pixmap_with_padding(
                self.blur_base_pixmap, local_crop_rect)

        new_regions = []
        for item in self.blur_region_items:
            if not self._is_deleted(item):
                item.remove()
        self.blur_region_items.clear()

        for rect in self.blur_regions:
            inter = rect.intersected(crop_rect)
            if not inter.isEmpty():
                inter.moveLeft(inter.left() - crop_rect.left())
                inter.moveTop(inter.top() - crop_rect.top())
                new_regions.append(inter)

        self.blur_regions = new_regions
        self.active_blur_index = None
        self._invalidate_blur_cache()

        for rect in self.blur_regions:
            item = BlurRegionItem(rect, self.view, mode='inactive')
            self.view.scene().addItem(item)
            self.blur_region_items.append(item)

        self._recompute_blurred_pixmap()

    def _add_blur_region_internal(self, rect):
        if self.blur_base_pixmap is None:
            self.blur_base_pixmap = self.view.image_editor.background_item.pixmap()
        self.blur_regions.append(rect)
        item = BlurRegionItem(rect, self.view, mode='active')
        self.view.scene().addItem(item)
        self.blur_region_items.append(item)
        self._invalidate_blur_cache()
        self._recompute_blurred_pixmap()
        self._set_active_blur(len(self.blur_regions) - 1)

    def _remove_last_blur_region(self):
        if self.blur_regions:
            self.blur_regions.pop()
            if self.blur_region_items:
                item = self.blur_region_items.pop()
                item.remove()
            for it in self.view.scene().items():
                if isinstance(it, BlurRegionItem) and it not in self.blur_region_items:
                    it.remove()
            self.active_blur_index = None
            self._invalidate_blur_cache()
            self._recompute_blurred_pixmap()

    def _remove_blur_region_at(self, index):
        if 0 <= index < len(self.blur_regions):
            rect = self.blur_regions.pop(index)
            item = self.blur_region_items.pop(index)
            # Проверяем, что элемент ещё в сцене, прежде чем удалять
            if not self._is_deleted(item) and item.scene() is not None:
                item.remove()
            if self.active_blur_index is not None:
                if self.active_blur_index == index:
                    self.active_blur_index = None
                elif self.active_blur_index > index:
                    self.active_blur_index -= 1
            for it in self.view.scene().items():
                if isinstance(it, BlurRegionItem) and it not in self.blur_region_items:
                    it.remove()
            self._invalidate_blur_cache()
            self._recompute_blurred_pixmap()
            return rect
        return None

    def _insert_blur_region_at(self, index, rect):
        self.blur_regions.insert(index, rect)
        item = BlurRegionItem(rect, self.view, mode='inactive')
        self.view.scene().addItem(item)
        self.blur_region_items.insert(index, item)
        self._invalidate_blur_cache()
        self._recompute_blurred_pixmap()

    def _update_blur_region_rect(self, index, rect):
        if 0 <= index < len(self.blur_regions):
            self.blur_regions[index] = rect
            item = self.blur_region_items[index]
            item.update_rect(rect)
            if self.active_blur_index == index and item.mode == 'active':
                if item.handles:
                    item.handles.update_handles(rect)
            self._recompute_blurred_pixmap()

    # ==============================================================
    # Адаптивные настройки пересчёта размытия
    # ==============================================================

    def _get_preview_settings(self):
        """Возвращает (радиус, масштаб) в зависимости от размера изображения."""
        if self.FORCE_FULL_QUALITY:
            return self.FULL_RADIUS, 1

        if self.blur_base_pixmap is None:
            return self.PREVIEW_RADIUS, self.PREVIEW_SCALE

        w = self.blur_base_pixmap.width()
        h = self.blur_base_pixmap.height()
        pixels = w * h

        if pixels <= 921600:
            return self.FULL_RADIUS, 1
        elif pixels <= 2073600:
            return 8.0, 2
        else:
            return 6.0, 2

    # ==============================================================
    # Пересчёт размытия
    # ==============================================================

    def _recompute_blurred_pixmap(self):
        """Полный пересчёт с нормальным радиусом (при отпускании)."""
        self._do_blur_recompute(radius=self.FULL_RADIUS, preview=False)

    def _recompute_blurred_pixmap_preview(self):
        """Быстрый пересчёт для перетаскивания (адаптивный)."""
        radius, scale = self._get_preview_settings()
        self._do_blur_recompute(radius=radius, preview=True, preview_scale=scale)

    def _render_blur_source(self, item):
        """Строит снимок только слоёв ниже данного blur.

        Здесь не используется QGraphicsScene.render(): при смешанном
        z-order он может дать некорректный результат для прозрачного
        временного изображения. Источник собирается явно: подложка +
        изображения/blur более низкого пользовательского слоя.
        """
        rect = item.sceneBoundingRect().normalized()
        width = max(1, int(round(rect.width())))
        height = max(1, int(round(rect.height())))

        image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        def draw_pixmap_in_scene_rect(pixmap, scene_rect):
            if pixmap is None or pixmap.isNull() or scene_rect.isEmpty():
                return
            target = QRectF(
                scene_rect.left() - rect.left(),
                scene_rect.top() - rect.top(),
                scene_rect.width(),
                scene_rect.height(),
            )
            painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))

        background = self.view.image_editor.background_item
        if background is not None and not self._is_deleted(background):
            bg_scene_rect = background.sceneBoundingRect().normalized()
            draw_pixmap_in_scene_rect(background.pixmap(), bg_scene_rect)

        current_layer = int(getattr(item, 'layer', 1))

        lower_items = []
        for scene_item in self.view.scene().items():
            if scene_item is item or not scene_item.isVisible():
                continue
            if scene_item is background:
                continue

            layer = getattr(scene_item, 'layer', None)
            if layer is None or int(layer) <= current_layer:
                continue

            if isinstance(scene_item, PastedImageItem):
                lower_items.append(scene_item)
            elif isinstance(scene_item, BlurRegionItem):
                lower_items.append(scene_item)

        # Сначала нижние пользовательские слои, затем объекты выше них
        # внутри источника. Для одинакового слоя сохраняем Qt-порядок.
        lower_items.sort(key=lambda it: it.zValue())

        for scene_item in lower_items:
            if isinstance(scene_item, PastedImageItem):
                draw_pixmap_in_scene_rect(
                    scene_item.pixmap(),
                    scene_item.sceneBoundingRect().normalized(),
                )
            elif isinstance(scene_item, BlurRegionItem):
                draw_pixmap_in_scene_rect(
                    scene_item.blurred_pixmap,
                    scene_item.sceneBoundingRect().normalized(),
                )

        painter.end()
        return QPixmap.fromImage(image)

    def _do_blur_recompute(self, radius=10.0, moving_index=None,
                           preview=False, preview_scale=None):
        background_item = self.view.image_editor.background_item
        if background_item is None or self._is_deleted(background_item):
            return

        if not self.blur_regions:
            if self.blur_base_pixmap is not None:
                background_item.prepareGeometryChange()
                background_item.setPixmap(self.blur_base_pixmap)
                background_item.update()
            self.view.viewport().update()
            return

        # Размытие является отдельным графическим слоем. Оно не меняет
        # пиксмап подложки: так оно может размывать изображения, находящиеся
        # на более низком пользовательском слое.
        background_item.prepareGeometryChange()
        if self.blur_base_pixmap is not None:
            background_item.setPixmap(self.blur_base_pixmap)
        background_item.update()

        items = [
            item for item in self.blur_region_items
            if not self._is_deleted(item) and item.scene() is self.view.scene()
        ]

        # Сначала нижние слои: верхний blur может использовать уже отрисованный
        # результат нижнего blur.
        items.sort(key=lambda it: it.zValue())

        for item in items:
            source = self._render_blur_source(item)
            if source.isNull():
                item.set_blurred_pixmap(QPixmap())
                continue

            if preview and preview_scale and preview_scale > 1:
                sw = max(1, source.width() // preview_scale)
                sh = max(1, source.height() // preview_scale)
                source = source.scaled(
                    sw, sh, Qt.IgnoreAspectRatio, Qt.FastTransformation)
                blurred = blur_region(
                    source,
                    QRectF(0, 0, source.width(), source.height()),
                    radius=radius,
                )
                blurred = blurred.scaled(
                    max(1, int(round(item.sceneBoundingRect().width()))),
                    max(1, int(round(item.sceneBoundingRect().height()))),
                    Qt.IgnoreAspectRatio,
                    Qt.FastTransformation,
                )
            else:
                blurred = blur_region(
                    source,
                    QRectF(0, 0, source.width(), source.height()),
                    radius=radius,
                )

            item.set_blurred_pixmap(blurred)

        # Аннотации могут временно перекрывать blur. После их ухода
        # существующий BlurRegionItem должен быть явно инвалидирован,
        # иначе Qt иногда оставляет старую dirty-region и новый blur
        # случайно "оживляет" старые зоны.
        scene = self.view.scene()
        for blur_item in items:
            if not self._is_deleted(blur_item):
                blur_item.update()
        try:
            scene.invalidate(scene.sceneRect())
        except (RuntimeError, AttributeError):
            pass
        scene.update()
        self.view.viewport().update()

    def _schedule_blur_recompute(self, moving_index=None):
        self._pending_moving_index = moving_index
        if not self._blur_recompute_timer.isActive():
            try:
                self._blur_recompute_timer.timeout.disconnect()
            except TypeError:
                pass
            self._blur_recompute_timer.timeout.connect(self._on_blur_timer)
            self._blur_recompute_timer.start()

    def _on_blur_timer(self):
        idx = getattr(self, '_pending_moving_index', None)
        radius, scale = self._get_preview_settings()
        self._do_blur_recompute(
            radius=radius, moving_index=idx, preview=True, preview_scale=scale)

    def _force_blur_recompute(self):
        self._blur_recompute_timer.stop()
        try:
            self._blur_recompute_timer.timeout.disconnect()
        except TypeError:
            pass
        self._pending_moving_index = None
        self._invalidate_blur_cache()
        self._do_blur_recompute(radius=self.FULL_RADIUS, preview=False)

    def _invalidate_blur_cache(self):
        self._blur_cache_pixmap = None
        self._blur_cache_index = None

    # ==============================================================
    # Активная зона размытия
    # ==============================================================

    def _set_active_blur(self, index):
        self._clear_active_blur()
        if 0 <= index < len(self.blur_region_items):
            item = self.blur_region_items[index]
            if not sip.isdeleted(item):
                item.set_mode('active')
                self.active_blur_index = index

    def _clear_active_blur(self):
        if self.active_blur_index is not None and self.active_blur_index < len(self.blur_region_items):
            item = self.blur_region_items[self.active_blur_index]
            if not sip.isdeleted(item):
                item.set_mode('inactive')
        self.active_blur_index = None

    def delete_active_blur_region(self):
        if self.active_blur_index is not None:
            from ..history import RemoveBlurRegionCommand
            command = RemoveBlurRegionCommand(self, self.active_blur_index)
            self.view.history.push(command)

    # ==============================================================
    # Скрытие зон для рендера
    # ==============================================================

    def hide_blur_regions_for_render(self):
        for item in self.blur_region_items:
            if not sip.isdeleted(item):
                item.setVisible(False)

    def show_blur_regions_after_render(self):
        for item in self.blur_region_items:
            if not sip.isdeleted(item):
                item.setVisible(True)

    # ==============================================================
    # Режим размытия
    # ==============================================================

    def start_blur_mode(self):
        if self.blur_mode:
            return
        self.view.image_editor.disable_crop_mode()
        self.view.set_tool(None)
        self.view.scene().clearSelection()
        self.blur_mode = True
        self.blur_interaction = None
        self.active_blur_index = None
        for item in self.blur_region_items:
            if not sip.isdeleted(item):
                item.set_mode('inactive')
        self.view.setCursor(Qt.CrossCursor)
        self.view.blur_mode_changed.emit(True)
        self.view._update_floating_widgets_visibility()

    def cancel_blur_mode(self):
        self.disable_blur_mode()

    def disable_blur_mode(self):
        self.blur_mode = False
        self._clear_active_blur()
        self.blur_interaction = None
        self.blur_temp_item = None
        self._blur_recompute_timer.stop()
        self.view.setCursor(Qt.CrossCursor)
        self.view.blur_mode_changed.emit(False)
        self.view._update_floating_widgets_visibility()

    def handle_blur_escape(self):
        if self.blur_interaction == 'drawing':
            if self.blur_temp_item:
                self.blur_temp_item.remove()
                self.blur_temp_item = None
            self.blur_interaction = None
            self.blur_start_point = None
            return
        if self.active_blur_index is not None:
            self._clear_active_blur()
            return
        self.disable_blur_mode()

    def apply_blur(self, rect: QRectF):
        background_item = self.view.image_editor.background_item
        if not background_item or rect.isEmpty():
            return

        # Зона blur может быть создана полностью или частично за пределами
        # текущей подложки. Сначала сохраняем её в координатах сцены, затем
        # после добавления расширяем подложку белым полем до фактической зоны.
        blur_rect = QRectF(rect).normalized()
        if blur_rect.width() < MIN_RECT_SIZE or blur_rect.height() < MIN_RECT_SIZE:
            return

        from ..history import AddBlurRegionCommand
        command = AddBlurRegionCommand(self, blur_rect)
        self.view.history.push(command)

        # _add_blur_region_internal уже создал BlurRegionItem, поэтому
        # expand_background_to_content увидит и сам blur и расширит canvas
        # влево/вправо/вверх/вниз без изменения координат объекта.
        self.view.expand_background_to_content(margin=0, threshold=1)
        self._force_blur_recompute()

    # ==============================================================
    # Обработчики мыши (в режиме blur_mode)
    # ==============================================================

    def handle_mouse_press(self, event) -> bool:
        if not self.blur_mode or event.button() != Qt.LeftButton:
            return False

        sp = self.view.mapToScene(event.pos())

        if self.active_blur_index is not None:
            item = self.blur_region_items[self.active_blur_index]
            handle_id = item.handles.hit_test(QPointF(event.pos()))
            if handle_id:
                self.blur_interaction = 'resizing'
                self.blur_resize_handle = handle_id
                self.blur_old_rect = QRectF(item.rect())
                if not item.isSelected():
                    self.view.scene().clearSelection()
                    item.setSelected(True)
                return True
            if item.rect().contains(sp):
                self.blur_interaction = 'moving'
                self.blur_move_start = sp
                self.blur_old_rect = QRectF(item.rect())
                self.view.prepare_drag_scene_rect(event.pos())
                if not item.isSelected():
                    self.view.scene().clearSelection()
                    item.setSelected(True)
                return True

        for idx, rect in enumerate(self.blur_regions):
            if idx == self.active_blur_index:
                continue
            if rect.contains(sp):
                self._set_active_blur(idx)
                self.blur_interaction = 'moving'
                self.blur_move_start = sp
                self.blur_old_rect = QRectF(rect)
                self.view.prepare_drag_scene_rect(event.pos())
                item = self.blur_region_items[idx]
                self.view.scene().clearSelection()
                item.setSelected(True)
                return True

        self._clear_active_blur()
        self.blur_interaction = 'drawing'
        self.blur_start_point = sp
        self.blur_temp_item = BlurRegionItem(QRectF(sp, sp), self.view, mode='drawing')
        self.view.scene().addItem(self.blur_temp_item)
        return True

    def handle_mouse_move(self, event) -> bool:
        if not self.blur_mode:
            return False

        sp = self.view.mapToScene(event.pos())

        if self.blur_interaction == 'resizing':
            self._auto_scroll_during_drag(event)
            if self.active_blur_index is not None:
                new_rect = self._apply_blur_resize(
                    self.active_blur_index, self.blur_resize_handle, sp)
                item = self.blur_region_items[self.active_blur_index]
                item.update_rect(new_rect)
                self.blur_regions[self.active_blur_index] = new_rect
                self._schedule_blur_recompute(moving_index=self.active_blur_index)
            return True

        if self.blur_interaction == 'moving':
            self._auto_scroll_during_drag(event)
            if self.active_blur_index is not None:
                item = self.blur_region_items[self.active_blur_index]
                delta = sp - self.blur_move_start

                if event.modifiers() & Qt.ShiftModifier:
                    if abs(delta.x()) > abs(delta.y()):
                        delta.setY(0.0)
                    else:
                        delta.setX(0.0)

                new_rect = self._constrain_move(self.blur_old_rect, delta)
                if not new_rect.isEmpty():
                    item.update_rect(new_rect)
                    self.blur_regions[self.active_blur_index] = new_rect
                    self._schedule_blur_recompute(moving_index=self.active_blur_index)
            return True

        if self.blur_interaction == 'drawing':
            if self.blur_temp_item:
                rect = QRectF(self.blur_start_point, sp).normalized()
                self.blur_temp_item.setRect(rect)
            return True

        if self.active_blur_index is not None:
            item = self.blur_region_items[self.active_blur_index]
            handle_id = item.handles.hit_test(QPointF(event.pos()))
            if handle_id:
                self.view.viewport().setCursor(
                    item.handles.get_cursor_for_handle(handle_id))
            elif item.rect().contains(sp):
                self.view.viewport().setCursor(Qt.SizeAllCursor)
            else:
                self.view.viewport().setCursor(Qt.CrossCursor)
        else:
            cursor_changed = False
            for item in self.blur_region_items:
                if item.rect().contains(sp):
                    self.view.viewport().setCursor(Qt.SizeAllCursor)
                    cursor_changed = True
                    break
            if not cursor_changed:
                self.view.viewport().setCursor(Qt.CrossCursor)
        return False

    def handle_mouse_release(self, event) -> bool:
        if not self.blur_mode or event.button() != Qt.LeftButton:
            return False

        if self.blur_interaction == 'resizing':
            if self.active_blur_index is not None:
                old_rect = self.blur_old_rect
                new_rect = self.blur_regions[self.active_blur_index]
                self._force_blur_recompute()
                if new_rect != old_rect:
                    from ..history import ResizeBlurRegionCommand
                    command = ResizeBlurRegionCommand(
                        self, self.active_blur_index, old_rect, new_rect)
                    self.view.history.push(command)
            self.blur_interaction = None
            self.blur_resize_handle = None
            self.blur_old_rect = None
            return True

        if self.blur_interaction == 'moving':
            if self.active_blur_index is not None:
                old_rect = self.blur_old_rect
                new_rect = self.blur_regions[self.active_blur_index]
                self._force_blur_recompute()
                if new_rect != old_rect:
                    from ..history import MoveBlurRegionCommand
                    command = MoveBlurRegionCommand(
                        self, self.active_blur_index, old_rect, new_rect)
                    self.view.history.push(command)
                    self.view.expand_background_to_content(margin=0, threshold=1)
                    self._force_blur_recompute()
            self.blur_interaction = None
            self.blur_move_start = None
            self.blur_old_rect = None
            return True

        if self.blur_interaction == 'drawing':
            sp = self.view.mapToScene(event.pos())
            rect = QRectF(self.blur_start_point, sp).normalized()
            if self.blur_temp_item:
                self.blur_temp_item.remove()
                self.blur_temp_item = None
            if rect.width() < MIN_RECT_SIZE or rect.height() < MIN_RECT_SIZE:
                self.blur_interaction = None
                self.blur_start_point = None
                return True
            self.blur_interaction = None
            self.blur_start_point = None
            self.apply_blur(rect)
            return True

        return False

    # ==============================================================
    # Обработка зон размытия ВНЕ режима blur_mode
    # ==============================================================

    def handle_blur_region_press_outside(self, event) -> bool:
        if event.button() != Qt.LeftButton:
            return False

        sp = self.view.mapToScene(event.pos())

        if self.active_blur_index is not None:
            item = self.blur_region_items[self.active_blur_index]
            handle_id = item.handles.hit_test(QPointF(event.pos()))
            if handle_id:
                # Ручки активного blur имеют приоритет над любым объектом.
                self.blur_outside_mode = True
                self.blur_outside_interaction = 'resizing'
                self.blur_resize_handle = handle_id
                self.blur_old_rect = QRectF(item.rect())
                if not item.isSelected():
                    self.view.scene().clearSelection()
                    item.setSelected(True)
                return True

            # Сам прямоугольник активного blur НЕ должен перехватывать клик,
            # если поверх него находится картинка/аннотация. В таком случае
            # выбор обязан идти по фактическому верхнему selectable-item.
            top_item = self.view._interactive_item_at(sp)
            if top_item is item and item.rect().contains(sp):
                self.blur_outside_mode = True
                self.blur_outside_interaction = 'moving'
                self.blur_move_start = sp
                self.blur_old_rect = QRectF(item.rect())
                self.view.prepare_drag_scene_rect(event.pos())
                if not item.isSelected():
                    self.view.scene().clearSelection()
                    item.setSelected(True)
                return True

        top_item = self.view._interactive_item_at(sp)
        if isinstance(top_item, BlurRegionItem):
            try:
                idx = self.blur_region_items.index(top_item)
            except ValueError:
                idx = None

            if idx is not None and idx != self.active_blur_index:
                rect = self.blur_regions[idx]
                if rect.contains(sp):
                    self._set_active_blur(idx)
                    self.blur_outside_mode = True
                    self.blur_outside_interaction = 'moving'
                    self.blur_move_start = sp
                    self.blur_old_rect = QRectF(rect)
                    self.view.prepare_drag_scene_rect(event.pos())
                    item = self.blur_region_items[idx]
                    self.view.scene().clearSelection()
                    item.setSelected(True)
                    return True

        self._clear_active_blur()
        return False

    def handle_blur_region_move_outside(self, event) -> bool:
        if not self.blur_outside_mode:
            sp = self.view.mapToScene(event.pos())
            if self.active_blur_index is not None:
                item = self.blur_region_items[self.active_blur_index]
                handle_id = item.handles.hit_test(QPointF(event.pos()))
                if handle_id:
                    self.view.viewport().setCursor(
                        item.handles.get_cursor_for_handle(handle_id))
                elif item.rect().contains(sp):
                    self.view.viewport().setCursor(Qt.SizeAllCursor)
            else:
                for item in self.blur_region_items:
                    if item.rect().contains(sp):
                        self.view.viewport().setCursor(Qt.SizeAllCursor)
                        break
            return False

        sp = self.view.mapToScene(event.pos())
        if self.blur_outside_interaction == 'resizing':
            self._auto_scroll_during_drag(event)
            if self.active_blur_index is not None:
                new_rect = self._apply_blur_resize(
                    self.active_blur_index, self.blur_resize_handle, sp)
                item = self.blur_region_items[self.active_blur_index]
                item.update_rect(new_rect)
                self.blur_regions[self.active_blur_index] = new_rect
                self._schedule_blur_recompute(moving_index=self.active_blur_index)
            return True
        elif self.blur_outside_interaction == 'moving':
            self._auto_scroll_during_drag(event)
            if self.active_blur_index is not None:
                item = self.blur_region_items[self.active_blur_index]
                delta = sp - self.blur_move_start

                if event.modifiers() & Qt.ShiftModifier:
                    if abs(delta.x()) > abs(delta.y()):
                        delta.setY(0.0)
                    else:
                        delta.setX(0.0)

                new_rect = self._constrain_move(self.blur_old_rect, delta)
                if not new_rect.isEmpty():
                    item.update_rect(new_rect)
                    self.blur_regions[self.active_blur_index] = new_rect
                    self._schedule_blur_recompute(moving_index=self.active_blur_index)
            return True

        return False

    def handle_blur_region_release_outside(self, event) -> bool:
        if event.button() != Qt.LeftButton or not self.blur_outside_mode:
            return False

        if self.blur_outside_interaction == 'resizing':
            if self.active_blur_index is not None:
                old_rect = self.blur_old_rect
                new_rect = self.blur_regions[self.active_blur_index]
                self._force_blur_recompute()
                if new_rect != old_rect:
                    from ..history import ResizeBlurRegionCommand
                    command = ResizeBlurRegionCommand(
                        self, self.active_blur_index, old_rect, new_rect)
                    self.view.history.push(command)
            self.blur_resize_handle = None
            self.blur_old_rect = None
        elif self.blur_outside_interaction == 'moving':
            if self.active_blur_index is not None:
                old_rect = self.blur_old_rect
                new_rect = self.blur_regions[self.active_blur_index]
                self._force_blur_recompute()
                if new_rect != old_rect:
                    from ..history import MoveBlurRegionCommand
                    command = MoveBlurRegionCommand(
                        self, self.active_blur_index, old_rect, new_rect)
                    self.view.history.push(command)
                    self.view.expand_background_to_content(margin=0, threshold=1)
                    self._force_blur_recompute()
            self.blur_move_start = None
            self.blur_old_rect = None

        self.blur_outside_mode = False
        self.blur_outside_interaction = None
        return True

    # ==============================================================
    # Вспомогательные
    # ==============================================================

    def _auto_scroll_during_drag(self, event):
        """Автопрокрутка расширенной sceneRect при перемещении blur."""
        edge = 24
        speed = 24
        viewport = self.view.viewport().rect()

        near_edge = (
            event.pos().x() <= viewport.left() + edge
            or event.pos().x() >= viewport.right() - edge
            or event.pos().y() <= viewport.top() + edge
            or event.pos().y() >= viewport.bottom() - edge
        )
        if not near_edge:
            return

        # Рабочее поле должно существовать до изменения scrollbar.
        self.view.prepare_drag_scene_rect(event.pos())

        hbar = self.view.horizontalScrollBar()
        vbar = self.view.verticalScrollBar()

        if event.pos().x() <= viewport.left() + edge:
            hbar.setValue(hbar.value() - speed)
        elif event.pos().x() >= viewport.right() - edge:
            hbar.setValue(hbar.value() + speed)

        if event.pos().y() <= viewport.top() + edge:
            vbar.setValue(vbar.value() - speed)
        elif event.pos().y() >= viewport.bottom() - edge:
            vbar.setValue(vbar.value() + speed)

    def _apply_blur_resize(self, index, handle_id, new_scene_pos):
        item = self.blur_region_items[index]
        rect = item.rect()
        left, top, right, bottom = rect.left(), rect.top(), rect.right(), rect.bottom()
        background_item = self.view.image_editor.background_item
        image_rect = background_item.mapRectToScene(
            QRectF(background_item.pixmap().rect()))
        min_size = MIN_RECT_SIZE

        x = max(image_rect.left(), min(image_rect.right(), new_scene_pos.x()))
        y = max(image_rect.top(), min(image_rect.bottom(), new_scene_pos.y()))

        if handle_id == 'tl':
            left = min(x, right - min_size)
            top = min(y, bottom - min_size)
        elif handle_id == 'tr':
            right = max(x, left + min_size)
            top = min(y, bottom - min_size)
        elif handle_id == 'bl':
            left = min(x, right - min_size)
            bottom = max(y, top + min_size)
        elif handle_id == 'br':
            right = max(x, left + min_size)
            bottom = max(y, top + min_size)
        elif handle_id == 'tm':
            top = min(y, bottom - min_size)
        elif handle_id == 'bm':
            bottom = max(y, top + min_size)
        elif handle_id == 'lm':
            left = min(x, right - min_size)
        elif handle_id == 'rm':
            right = max(x, left + min_size)

        return QRectF(left, top, right - left, bottom - top).normalized()

    def _constrain_move(self, old_rect: QRectF, delta: QPointF):
        # Blur, как и остальные редактируемые объекты, может свободно
        # выходить за пределы исходной подложки.
        return old_rect.translated(delta)