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
    # CAD-скриншоты часто содержат очень тонкие линии и мелкий текст.
    # До 3840 px сохраняем запас по детализации без превращения
    # уже очень больших кадров в чрезмерно тяжёлые 2x изображения.
    if longest <= 3840:
        return 1.25
    return 1.0


def _qimage_to_rgba(image):
    """Преобразует QImage в непрерывный массив RGBA с учётом шага строки."""
    source = image.convertToFormat(QImage.Format_RGBA8888).copy()
    width = source.width()
    height = source.height()
    stride = source.bytesPerLine()

    data = source.bits()
    data.setsize(stride * height)
    # Копируем Qt-буфер в Python bytes до передачи в NumPy.
    # Это исключает зависимость массива от времени жизни sip-объекта.
    raw = bytes(data)
    array = np.frombuffer(raw, dtype=np.uint8).reshape((height, stride))
    array = array[:, :width * 4]
    array = array.reshape((height, width, 4))
    return np.ascontiguousarray(array)


def _rgba_to_qimage(array):
    """Преобразует массив RGBA обратно в независимый QImage."""
    array = np.ascontiguousarray(array, dtype=np.uint8)
    height, width, _ = array.shape
    image = QImage(width, height, QImage.Format_RGBA8888)
    image.fill(0)
    destination = image.bits()
    destination.setsize(image.bytesPerLine() * height)
    destination_array = np.frombuffer(
        destination,
        dtype=np.uint8,
    ).reshape((height, image.bytesPerLine()))
    destination_array[:, :width * 4] = array.reshape(
        (height, width * 4)
    )
    return image


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


def _line_mask(gray, inverted=False):
    """Находит тонкие длинные горизонтальные и вертикальные линии."""
    height, width = gray.shape[:2]
    dark = ((gray > 128) if inverted else (gray < 128)).astype(np.uint8) * 255

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
        dark,
        cv2.MORPH_OPEN,
        horizontal_kernel,
    )
    vertical = cv2.morphologyEx(
        dark,
        cv2.MORPH_OPEN,
        vertical_kernel,
    )

    lines = cv2.bitwise_or(horizontal, vertical)
    # Не расширяем линии на 3x3: для CAD это создавало ореолы.
    return _normalise_mask(lines, 0.65)


def _directional_boundary_mask(gray):
    """Выделяет направленные границы, включая диагональные CAD-линии."""
    gray_float = gray.astype(np.float32)

    gx = cv2.Sobel(gray_float, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray_float, cv2.CV_32F, 0, 1, ksize=3)
    gx2 = cv2.GaussianBlur(gx * gx, (0, 0), 1.0)
    gy2 = cv2.GaussianBlur(gy * gy, (0, 0), 1.0)
    gxy = cv2.GaussianBlur(gx * gy, (0, 0), 1.0)

    trace = gx2 + gy2
    discriminant = np.sqrt(
        np.maximum((gx2 - gy2) ** 2 + 4.0 * gxy * gxy, 0.0)
    )
    # Коэффициент когерентности структуры не зависит от того, является
    # линия горизонтальной, вертикальной или диагональной.
    coherence = discriminant / (trace + 1e-3)
    gradient = np.sqrt(np.maximum(trace, 0.0))

    positive_gradient = gradient[gradient > 1.0]
    if positive_gradient.size == 0:
        return np.zeros_like(gray_float)

    reference = float(np.percentile(positive_gradient, 75))
    if reference <= 1.0:
        return np.zeros_like(gray_float)

    response = np.clip(gradient / reference, 0.0, 1.0) * coherence
    response = cv2.GaussianBlur(response, (0, 0), 0.45)

    return np.clip((response - 0.12) / 0.88, 0.0, 1.0).astype(np.float32)


def _directional_gaussian_kernel(angle, sigma_t=0.35, sigma_n=1.15, size=9):
    """Строит анизотропное ядро вдоль заданного направления штриха."""
    radius = size // 2
    axis = np.arange(-radius, radius + 1, dtype=np.float32)
    yy, xx = np.meshgrid(axis, axis)

    tangent = xx * np.cos(angle) + yy * np.sin(angle)
    normal = -xx * np.sin(angle) + yy * np.cos(angle)

    kernel = np.exp(
        -0.5 * (
            (tangent / sigma_t) ** 2
            + (normal / sigma_n) ** 2
        )
    ).astype(np.float32)
    return kernel / max(float(kernel.sum()), 1e-6)


def _apply_directional_cad_detail(bgr, boundary_mask, gain=0.85):
    """Усиливает тонкие CAD-штрихи вдоль их собственной ориентации."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)

    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    gx2 = cv2.GaussianBlur(gx * gx, (0, 0), 1.0)
    gy2 = cv2.GaussianBlur(gy * gy, (0, 0), 1.0)
    gxy = cv2.GaussianBlur(gx * gy, (0, 0), 1.0)

    # Оцениваем ориентацию локального градиента, а затем переводим её
    # в ориентацию самого штриха. Это позволяет обрабатывать не только
    # горизонтали/вертикали, но и типичные диагональные CAD-линии.
    gradient_angle = 0.5 * np.arctan2(
        2.0 * gxy,
        gx2 - gy2 + 1e-3,
    )
    line_angle = gradient_angle + (np.pi / 2.0)

    directions = (
        0.0,
        np.pi / 2.0,
        np.pi / 4.0,
        -np.pi / 4.0,
    )
    orientation_weights = []
    for direction in directions:
        weight = (
            0.5
            * (
                1.0
                + np.cos(2.0 * (line_angle - direction))
            )
        )
        orientation_weights.append(np.power(np.clip(weight, 0.0, 1.0), 4.0))

    weights = np.stack(orientation_weights, axis=0)
    weights /= np.maximum(weights.sum(axis=0), 1e-3)

    # Анизотропные high-pass для четырёх основных направлений.
    # Узкое направление вдоль штриха и более широкое поперёк него
    # помогают не раздувать саму CAD-линию.
    responses = []
    for direction in directions:
        kernel = _directional_gaussian_kernel(direction)
        blurred = cv2.filter2D(
            gray,
            cv2.CV_32F,
            kernel,
            borderType=cv2.BORDER_REPLICATE,
        )
        responses.append(gray - blurred)

    directional = sum(
        response * weight
        for response, weight in zip(responses, weights)
    )
    directional = np.clip(directional, -32.0, 32.0)

    strength = boundary_mask * gain
    result = (
        bgr.astype(np.float32)
        + directional[:, :, None] * strength[:, :, None]
    )
    return result.clip(0, 255).astype(np.uint8)




def _dark_red_mask(rgb):
    """Выделяет тёмно-красные CAD-объекты до инверсии."""
    rgb_float = rgb.astype(np.float32)
    red = rgb_float[:, :, 0]
    green = rgb_float[:, :, 1]
    blue = rgb_float[:, :, 2]

    # Оцениваем тёмность по воспринимаемой яркости, а цвет — по
    # доминированию красного. Для нейтрального тёмного фона маска должна
    # быть нулевой, иначе приглушение затронет весь CAD-снимок.
    luminance = (
        0.299 * red
        + 0.587 * green
        + 0.114 * blue
    )
    darkness = np.clip((140.0 - luminance) / 140.0, 0.0, 1.0)
    red_dominance = np.clip(
        (red - np.maximum(green, blue) - 8.0) / 100.0,
        0.0,
        1.0,
    )
    low_green_blue = np.clip(
        (130.0 - np.maximum(green, blue)) / 130.0,
        0.0,
        1.0,
    )
    mask = (
        darkness
        * red_dominance
        * (0.65 + 0.35 * low_green_blue)
    )
    return np.clip(mask, 0.0, 1.0).astype(np.float32)


def _dark_blue_mask(rgb):
    """Выделяет тёмно-синие CAD-объекты до инверсии."""
    rgb_float = rgb.astype(np.float32)
    red = rgb_float[:, :, 0]
    green = rgb_float[:, :, 1]
    blue = rgb_float[:, :, 2]

    # Для синего важна именно воспринимаемая тёмность: насыщенный синий
    # с B=255 всё равно выглядит тёмным и после инверсии становится
    # жёлто-белым. Поэтому нельзя ограничиваться условием blue < N.
    luminance = (
        0.299 * red
        + 0.587 * green
        + 0.114 * blue
    )
    darkness = np.clip((140.0 - luminance) / 140.0, 0.0, 1.0)
    blue_dominance = np.clip(
        (blue - np.maximum(red, green) - 8.0) / 100.0,
        0.0,
        1.0,
    )
    low_red_green = np.clip(
        (130.0 - np.maximum(red, green)) / 130.0,
        0.0,
        1.0,
    )
    mask = (
        darkness
        * blue_dominance
        * (0.65 + 0.35 * low_red_green)
    )
    return np.clip(mask, 0.0, 1.0).astype(np.float32)


def _tone_map_dark_red_after_inversion(gray, dark_red_mask):
    """Уводит инвертированный тёмно-красный цвет в устойчивый светло-серый."""
    gray_float = gray.astype(np.float32)
    mask = np.clip(dark_red_mask.astype(np.float32), 0.0, 1.0)

    # Не превращаем тёмно-красные объекты в белые пятна: после инверсии
    # слегка приглушаем только их яркость. Это одновременно повышает
    # различимость тонких красных линий на почти белом фоне.
    # Сильнее приглушаем уверенно распознанный красный штрих:
    # после инверсии он должен оставаться светло-серым, а не сливаться
    # с почти белым фоном.
    reduction = 14.0 + 30.0 * mask
    result = gray_float - reduction * mask
    return np.clip(result, 0.0, 255.0).astype(np.uint8)


def _tone_map_dark_blue_after_inversion(gray, dark_blue_mask):
    """Уводит инвертированный тёмно-синий цвет в устойчивый светло-серый."""
    gray_float = gray.astype(np.float32)
    mask = np.clip(dark_blue_mask.astype(np.float32), 0.0, 1.0)

    # Насыщенный синий на тёмной CAD-подложке после RGB-инверсии
    # становится жёлто-белым. Приглушаем только распознанный синий штрих.
    reduction = 14.0 + 30.0 * mask
    result = gray_float - reduction * mask
    return np.clip(result, 0.0, 255.0).astype(np.uint8)


def _compress_cad_highlights(gray, feature_mask, start=170.0, reduction=24.0):
    """Softly reduce only overly bright CAD strokes after inversion."""
    gray_float = gray.astype(np.float32)
    mask = np.clip(feature_mask.astype(np.float32), 0.0, 1.0)

    strength = np.clip(
        (gray_float - start) / max(255.0 - start, 1.0),
        0.0,
        1.0,
    )
    strength = np.power(strength, 1.6) * mask
    delta = reduction * strength
    return np.clip(gray_float - delta, 0.0, 255.0).astype(np.uint8)

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
            cv2.line(mask, (x1, y1), (x2, y2), 255, 1)

    return _normalise_mask(mask, 0.75)


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


def _build_feature_masks(gray, options, inverted=False):
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
        masks["lines"] = _line_mask(gray, inverted=inverted)
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


def is_dark_autocad_scheme(image):
    """Определяет тёмную цветовую схему AutoCAD по преобладающему фону."""
    if image is None or image.isNull():
        return False

    gray = image.convertToFormat(QImage.Format_Grayscale8)
    width = gray.width()
    height = gray.height()
    if width > 128 or height > 128:
        gray = gray.scaled(128, 128)

    data = gray.bits()
    data.setsize(gray.bytesPerLine() * gray.height())
    array = np.frombuffer(data, dtype=np.uint8).reshape(
        (gray.height(), gray.bytesPerLine())
    )[:, :gray.width()]

    median = float(np.median(array))
    dark_fraction = float(np.mean(array < 80))
    bright_fraction = float(np.mean(array > 180))

    # Тёмная схема CAD имеет преимущественно тёмный фон и сравнительно
    # небольшую долю светлых элементов. Светлая схема — наоборот.
    return (
        dark_fraction >= 0.55
        and median < 115
        and bright_fraction < 0.35
    )


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
    source_rgb = rgb.copy()
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    invert = options.color_mode == "invert"
    monochrome = options.color_mode == "monochrome"
    dark_red_mask = _dark_red_mask(rgb) if monochrome else None
    dark_blue_mask = _dark_blue_mask(rgb) if monochrome else None

    scale = _choose_scale(image.width(), image.height(), options.scale)
    if scale != 1.0:
        rgb = cv2.resize(
            rgb,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_LANCZOS4,
        )
        if dark_red_mask is not None:
            dark_red_mask = cv2.resize(
                dark_red_mask,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_LINEAR,
            )
        if dark_blue_mask is not None:
            dark_blue_mask = cv2.resize(
                dark_blue_mask,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_LINEAR,
            )
        source_rgb = cv2.resize(
            source_rgb,
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

    # В монохромном режиме CAD-снимок сначала инвертируется,
    # затем переводится в оттенки серого: белая геометрия на тёмном фоне.
    inverted_white = None
    if invert or monochrome:
        rgb = (255 - rgb.astype(np.int16)).astype(np.uint8)
        if monochrome:
            # Не даём последующим CAD-фильтрам затемнить пиксели,
            # которые были чисто чёрными в исходном изображении.
            inverted_white = np.all(rgb == 255, axis=2)

    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    if monochrome:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        gray = _tone_map_dark_red_after_inversion(
            gray,
            dark_red_mask,
        )
        gray = _tone_map_dark_blue_after_inversion(
            gray,
            dark_blue_mask,
        )
        highlight_geometry = _geometry_mask(gray)
        highlight_directional = _directional_boundary_mask(gray)
        highlight_mask = np.maximum(
            highlight_geometry,
            highlight_directional,
        )
        gray = _compress_cad_highlights(
            gray,
            highlight_mask,
        )
        bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    else:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    masks = _build_feature_masks(
        gray,
        options,
        inverted=(invert or monochrome),
    )

    combined = np.zeros_like(gray, dtype=np.float32)
    strengths = {
        "text": 0.60,
        "lines": 0.82,
        "ui": 0.35,
        "geometry": 0.70,
    }
    for name, mask in masks.items():
        combined = np.maximum(combined, mask * strengths[name])

    if float(combined.max()) > 0:
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        # Контраст повышаем только там, где есть локальная граница.
        gx = cv2.Sobel(l_channel, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(l_channel, cv2.CV_32F, 0, 1, ksize=3)
        gradient = cv2.magnitude(gx, gy)
        edge_reference = float(np.percentile(gradient, 92))
        if edge_reference > 1.0:
            edge_gate = np.clip(gradient / edge_reference, 0.0, 1.0)
            edge_gate = cv2.GaussianBlur(edge_gate, (0, 0), 0.55)
        else:
            edge_gate = np.zeros_like(combined)

        local = cv2.createCLAHE(
            clipLimit=1.20,
            tileGridSize=(8, 8),
        ).apply(l_channel)
        clahe_delta = local.astype(np.float32) - l_channel.astype(np.float32)
        contrast_mask = combined * edge_gate * 0.45
        l_channel = (
            l_channel.astype(np.float32) + clahe_delta * contrast_mask
        ).clip(0, 255).astype(np.uint8)

        enhanced = cv2.cvtColor(
            cv2.merge((l_channel, a_channel, b_channel)),
            cv2.COLOR_LAB2BGR,
        )

        # High-pass практически равен нулю в однородной заливке.
        # Для AutoCAD нужен более узкий high-pass: он подчёркивает
        # штрих/текст, но меньше создаёт светлые ореолы вокруг длинных линий.
        cad_profile = monochrome
        detail_sigma = 0.72 if cad_profile else 1.05
        detail_gain = 0.72 if cad_profile else 0.45
        blurred = cv2.GaussianBlur(
            enhanced,
            (0, 0),
            detail_sigma,
        )
        detail = enhanced.astype(np.float32) - blurred.astype(np.float32)

        # Не усиливаем слабый шум: для CAD полезнее сохранить чистый фон,
        # чем пытаться "вытянуть" каждый пиксель.
        detail_threshold = 1.5 if cad_profile else 0.0
        if detail_threshold > 0:
            detail = np.sign(detail) * np.maximum(
                np.abs(detail) - detail_threshold,
                0.0,
            )

        detail_strength = (
            combined[:, :, None]
            * np.maximum(edge_gate[:, :, None], 0.25)
            * detail_gain
        )
        sharpened = (
            enhanced.astype(np.float32) + detail * detail_strength
        ).clip(0, 255).astype(np.uint8)

        mask = combined[:, :, None]
        bgr = (
            bgr.astype(np.float32) * (1.0 - mask)
            + sharpened.astype(np.float32) * mask
        ).clip(0, 255).astype(np.uint8)

        # Отдельный CAD-проход: не повышаем общую резкость кадра,
        # а усиливаем только направленные границы тонких штрихов.
        # Это особенно полезно для размерных линий и мелких элементов
        # чертежа, где обычный unsharp mask даёт ореолы.
        if cad_profile:
            directional_mask = _directional_boundary_mask(
                cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            )
            bgr = _apply_directional_cad_detail(
                bgr,
                directional_mask,
                gain=0.85,
            )

    if monochrome:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        if inverted_white is not None:
            gray[inverted_white] = 255

        # В тёмной схеме AutoCAD нейтрально-тёмная подложка должна стать
        # чисто белой. Цветные тёмные штрихи сюда не попадают: их высокая
        # цветовая насыщенность уже обрабатывается отдельными масками.
        source_rgb_float = source_rgb.astype(np.float32)
        source_luminance = (
            0.299 * source_rgb_float[:, :, 0]
            + 0.587 * source_rgb_float[:, :, 1]
            + 0.114 * source_rgb_float[:, :, 2]
        )
        source_chroma = (
            source_rgb_float.max(axis=2)
            - source_rgb_float.min(axis=2)
        )
        neutral_dark_background = (
            (source_luminance < 80.0)
            & (source_chroma < 15.0)
        )
        gray[neutral_dark_background] = 255
        bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    elif not invert:
        bgr = _apply_color_mode(bgr, options.color_mode)

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    result = np.dstack((rgb, alpha))
    return _rgba_to_qimage(result)
