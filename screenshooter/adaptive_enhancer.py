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


def _normalise_mask(mask, blur=1.0):
    """Преобразует бинарную или градиентную маску в мягкую шкалу 0..1."""
    mask = np.asarray(mask, dtype=np.float32)
    if mask.size == 0 or float(mask.max()) <= 0:
        return np.zeros(mask.shape, dtype=np.float32)

    if blur > 0:
        mask = cv2.GaussianBlur(mask, (0, 0), blur)

    maximum = float(mask.max())
    return np.clip(mask / maximum, 0.0, 1.0)


def _text_mask(gray):
    """Находит компактные штрихи, характерные для мелкого текста."""
    height, width = gray.shape[:2]
    kernel_size = max(3, min(21, int(round(min(height, width) / 35)) | 1))
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (kernel_size, kernel_size),
    )

    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    response = np.maximum(blackhat, tophat)

    threshold = max(8.0, float(np.percentile(response, 88)))
    binary = (response >= threshold).astype(np.uint8) * 255

    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, close_kernel)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        binary,
        connectivity=8,
    )
    accepted = np.zeros_like(binary)
    image_area = height * width

    for label in range(1, num_labels):
        x, y, w, h, area = stats[label]
        if area < 2:
            continue
        if area > max(256, image_area // 80):
            continue
        if w > max(4, width // 3) or h > max(4, height // 3):
            continue

        fill_ratio = area / float(max(1, w * h))
        if 0.03 <= fill_ratio <= 0.80:
            accepted[labels == label] = 255

    return _normalise_mask(accepted, 0.8)


def _line_mask(gray):
    """Находит тонкие длинные горизонтальные и вертикальные линии."""
    edges = cv2.Canny(gray, 40, 120)

    height, width = gray.shape[:2]
    horizontal_length = max(5, width // 18)
    vertical_length = max(5, height // 18)

    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (horizontal_length, 1),
    )
    vertical_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (1, vertical_length),
    )

    horizontal = cv2.morphologyEx(
        edges,
        cv2.MORPH_OPEN,
        horizontal_kernel,
    )
    vertical = cv2.morphologyEx(
        edges,
        cv2.MORPH_OPEN,
        vertical_kernel,
    )

    lines = cv2.bitwise_or(horizontal, vertical)
    lines = cv2.dilate(
        lines,
        np.ones((3, 3), np.uint8),
        iterations=1,
    )
    return _normalise_mask(lines, 0.9)


def _geometry_mask(gray):
    """Находит длинные прямые сегменты и угловые геометрические контуры."""
    edges = cv2.Canny(gray, 50, 150)
    height, width = gray.shape[:2]
    min_length = max(12, min(width, height) // 8)

    segments = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=max(12, min(width, height) // 12),
        minLineLength=min_length,
        maxLineGap=max(3, min(width, height) // 60),
    )

    mask = np.zeros_like(gray)
    if segments is not None:
        for segment in segments:
            x1, y1, x2, y2 = map(int, segment)
            cv2.line(mask, (x1, y1), (x2, y2), 255, 2)

    return _normalise_mask(mask, 1.0)


def _ui_mask(gray):
    """Находит небольшие прямоугольные области, характерные для UI."""
    edges = cv2.Canny(gray, 40, 120)
    contours, _ = cv2.findContours(
        edges,
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    height, width = gray.shape[:2]
    image_area = height * width
    mask = np.zeros_like(gray)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 16 or area > image_area * 0.35:
            continue

        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue

        polygon = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue

        x, y, w, h = cv2.boundingRect(polygon)
        if w < 6 or h < 6:
            continue
        if w > width * 0.8 or h > height * 0.8:
            continue

        aspect = w / float(h)
        if aspect < 0.15 or aspect > 8.0:
            continue

        cv2.drawContours(mask, [contour], -1, 255, 2)

    return _normalise_mask(mask, 1.0)


def _build_feature_masks(gray, options):
    """Строит независимые маски текста, линий, UI и геометрии."""
    masks = {
        "text": np.zeros_like(gray, dtype=np.float32),
        "lines": np.zeros_like(gray, dtype=np.float32),
        "ui": np.zeros_like(gray, dtype=np.float32),
        "geometry": np.zeros_like(gray, dtype=np.float32),
    }

    if options.text:
        masks["text"] = _text_mask(gray)
    if options.lines:
        masks["lines"] = _line_mask(gray)
    if options.ui:
        masks["ui"] = _ui_mask(gray)
    if options.geometry:
        masks["geometry"] = _geometry_mask(gray)

    return masks


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
    rgb = rgba[:, :, :3].copy()
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    invert = options.color_mode == "invert"

    scale = _choose_scale(image.width(), image.height(), options.scale)
    if scale != 1.0:
        rgb = cv2.resize(
            rgb,
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
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    if invert:
        rgb = cv2.bitwise_not(rgb)
        result = np.dstack((rgb, alpha))
        return _rgba_to_qimage(result)

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    masks = _build_feature_masks(gray, options)

    combined = np.zeros_like(gray, dtype=np.float32)
    strengths = {
        "text": 0.55,
        "lines": 0.75,
        "ui": 0.40,
        "geometry": 0.65,
    }
    for name, mask in masks.items():
        combined = np.maximum(combined, mask * strengths[name])

    if float(combined.max()) > 0:
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        contrast_mask = np.clip(combined * 0.55, 0.0, 0.55)
        local = cv2.createCLAHE(
            clipLimit=1.35,
            tileGridSize=(8, 8),
        ).apply(l_channel)
        l_channel = (
            l_channel.astype(np.float32) * (1.0 - contrast_mask)
            + local.astype(np.float32) * contrast_mask
        ).clip(0, 255).astype(np.uint8)

        enhanced = cv2.cvtColor(
            cv2.merge((l_channel, a_channel, b_channel)),
            cv2.COLOR_LAB2BGR,
        )

        blurred = cv2.GaussianBlur(enhanced, (0, 0), 0.9)
        sharpened = cv2.addWeighted(
            enhanced,
            1.0 + 0.65 * combined,
            blurred,
            -0.65 * combined,
            0,
        )

        mask = combined[:, :, None]
        bgr = (
            bgr.astype(np.float32) * (1.0 - mask)
            + sharpened.astype(np.float32) * mask
        ).clip(0, 255).astype(np.uint8)

    bgr = _apply_color_mode(bgr, options.color_mode)

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    result = np.dstack((rgb, alpha))
    return _rgba_to_qimage(result)
