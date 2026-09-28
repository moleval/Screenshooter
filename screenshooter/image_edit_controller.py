"""
Модуль: image_edit_controller.py
Описание: Контроллер операций редактирования фонового изображения.
          Управляет режимами обрезки и поворота.
          Размытие вынесено в BlurController.
"""

from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer
import math
from PyQt5.QtGui import QImage, QPainter, QPixmap
from PyQt5.QtWidgets import QGraphicsRectItem

from .constants import MIN_RECT_SIZE
from .theme import theme_manager
from .controllers.crop_cursor_factory import CropCursorFactory
from .controllers.crop_overlay_controller import CropOverlayController
from .controllers.status_bar_manager import StatusBarManager
from .history import (CropCommand, RotateCommand,
                      CropPastedImageCommand, RotatePastedImageCommand)
from .image_processing import (crop_pixmap, crop_pixmap_with_padding,
                                      rotate_pixmap, trim_white_border)
from .items.pasted_image_item import PastedImageItem
from .items.blur_region_item import BlurRegionItem


class ImageEditController:
    """
    Управляет операциями с фоновым изображением (crop, rotate).
    Также поддерживает операции с вставленными изображениями.
    Размытие вынесено в BlurController.
    """

    ASPECT_RATIOS = (
        (1, 1), (4, 5), (5, 4), (3, 4), (4, 3),
        (2, 3), (3, 2), (10, 16), (16, 10), (9, 16),
        (16, 9), (9, 21), (21, 9), (1, 2), (2, 1),
        (1, 3), (3, 1),
    )
    ASPECT_SNAP_DISTANCE_PX = 8.0
    ASPECT_RELEASE_DISTANCE_PX = 18.0
    ASPECT_VISIBLE_CANDIDATES = 3
    ASPECT_SOFT_SNAP_STRENGTH = 0.65

    def __init__(self, view):
        self.view = view

        self.background_item = None
        self.crop_target_item = None
        self.crop_mode = False
        self.crop_rect = None
        self.temp_crop_start = None
        self.active_handle = None
        self.active_aspect_ratio = None
        self.aspect_drag_candidates = []
        self.aspect_drag_caught_ratio = None
        self.aspect_drag_used_ratios = set()
        self.aspect_drag_handle = None
        self.aspect_drag_last_mouse = None
        self.aspect_drag_skip_snap = False

        # Менеджер статусной строки
        self.status_bar_manager = StatusBarManager(self.view)

        # Контроллер визуальных элементов обрезки
        self.overlay = CropOverlayController(self.view, self.status_bar_manager)

    # --------------------------------------------------------------
    # Установка фонового элемента и сброс
    # --------------------------------------------------------------
    def set_background_item(self, item):
        self.background_item = item
        self.crop_target_item = item
        self.reset_state()

    def reset_state(self):
        self.crop_mode = False
        self.overlay.clear()
        self.overlay.remove_handles()
        self.crop_rect = None
        self.temp_crop_start = None
        self.active_handle = None
        self.active_aspect_ratio = None
        self.aspect_drag_candidates = []
        self.aspect_drag_caught_ratio = None
        self.aspect_drag_used_ratios = set()
        self.aspect_drag_handle = None
        self.aspect_drag_last_mouse = None
        self.aspect_drag_skip_snap = False

        # Сброс размытия делегирован в blur_controller
        self.view.blur_controller.reset_state()

        self.view.setBackgroundBrush(self.view.normal_background_color)
        self.view.crop_mode_changed.emit(False)
        self.view.blur_mode_changed.emit(False)
        self.view._update_floating_widgets_visibility()

    @staticmethod
    def _is_deleted(obj):
        return obj is None or sip.isdeleted(obj)

    # --------------------------------------------------------------
    # Ограничение точки пределами целевого изображения
    # --------------------------------------------------------------
    def _clamp_to_target(self, scene_pos):
        """Ограничивает точку только для вставленного изображения."""
        if self.crop_target_item is None:
            return scene_pos
        if self.crop_target_item is self.background_item:
            return scene_pos
        pixmap = self.crop_target_item.pixmap()
        image_rect = self.crop_target_item.mapRectToScene(
            QRectF(0, 0, pixmap.width(), pixmap.height()))
        x = max(image_rect.left(), min(image_rect.right(), scene_pos.x()))
        y = max(image_rect.top(), min(image_rect.bottom(), scene_pos.y()))
        return QPointF(x, y)

    # --------------------------------------------------------------
    # Режим обрезки
    # --------------------------------------------------------------
    def start_crop_mode(self):
        if self.crop_mode:
            return

        self.view.blur_controller.disable_blur_mode()
        self.view.set_tool(None)

        self.crop_mode = True
        self.temp_crop_start = None
        self.active_handle = None

        self.view.setCursor(CropCursorFactory.get_cursor())
        self.view.setBackgroundBrush(theme_manager.get_color('crop_bg'))

        if self.crop_target_item is None:
            self.crop_target_item = self.background_item

        if self.crop_target_item:
            self.crop_rect = self.crop_target_item.mapRectToScene(
                QRectF(self.crop_target_item.pixmap().rect()))
            if self.crop_target_item is self.background_item:
                self.view.set_scene_rect_preserving_view(
                    self.crop_rect.adjusted(-5000, -5000, 5000, 5000))
        else:
            self.crop_rect = self.view.sceneRect()

        self.overlay.clear()
        self.overlay.create_handles(self.crop_rect)
        self._begin_aspect_drag("br", self.crop_rect.bottomRight())
        self.overlay.update(
            self.crop_rect,
            self.active_aspect_ratio,
            self.aspect_drag_candidates,
            None,
        )
        self.overlay.update_resolution_text(self.crop_rect, self.crop_target_item)

        self.view.crop_mode_changed.emit(True)
        self.view._update_floating_widgets_visibility()

        QTimer.singleShot(
            0,
            lambda: self.status_bar_manager.set_crop_status(self.crop_target_item)
        )

    def cancel_crop_mode(self):
        self.disable_crop_mode()

    def disable_crop_mode(self):
        self.crop_mode = False
        self.overlay.clear()
        self.overlay.remove_handles()
        self.crop_rect = None
        self.temp_crop_start = None
        self.active_handle = None
        self.active_aspect_ratio = None
        self.aspect_drag_candidates = []
        self.aspect_drag_caught_ratio = None
        self.aspect_drag_used_ratios = set()
        self.aspect_drag_handle = None
        self.aspect_drag_last_mouse = None
        self.aspect_drag_skip_snap = False

        self.view.setCursor(Qt.CrossCursor)
        self.view.setBackgroundBrush(self.view.normal_background_color)
        if self.background_item is not None and not self._is_deleted(self.background_item):
            self.view.set_scene_rect_preserving_view(
                self.background_item.sceneBoundingRect())
        self.view.crop_mode_changed.emit(False)
        self.view._update_floating_widgets_visibility()
        self.crop_target_item = None

        self.view.update_resolution_from_background()
        self.status_bar_manager.reset_to_normal()

    def _apply_handle_drag(self, handle_id, new_scene_pos):
        rect = self.crop_rect.normalized()
        left, top, right, bottom = (
            rect.left(),
            rect.top(),
            rect.right(),
            rect.bottom(),
        )
        image_rect = self.crop_target_item.mapRectToScene(
            QRectF(
                0,
                0,
                self.crop_target_item.pixmap().width(),
                self.crop_target_item.pixmap().height(),
            )
        ).normalized()

        if self.crop_target_item is self.background_item:
            x = new_scene_pos.x()
            y = new_scene_pos.y()
        else:
            x = max(image_rect.left(), min(image_rect.right(), new_scene_pos.x()))
            y = max(image_rect.top(), min(image_rect.bottom(), new_scene_pos.y()))

        if handle_id == "tl":
            left = min(x, right - MIN_RECT_SIZE)
            top = min(y, bottom - MIN_RECT_SIZE)
        elif handle_id == "tr":
            right = max(x, left + MIN_RECT_SIZE)
            top = min(y, bottom - MIN_RECT_SIZE)
        elif handle_id == "bl":
            left = min(x, right - MIN_RECT_SIZE)
            bottom = max(y, top + MIN_RECT_SIZE)
        elif handle_id == "br":
            right = max(x, left + MIN_RECT_SIZE)
            bottom = max(y, top + MIN_RECT_SIZE)
        elif handle_id == "tm":
            top = min(y, bottom - MIN_RECT_SIZE)
        elif handle_id == "bm":
            bottom = max(y, top + MIN_RECT_SIZE)
        elif handle_id == "lm":
            left = min(x, right - MIN_RECT_SIZE)
        elif handle_id == "rm":
            right = max(x, left + MIN_RECT_SIZE)

        raw_rect = QRectF(
            left, top, right - left, bottom - top
        ).normalized()

        snapped = self._apply_aspect_candidate_snap(
            raw_rect, handle_id, new_scene_pos
        )
        if snapped is not None:
            self.active_aspect_ratio = snapped["ratio"]
            return snapped["rect"]

        self.active_aspect_ratio = None
        return raw_rect

    @staticmethod
    def _ratio_error(current, target):
        return abs(current - target) / target

    def _ratio_rect(self, rect, handle_id, ratio):
        rect = QRectF(rect).normalized()
        left, top = rect.left(), rect.top()
        right, bottom = rect.right(), rect.bottom()
        width, height = rect.width(), rect.height()

        if handle_id in ("tm", "bm"):
            height = width / ratio
            if handle_id == "tm":
                top = bottom - height
            else:
                bottom = top + height
        elif handle_id in ("lm", "rm"):
            width = height * ratio
            if handle_id == "lm":
                left = right - width
            else:
                right = left + width
        else:
            anchor_y = bottom if handle_id in ("tl", "tr") else top
            anchor_x = right if handle_id in ("tl", "bl") else left

            if width >= height * ratio:
                height = width / ratio
            else:
                width = height * ratio

            if handle_id in ("tl", "tr"):
                top = anchor_y - height
            else:
                bottom = anchor_y + height
            if handle_id in ("tl", "bl"):
                left = anchor_x - width
            else:
                right = anchor_x + width

        return QRectF(left, top, right - left, bottom - top).normalized()

    @staticmethod
    def _handle_point(rect, handle_id):
        points = {
            "tl": rect.topLeft(),
            "tr": rect.topRight(),
            "bl": rect.bottomLeft(),
            "br": rect.bottomRight(),
            "tm": QPointF(rect.center().x(), rect.top()),
            "bm": QPointF(rect.center().x(), rect.bottom()),
            "lm": QPointF(rect.left(), rect.center().y()),
            "rm": QPointF(rect.right(), rect.center().y()),
        }
        return points.get(handle_id)

    def _aspect_target_bounds(self):
        if self.crop_target_item is None:
            return None
        if self.crop_target_item is self.background_item:
            return None

        pixmap = self.crop_target_item.pixmap()
        return self.crop_target_item.mapRectToScene(
            QRectF(0, 0, pixmap.width(), pixmap.height())
        ).normalized()

    def _candidate_rect_for_ratio(
        self, rect, handle_id, ratio, mouse_pos, scale=1.0
    ):
        """Вычисляет цель соотношения для ручки с заданным удалением от якоря."""
        rect = QRectF(rect).normalized()
        ratio = float(ratio)
        if ratio <= 0 or scale <= 0:
            return None

        bounds = self._aspect_target_bounds()

        if handle_id in ("tl", "tr", "bl", "br"):
            anchors = {
                "tl": (rect.right(), rect.bottom(), -1, -1),
                "tr": (rect.left(), rect.bottom(), 1, -1),
                "bl": (rect.right(), rect.top(), -1, 1),
                "br": (rect.left(), rect.top(), 1, 1),
            }
            ax, ay, sx, sy = anchors[handle_id]
            dx = mouse_pos.x() - ax
            dy = mouse_pos.y() - ay
            inv_ratio = 1.0 / ratio
            width = (
                sx * dx + sy * dy * inv_ratio
            ) / (1.0 + inv_ratio * inv_ratio)
            width = max(width * scale, float(MIN_RECT_SIZE))

            if bounds is not None:
                max_w_x = (
                    bounds.right() - ax if sx > 0 else ax - bounds.left()
                )
                max_h = (
                    bounds.bottom() - ay if sy > 0 else ay - bounds.top()
                )
                max_w = min(max_w_x, max_h * ratio)
                if max_w < MIN_RECT_SIZE:
                    return None
                width = min(width, max_w)

            height = width / ratio
            if bounds is not None:
                if height < MIN_RECT_SIZE:
                    return None
                max_w_x = (
                    bounds.right() - ax if sx > 0 else ax - bounds.left()
                )
                max_h = (
                    bounds.bottom() - ay if sy > 0 else ay - bounds.top()
                )
                if width > max_w_x + 1e-6 or height > max_h + 1e-6:
                    return None

            x = ax + sx * width
            y = ay + sy * height
            return QRectF(
                min(ax, x),
                min(ay, y),
                abs(x - ax),
                abs(y - ay),
            ).normalized()

        if handle_id in ("tm", "bm"):
            width = rect.width() * scale
            height = width / ratio
            anchor_y = rect.bottom() if handle_id == "tm" else rect.top()
            top = anchor_y - height if handle_id == "tm" else anchor_y
            candidate = QRectF(
                rect.left(), top, width, height
            ).normalized()
        elif handle_id in ("lm", "rm"):
            height = rect.height() * scale
            width = height * ratio
            anchor_x = rect.right() if handle_id == "lm" else rect.left()
            left = anchor_x - width if handle_id == "lm" else anchor_x
            candidate = QRectF(
                left, rect.top(), width, height
            ).normalized()
        else:
            return None

        if bounds is not None and not bounds.contains(candidate):
            return None
        if candidate.width() < MIN_RECT_SIZE or candidate.height() < MIN_RECT_SIZE:
            return None
        return candidate

    def _build_aspect_drag_candidates(
        self, rect, handle_id, mouse_pos, forward_scale=1.0
    ):
        """Строит цели соотношений, разнесённые вдоль направления ручки."""
        candidates = []
        for ratio_pair in self.ASPECT_RATIOS:
            ratio = ratio_pair[0] / ratio_pair[1]
            candidate_rect = self._candidate_rect_for_ratio(
                rect, handle_id, ratio, mouse_pos, forward_scale
            )
            if candidate_rect is None:
                continue

            handle_point = self._handle_point(candidate_rect, handle_id)
            if handle_point is None:
                continue

            current_point = self._handle_point(rect, handle_id)
            if (
                current_point is not None
                and math.hypot(
                    handle_point.x() - current_point.x(),
                    handle_point.y() - current_point.y(),
                ) < 0.5
            ):
                continue

            distance = math.hypot(
                handle_point.x() - mouse_pos.x(),
                handle_point.y() - mouse_pos.y(),
            )
            candidates.append({
                "ratio": ratio_pair,
                "label": f"{ratio_pair[0]}:{ratio_pair[1]}",
                "rect": candidate_rect,
                "handle_point": handle_point,
                "distance": distance,
            })

        candidates.sort(key=lambda item: item["distance"])
        visible = candidates[:self.ASPECT_VISIBLE_CANDIDATES]

        # Разносим видимые цели по траектории: каждая следующая цель
        # находится дальше от неподвижного якоря, поэтому рамки не сливаются.
        spaced = []
        scales = (0.78, 1.0, 1.24)
        for index, candidate in enumerate(visible):
            scale = scales[min(index, len(scales) - 1)]
            spaced_rect = self._candidate_rect_for_ratio(
                rect,
                handle_id,
                candidate["ratio"][0] / candidate["ratio"][1],
                mouse_pos,
                forward_scale * scale,
            )
            if spaced_rect is None:
                spaced_rect = candidate["rect"]
            candidate = dict(candidate)
            candidate["rect"] = spaced_rect
            candidate["handle_point"] = self._handle_point(
                spaced_rect, handle_id
            )
            candidate["distance"] = self._distance_to_candidate(
                candidate, mouse_pos
            )
            spaced.append(candidate)

        spaced.sort(key=lambda item: item["distance"])
        return spaced

    def _begin_aspect_drag(self, handle_id, mouse_pos):
        """Фиксирует стартовый набор целей и очищает прошлое состояние."""
        self.aspect_drag_handle = handle_id
        self.aspect_drag_caught_ratio = None
        self.aspect_drag_used_ratios = set()
        self.aspect_drag_last_mouse = QPointF(mouse_pos)
        self.aspect_drag_candidates = self._build_aspect_drag_candidates(
            self.crop_rect, handle_id, mouse_pos
        )
        self.aspect_drag_skip_snap = False

    def _distance_to_candidate(self, candidate, mouse_pos):
        """Возвращает расстояние от курсора до ручки цели в координатах сцены."""
        point = candidate["handle_point"]
        return math.hypot(
            point.x() - mouse_pos.x(),
            point.y() - mouse_pos.y(),
        )

    def _rect_with_handle_point(self, rect, handle_id, point):
        """Возвращает рамку с перемещённой ручкой и фиксированным якорем."""
        rect = QRectF(rect).normalized()
        left, top, right, bottom = (
            rect.left(), rect.top(), rect.right(), rect.bottom()
        )

        if handle_id == "tl":
            left, top = point.x(), point.y()
        elif handle_id == "tr":
            right, top = point.x(), point.y()
        elif handle_id == "bl":
            left, bottom = point.x(), point.y()
        elif handle_id == "br":
            right, bottom = point.x(), point.y()
        elif handle_id == "tm":
            top = point.y()
        elif handle_id == "bm":
            bottom = point.y()
        elif handle_id == "lm":
            left = point.x()
        elif handle_id == "rm":
            right = point.x()

        return QRectF(left, top, right - left, bottom - top).normalized()

    def _consume_caught_aspect_candidate(self, mouse_pos, rect):
        caught = None
        for candidate in self.aspect_drag_candidates:
            if tuple(candidate["ratio"]) == tuple(self.aspect_drag_caught_ratio or ()):
                caught = candidate
                break
        if caught is None:
            return

        self.aspect_drag_candidates = [
            item for item in self.aspect_drag_candidates if item is not caught
        ]
        self.aspect_drag_used_ratios.add(tuple(caught["ratio"]))
        self.aspect_drag_caught_ratio = None
        self.aspect_drag_skip_snap = True

        replacements = self._build_aspect_drag_candidates(
            rect, self.aspect_drag_handle, mouse_pos, forward_scale=1.35
        )
        for candidate in replacements:
            if (
                tuple(candidate["ratio"]) not in self.aspect_drag_used_ratios
                and candidate["ratio"] not in {
                    tuple(item["ratio"])
                    for item in self.aspect_drag_candidates
                }
            ):
                self.aspect_drag_candidates.append(candidate)
                break

        self.aspect_drag_candidates.sort(
            key=lambda item: self._distance_to_candidate(item, mouse_pos)
        )
        self.aspect_drag_candidates = self.aspect_drag_candidates[
            :self.ASPECT_VISIBLE_CANDIDATES
        ]

    def _apply_aspect_candidate_snap(self, raw_rect, handle_id, mouse_pos):
        """Возвращает мягко притянутую цель или None."""
        if self.aspect_drag_handle != handle_id:
            return None
        if not self.aspect_drag_candidates:
            return None

        last_mouse = self.aspect_drag_last_mouse or QPointF(mouse_pos)

        if self.aspect_drag_skip_snap:
            self.aspect_drag_skip_snap = False
            self.aspect_drag_last_mouse = QPointF(mouse_pos)
            return None

        if self.aspect_drag_caught_ratio is not None:
            caught = next(
                (
                    item
                    for item in self.aspect_drag_candidates
                    if tuple(item["ratio"])
                    == tuple(self.aspect_drag_caught_ratio)
                ),
                None,
            )
            if caught is not None:
                distance = self._distance_to_candidate(caught, mouse_pos)
                movement = QPointF(
                    mouse_pos.x() - last_mouse.x(),
                    mouse_pos.y() - last_mouse.y(),
                )
                away = QPointF(
                    mouse_pos.x() - caught["handle_point"].x(),
                    mouse_pos.y() - caught["handle_point"].y(),
                )
                if (
                    distance > self.ASPECT_RELEASE_DISTANCE_PX
                    and movement.x() * away.x()
                    + movement.y() * away.y() > 0
                ):
                    self._consume_caught_aspect_candidate(mouse_pos, raw_rect)
                else:
                    self.aspect_drag_last_mouse = QPointF(mouse_pos)
                    return {
                        "ratio": caught["ratio"],
                        "rect": QRectF(caught["rect"]),
                    }

        caught = None
        caught_distance = None
        for candidate in self.aspect_drag_candidates:
            if tuple(candidate["ratio"]) in self.aspect_drag_used_ratios:
                continue
            distance = self._distance_to_candidate(candidate, mouse_pos)
            if distance <= self.ASPECT_SNAP_DISTANCE_PX:
                if caught is None or distance < caught_distance:
                    caught = candidate
                    caught_distance = distance

        if caught is not None:
            self.aspect_drag_caught_ratio = tuple(caught["ratio"])
            self.aspect_drag_last_mouse = QPointF(mouse_pos)
            return {
                "ratio": caught["ratio"],
                "rect": QRectF(caught["rect"]),
            }

        self.aspect_drag_last_mouse = QPointF(mouse_pos)
        return None

    def _snap_aspect_ratio(self, rect, handle_id, mouse_pos):
        if rect.width() < MIN_RECT_SIZE or rect.height() < MIN_RECT_SIZE:
            return rect, None

        current = rect.width() / rect.height()
        best = min(
            self.ASPECT_RATIOS,
            key=lambda pair: self._ratio_error(current, pair[0] / pair[1]),
        )
        target = best[0] / best[1]
        if self._ratio_error(current, target) > 0.05:
            return rect, None

        snapped = self._ratio_rect(rect, handle_id, target)
        handle_points = {
            "tl": snapped.topLeft(),
            "tr": snapped.topRight(),
            "bl": snapped.bottomLeft(),
            "br": snapped.bottomRight(),
            "tm": QPointF(snapped.center().x(), snapped.top()),
            "bm": QPointF(snapped.center().x(), snapped.bottom()),
            "lm": QPointF(snapped.left(), snapped.center().y()),
            "rm": QPointF(snapped.right(), snapped.center().y()),
        }
        point = handle_points.get(handle_id)
        if point is None:
            return rect, None

        zoom = abs(self.view.transform().m11())
        if zoom < 1e-6:
            zoom = 1.0
        max_distance = max(self.ASPECT_SNAP_DISTANCE_PX / zoom, 4.0)
        if math.hypot(point.x() - mouse_pos.x(), point.y() - mouse_pos.y()) > max_distance:
            return rect, None

        target_item = self.crop_target_item
        if target_item is not None and target_item is not self.background_item:
            pixmap = target_item.pixmap()
            image_rect = target_item.mapRectToScene(
                QRectF(0, 0, pixmap.width(), pixmap.height())
            ).normalized()
            snapped = self._fit_ratio_rect_to_bounds(
                snapped, handle_id, target, image_rect
            )
            if (
                snapped.isEmpty()
                or snapped.width() < MIN_RECT_SIZE
                or snapped.height() < MIN_RECT_SIZE
            ):
                return rect, None

        return snapped, best

    @staticmethod
    def _fit_ratio_rect_to_bounds(rect, handle_id, ratio, bounds):
        """Вписывает рамку заданного соотношения в границы вставленного изображения."""
        rect = QRectF(rect).normalized()
        bounds = QRectF(bounds).normalized()
        ratio = float(ratio)
        if ratio <= 0 or bounds.isEmpty():
            return rect

        if handle_id in ("tl", "tr", "bl", "br"):
            if handle_id == "tl":
                ax, ay = rect.right(), rect.bottom()
                max_w = ax - bounds.left()
                max_h = ay - bounds.top()
                w = min(rect.width(), max_w, max_h * ratio)
                h = w / ratio
                return QRectF(ax - w, ay - h, w, h).normalized()
            if handle_id == "tr":
                ax, ay = rect.left(), rect.bottom()
                max_w = bounds.right() - ax
                max_h = ay - bounds.top()
                w = min(rect.width(), max_w, max_h * ratio)
                h = w / ratio
                return QRectF(ax, ay - h, w, h).normalized()
            if handle_id == "bl":
                ax, ay = rect.right(), rect.top()
                max_w = ax - bounds.left()
                max_h = bounds.bottom() - ay
                w = min(rect.width(), max_w, max_h * ratio)
                h = w / ratio
                return QRectF(ax - w, ay, w, h).normalized()

            ax, ay = rect.left(), rect.top()
            max_w = bounds.right() - ax
            max_h = bounds.bottom() - ay
            w = min(rect.width(), max_w, max_h * ratio)
            h = w / ratio
            return QRectF(ax, ay, w, h).normalized()

        if handle_id in ("tm", "bm"):
            anchor_y = rect.bottom() if handle_id == "tm" else rect.top()
            width = min(rect.width(), bounds.width())
            height = width / ratio
            if height > bounds.height():
                height = bounds.height()
                width = height * ratio
            left = max(
                bounds.left(),
                min(rect.center().x() - width / 2, bounds.right() - width),
            )
            if handle_id == "tm":
                top = anchor_y - height
                top = max(bounds.top(), min(top, bounds.bottom() - height))
            else:
                top = anchor_y
                top = max(bounds.top(), min(top, bounds.bottom() - height))
            return QRectF(left, top, width, height).normalized()

        if handle_id in ("lm", "rm"):
            anchor_x = rect.right() if handle_id == "lm" else rect.left()
            height = min(rect.height(), bounds.height())
            width = height * ratio
            if width > bounds.width():
                width = bounds.width()
                height = width / ratio
            top = max(
                bounds.top(),
                min(rect.center().y() - height / 2, bounds.bottom() - height),
            )
            if handle_id == "lm":
                left = anchor_x - width
                left = max(bounds.left(), min(left, bounds.right() - width))
            else:
                left = anchor_x
                left = max(bounds.left(), min(left, bounds.right() - width))
            return QRectF(left, top, width, height).normalized()

        return rect

    def _snap_new_crop_rect(self, rect, start_pos, current_pos):
        handle_id = (
            ("r" if current_pos.x() >= start_pos.x() else "l") +
            ("b" if current_pos.y() >= start_pos.y() else "t")
        )
        handle_id = {"rb": "br", "rt": "tr", "lb": "bl", "lt": "tl"}[handle_id]
        return self._snap_aspect_ratio(rect, handle_id, current_pos)

    # --------------------------------------------------------------
    # Применение обрезки
    # --------------------------------------------------------------
    def apply_crop(self):
        if not self.crop_mode or not self.crop_rect or not self.crop_target_item:
            return

        crop = self.crop_rect.normalized()

        if self.crop_target_item is self.background_item:
            self._apply_crop_to_background(crop)
        else:
            self._apply_crop_to_pasted_image(crop)

    def _apply_crop_to_background(self, crop):
        items_to_remove, items_to_shift, old_positions, new_positions = \
            self._collect_items_for_crop(crop)

        old_pixmap = self.background_item.pixmap()
        old_background_pos = self.background_item.pos()
        local_crop = self.background_item.mapRectFromScene(crop)
        new_pixmap = crop_pixmap_with_padding(old_pixmap, local_crop)
        if new_pixmap.isNull():
            self.overlay.clear()
            return

        command = CropCommand(
            self.view.scene(), self.background_item,
            old_pixmap, new_pixmap, items_to_remove,
            blur_controller=self.view.blur_controller,
            crop_rect=crop,
            items_to_shift=items_to_shift,
            old_positions=old_positions,
            new_positions=new_positions,
            background_pos=old_background_pos,
            # Новый pixmap начинается именно в левом верхнем углу
            # сформированной пользователем scene-рамки.
            new_background_pos=crop.topLeft()
        )

        command._local_crop_rect = local_crop
        self.view.history.push(command)

        self._finish_crop_operation()

    def _apply_crop_to_pasted_image(self, crop):
        old_original = self.crop_target_item.original_pixmap
        old_scale = self.crop_target_item.scale
        old_pos = self.crop_target_item.pos()
        displayed_pixmap = self.crop_target_item.pixmap()

        local_crop_display = self.crop_target_item.mapRectFromScene(crop)

        disp_w = displayed_pixmap.width()
        disp_h = displayed_pixmap.height()
        orig_w = old_original.width()
        orig_h = old_original.height()

        if disp_w > 0 and disp_h > 0 and orig_w > 0 and orig_h > 0:
            scale_x = orig_w / disp_w
            scale_y = orig_h / disp_h
            crop_orig_rect = QRectF(
                round(local_crop_display.x() * scale_x),
                round(local_crop_display.y() * scale_y),
                round(local_crop_display.width() * scale_x),
                round(local_crop_display.height() * scale_y)
            )
        else:
            crop_orig_rect = local_crop_display

        new_original = crop_pixmap(old_original, crop_orig_rect)
        if new_original.isNull():
            self.overlay.clear()
            return

        new_width = new_original.width()
        new_height = new_original.height()
        if new_width > 0 and new_height > 0:
            new_scale = min(crop.width() / new_width, crop.height() / new_height)
            if new_scale <= 0:
                new_scale = 1.0
        else:
            new_scale = 1.0

        crop_scene_pos = crop.topLeft()
        command = CropPastedImageCommand(
            self.crop_target_item, old_original, new_original,
            old_pos, old_scale, new_scale, crop_scene_pos
        )
        self.view.history.push(command)

        self._finish_crop_operation()

    @staticmethod
    def _scene_shape_bounds(item):
        """Возвращает фактические границы shape() в координатах сцены.

        Для crop важно учитывать не только геометрию boundingRect(),
        но и переопределённый shape() аннотации. Иначе элемент,
        визуально/интерактивно выходящий за границу crop, может ошибочно
        считаться полностью помещённым внутрь.
        """
        try:
            path = item.mapToScene(item.shape())
            if not path.isEmpty():
                return path.boundingRect()
        except (AttributeError, RuntimeError):
            pass
        return item.sceneBoundingRect()

    def _collect_items_for_crop(self, crop):
        items_to_remove = []
        items_to_shift = []
        old_positions = []
        new_positions = []

        overlay_items = self.overlay.get_all_overlay_items()
        handle_items = self.overlay.get_handle_items()

        for item in self.view.scene().items():
            if item is self.background_item:
                continue
            if item in overlay_items or item in handle_items.values():
                continue
            if isinstance(item, BlurRegionItem):
                continue

            br = self._scene_shape_bounds(item)
            if not crop.contains(br):
                items_to_remove.append(item)
            else:
                items_to_shift.append(item)
                old_positions.append(item.pos())
                new_positions.append(item.pos() - crop.topLeft())

        return items_to_remove, items_to_shift, old_positions, new_positions

    def _finish_crop_operation(self):
        self.overlay.clear()
        self.overlay.remove_handles()
        self.crop_rect = None
        self.temp_crop_start = None
        self.active_handle = None
        self.crop_mode = False

        self.view.setCursor(Qt.CrossCursor)
        self.view.setBackgroundBrush(self.view.normal_background_color)
        self.view.crop_mode_changed.emit(False)
        self.view._update_floating_widgets_visibility()
        self.crop_target_item = None

        self.view.update_resolution_from_background()
        self.status_bar_manager.reset_to_normal()

    # --------------------------------------------------------------
    # Удаление лишних белых полей
    # --------------------------------------------------------------
    def trim_white_fields(self):
        """Убирает белое поле, оставшееся после расширения подложки."""
        bg = self.background_item
        if (bg is None or self._is_deleted(bg)
                or bg.scene() is not self.view.scene()):
            return False
        if self.crop_mode or self.view.blur_controller.blur_mode:
            return False

        annotation_controller = getattr(
            self.view, "annotation_resize_controller", None)
        if annotation_controller is not None:
            annotation_controller.remove_handles()
        self.view.hide_pasted_image_handles_for_render()

        try:
            local_content = trim_white_border(bg.pixmap())
            if local_content.isEmpty():
                return False

            crop = bg.mapRectToScene(local_content)

            # Границы определяются только реальным содержимым подложки.
            # Аннотации и вставленные объекты не должны расширять crop обратно
            # в белое поле: если объект пересекает новую границу, существующий
            # CropCommand обработает его по обычным правилам crop.
            crop = crop.normalized()
            old_rect = bg.sceneBoundingRect()
            if (abs(crop.left() - old_rect.left()) < 0.5
                    and abs(crop.top() - old_rect.top()) < 0.5
                    and abs(crop.right() - old_rect.right()) < 0.5
                    and abs(crop.bottom() - old_rect.bottom()) < 0.5):
                return False

            self._apply_crop_to_background(crop)
            return True
        finally:
            self.view.show_pasted_image_handles_after_render()
            if annotation_controller is not None:
                annotation_controller.sync_handles()

    # --------------------------------------------------------------
    # Поворот
    # --------------------------------------------------------------
    def rotate_image(self, angle: float):
        selected_pasted = [it for it in self.view.scene().selectedItems()
                           if isinstance(it, PastedImageItem)]
        if selected_pasted:
            for item in selected_pasted:
                old_original = item.original_pixmap
                displayed_pixmap = item.pixmap()
                new_original = rotate_pixmap(displayed_pixmap, angle)
                old_pos = item.pos()
                old_scale = item.scale
                command = RotatePastedImageCommand(
                    item, old_original, new_original, old_pos, old_scale)
                self.view.history.push(command)
            return

        if not self.background_item:
            return

        # Ручки аннотаций — отдельные служебные QGraphicsItem. Перед
        # растеризацией поворота их нужно удалить из сцены: иначе RotateCommand
        # сохранит их как часть поворачиваемого содержимого, а затем undo()
        # сможет вернуть их как независимые устаревшие маркеры.
        annotation_controller = getattr(
            self.view, "annotation_resize_controller", None)
        if annotation_controller is not None:
            annotation_controller.remove_handles()

        items_to_remove = []
        for item in self.view.scene().items():
            if item is self.background_item:
                continue
            items_to_remove.append(item)

        # Рендерим именно в координатах сцены, а не от (0, 0).
        # Подложка после расширения может иметь отрицательную позицию,
        # поэтому QRectF(pixmap.rect()) здесь давал неверный источник
        # и после поворота sceneRect возвращал подложку к началу координат.
        target_rect = self.background_item.sceneBoundingRect()
        rendered_image = QImage(
            target_rect.size().toSize(), QImage.Format_ARGB32)
        rendered_image.fill(Qt.transparent)
        painter = QPainter(rendered_image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        self.view.scene().render(painter, QRectF(0, 0, target_rect.width(),
                                                  target_rect.height()),
                                  target_rect)
        painter.end()

        rendered_pixmap = QPixmap.fromImage(rendered_image)
        rotated_pixmap = rotate_pixmap(rendered_pixmap, angle)

        old_pixmap = self.background_item.pixmap()
        old_background_pos = self.background_item.pos()

        # При повороте размеры pixmap меняются. Сохраняем центр подложки
        # в тех же координатах сцены, а не просто старый левый верхний угол.
        # Это исключает скачок изображения в сторону (0, 0).
        old_scene_rect = self.background_item.sceneBoundingRect()
        new_size = rotated_pixmap.size()
        new_background_pos = old_scene_rect.center() - QPointF(
            new_size.width() / 2.0,
            new_size.height() / 2.0,
        )

        command = RotateCommand(
            self.view.scene(), self.background_item,
            old_pixmap, rotated_pixmap, items_to_remove,
            blur_controller=self.view.blur_controller,
            background_pos=old_background_pos,
            new_background_pos=new_background_pos,
        )
        self.view.history.push(command)
        if annotation_controller is not None:
            self.view.annotation_resize_controller.sync_handles()

    # --------------------------------------------------------------
    # Обработчики мыши — только режим обрезки
    # --------------------------------------------------------------
    def handle_mouse_press(self, event):
        if not self.crop_mode or event.button() != Qt.LeftButton:
            return False

        handle_id = self.overlay.hit_test_handle(QPointF(event.pos()))
        if handle_id:
            self.active_handle = handle_id
            self._begin_aspect_drag(
                handle_id, self.view.mapToScene(event.pos())
            )
            self.overlay.update(
                self.crop_rect,
                self.active_aspect_ratio,
                self.aspect_drag_candidates,
                None,
            )
            return True

        sp = self.view.mapToScene(event.pos())
        sp = self._clamp_to_target(sp)
        self.temp_crop_start = sp
        self.crop_rect = QRectF(sp, sp)
        self.active_aspect_ratio = None
        self.aspect_drag_candidates = []
        self.aspect_drag_caught_ratio = None
        self.aspect_drag_handle = None
        self.aspect_drag_last_mouse = None
        self.aspect_drag_skip_snap = False
        self.overlay.update(self.crop_rect)
        return True

    def handle_mouse_move(self, event):
        if not self.crop_mode:
            return False

        if self.active_handle is not None:
            sp = self.view.mapToScene(event.pos())
            self.crop_rect = self._apply_handle_drag(
                self.active_handle, sp
            )
            caught = self.active_aspect_ratio
            self.overlay.update(
                self.crop_rect,
                caught,
                self.aspect_drag_candidates,
                caught,
            )
            self.overlay.update_resolution_text(
                self.crop_rect, self.crop_target_item
            )
            return True

        if self.temp_crop_start is not None:
            sp = self.view.mapToScene(event.pos())
            sp = self._clamp_to_target(sp)
            raw_rect = QRectF(
                self.temp_crop_start, sp
            ).normalized()

            if (
                raw_rect.width() >= MIN_RECT_SIZE
                and raw_rect.height() >= MIN_RECT_SIZE
                and not self.aspect_drag_candidates
            ):
                handle_id = (
                    ("r" if sp.x() >= self.temp_crop_start.x() else "l")
                    + ("b" if sp.y() >= self.temp_crop_start.y() else "t")
                )
                handle_id = {
                    "rb": "br", "rt": "tr",
                    "lb": "bl", "lt": "tl",
                }[handle_id]
                self.crop_rect = raw_rect
                self._begin_aspect_drag(handle_id, sp)

            if self.aspect_drag_candidates:
                handle_id = self.aspect_drag_handle
                snapped = self._apply_aspect_candidate_snap(
                    raw_rect, handle_id, sp
                )
                if snapped is not None:
                    self.crop_rect = snapped["rect"]
                    self.active_aspect_ratio = snapped["ratio"]
                else:
                    self.crop_rect = raw_rect
                    self.active_aspect_ratio = None
            else:
                self.crop_rect, self.active_aspect_ratio = self._snap_new_crop_rect(
                    raw_rect, self.temp_crop_start, sp
                )

            self.overlay.update(
                self.crop_rect,
                self.active_aspect_ratio,
                self.aspect_drag_candidates,
                self.aspect_drag_caught_ratio,
            )
            self.overlay.update_resolution_text(
                self.crop_rect, self.crop_target_item
            )
            return True

        handle_id = self.overlay.hit_test_handle(QPointF(event.pos()))
        return handle_id is not None

    def handle_mouse_release(self, event):
        if not self.crop_mode or event.button() != Qt.LeftButton:
            return False

        if self.active_handle is not None:
            self.active_handle = None
            self.active_aspect_ratio = None
            self.aspect_drag_candidates = []
            self.aspect_drag_caught_ratio = None
            self.aspect_drag_used_ratios = set()
            self.aspect_drag_handle = None
            self.aspect_drag_last_mouse = None
            self.aspect_drag_skip_snap = False
            return True

        if self.temp_crop_start is not None:
            sp = self.view.mapToScene(event.pos())
            sp = self._clamp_to_target(sp)
            self.crop_rect = QRectF(
                self.temp_crop_start, sp
            ).normalized()
            self.crop_rect, self.active_aspect_ratio = self._snap_new_crop_rect(
                self.crop_rect, self.temp_crop_start, sp
            )

            if (
                self.crop_rect.width() < MIN_RECT_SIZE
                or self.crop_rect.height() < MIN_RECT_SIZE
            ):
                if self.crop_target_item:
                    self.crop_rect = self.crop_target_item.mapRectToScene(
                        QRectF(self.crop_target_item.pixmap().rect())
                    )
                else:
                    self.crop_rect = self.view.sceneRect()

            self.overlay.remove_handles()
            self.overlay.create_handles(self.crop_rect)
            self.overlay.update(self.crop_rect)
            self.overlay.update_resolution_text(
                self.crop_rect, self.crop_target_item
            )
            self.temp_crop_start = None
            self.aspect_drag_candidates = []
            self.aspect_drag_caught_ratio = None
            self.aspect_drag_used_ratios = set()
            self.aspect_drag_handle = None
            self.aspect_drag_last_mouse = None
            self.aspect_drag_skip_snap = False
            return True

        return False

        if self.active_handle is not None:
            self.active_handle = None
            self.active_aspect_ratio = None
            self.aspect_drag_candidates = []
            self.aspect_drag_caught_ratio = None
            self.aspect_drag_used_ratios = set()
            self.aspect_drag_handle = None
            self.aspect_drag_last_mouse = None
            return True

        if self.temp_crop_start is not None:
            sp = self.view.mapToScene(event.pos())
            sp = self._clamp_to_target(sp)
            self.crop_rect = QRectF(
                self.temp_crop_start, sp
            ).normalized()
            self.crop_rect, self.active_aspect_ratio = self._snap_new_crop_rect(
                self.crop_rect, self.temp_crop_start, sp
            )

            if (
                self.crop_rect.width() < MIN_RECT_SIZE
                or self.crop_rect.height() < MIN_RECT_SIZE
            ):
                if self.crop_target_item:
                    self.crop_rect = self.crop_target_item.mapRectToScene(
                        QRectF(self.crop_target_item.pixmap().rect())
                    )
                else:
                    self.crop_rect = self.view.sceneRect()

            self.overlay.remove_handles()
            self.overlay.create_handles(self.crop_rect)
            self.overlay.update(self.crop_rect)
            self.overlay.update_resolution_text(
                self.crop_rect, self.crop_target_item
            )
            self.temp_crop_start = None
            return True

        return False
