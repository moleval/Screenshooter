""" 
Модуль: adaptive_enhancer.py
Описание: Адаптивное улучшение готового изображения перед экспортом.
"""

from dataclasses import dataclass

import cv2
import numpy as np
from PyQt5.QtGui import QImage


@dataclass(frozen=True)
class EnhancerOptions:
    """Параметры адаптивного улучшения."""

    enabled: bool = False
    scale: object = "auto"
    text: bool = True
    lines: bool = True
    ui: bool = True
    geometry: bool = True
    color_mode: str = "auto"


def _choose_scale(width, height, requested):
    """Выбирает масштаб, ограничивая чрезмерное увеличение изображения."""
    if requested != "auto":
        try:
            return max(1.0, min(float(requested), 3.0))
        except (TypeError, ValueError):
            return 1.0

    longest = max(width, height)
    if longest <= 1600:
        return 2.0
    if longest <= 2560:
        return 1.5
    return 1.0


def _qimage_to_rgba(image):
    """Преобразует QImage в непрерывный массив RGBA с учётом шага строки."""
    source = image.convertToFormat(QImage.Format_RGBA8888)
    width = source.width()
    height = source.height()
    stride = source.bytesPerLine()

    data = source.bits()
    data.setsize(stride * height)
    array = np.frombuffer(data, dtype=np.uint8)
    array = array.reshape((height, stride))
    array = array[:, :width * 4]
    array = array.reshape((height, width, 4))
    return np.ascontiguousarray(array)


def _rgba_to_qimage(array):
    """Преобразует массив RGBA обратно в независимый QImage."""
    array = np.ascontiguousarray(array, dtype=np.uint8)
    height, width, _ = array.shape
    image = QImage(
        array.data,
        width,
        height,
        width * 4,
        QImage.Format_RGBA8888,
    )
    return image.copy()


def _edge_mask(gray, strength):
    """Строит мягкую маску для тонких деталей и геометрических контуров."""
    if strength <= 0:
        return None

    edges = cv2.Canny(gray, 40, 120)
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)
    mask = cv2.GaussianBlur(edges, (0, 0), 1.2)
    return (mask.astype(np.float32) / 255.0) * strength


def _apply_color_mode(bgr, mode):
    """Применяет явно выбранный режим цветовой схемы."""
    if mode == "invert":
        return cv2.bitwise_not(bgr)

    return bgr


def enhance_image(image, options):
    """Адаптивно улучшает QImage и возвращает новый QImage."""
    if image is None or image.isNull():
        return image

    if not isinstance(options, EnhancerOptions):
        options = EnhancerOptions(**options)

    if not options.enabled:
        return image

    rgba = _qimage_to_rgba(image)
    alpha = rgba[:, :, 3].copy()
    bgr = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR)

    invert = options.color_mode == "invert"

    scale = _choose_scale(image.width(), image.height(), options.scale)
    if scale != 1.0:
        bgr = cv2.resize(
            bgr,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_LANCZOS4,
        )
        alpha = cv2.resize(
            alpha,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_NEAREST,
        )

    if invert:
        bgr = cv2.bitwise_not(bgr)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        result = np.dstack((rgb, alpha))
        return _rgba_to_qimage(result)

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Базовое локальное улучшение контраста применяется только при
    # наличии включённых режимов, чтобы выключение всех оптимизаций
    # не меняло изображение неожиданно.
    if options.text or options.ui:
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clip_limit = 1.4 if options.text else 1.15
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        bgr = cv2.cvtColor(
            cv2.merge((l_channel, a_channel, b_channel)),
            cv2.COLOR_LAB2BGR,
        )

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    detail_strength = 0.0
    if options.text:
        detail_strength += 0.30
    if options.lines:
        detail_strength += 0.35
    if options.ui:
        detail_strength += 0.15
    if options.geometry:
        detail_strength += 0.20

    if detail_strength > 0:
        blurred = cv2.GaussianBlur(bgr, (0, 0), 1.0)
        sharpened = cv2.addWeighted(
            bgr,
            1.0 + detail_strength,
            blurred,
            -detail_strength,
            0,
        )

        mask_strength = 0.0
        if options.lines:
            mask_strength += 0.45
        if options.geometry:
            mask_strength += 0.35
        if options.text:
            mask_strength += 0.20

        mask = _edge_mask(gray, mask_strength)
        if mask is not None:
            mask = mask[:, :, None]
            bgr = (
                bgr.astype(np.float32) * (1.0 - mask)
                + sharpened.astype(np.float32) * mask
            ).clip(0, 255).astype(np.uint8)

    bgr = _apply_color_mode(bgr, options.color_mode)

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    result = np.dstack((rgb, alpha))
    return _rgba_to_qimage(result)
