""" 
Тесты адаптивного улучшайзера.
"""

import cv2
import numpy as np
from PyQt5.QtGui import QColor, QImage

from screenshooter.adaptive_enhancer import (
    EnhancerOptions,
    _apply_directional_cad_detail,
    _build_feature_masks,
    _directional_boundary_mask,
    _compress_cad_highlights,
    _dark_blue_mask,
    _dark_colored_mask,
    _dark_red_mask,
    _tone_map_dark_blue_after_inversion,
    _tone_map_dark_colors_after_inversion,
    _tone_map_dark_red_after_inversion,
    _choose_scale,
    enhance_image,
    is_dark_autocad_scheme,
)


def _image(width=80, height=50):
    image = QImage(width, height, QImage.Format_RGBA8888)
    image.fill(QColor("white"))
    for x in range(width // 4, width * 3 // 4):
        for y in range(height // 3, height * 2 // 3):
            image.setPixelColor(x, y, QColor("black"))
    return image


def _gray_array(image):
    gray_image = image.convertToFormat(QImage.Format_Grayscale8)
    data = gray_image.bits()
    data.setsize(gray_image.bytesPerLine() * gray_image.height())
    array = np.frombuffer(data, dtype=np.uint8).reshape(
        (gray_image.height(), gray_image.bytesPerLine())
    )
    return np.array(array[:, :gray_image.width()], dtype=np.uint8, copy=True)


def _feature_image():
    image = QImage(320, 200, QImage.Format_RGBA8888)
    image.fill(QColor("white"))

    array = np.zeros((200, 320, 4), dtype=np.uint8)
    array[:, :, :3] = 255
    array[:, :, 3] = 255

    array[19:22, 20:301, :3] = 0
    array[35:171, 159:162, :3] = 0
    array[69:72, 210:291, :3] = 0
    array[119:122, 210:291, :3] = 0
    array[70:121, 209:212, :3] = 0
    array[70:121, 289:292, :3] = 0

    for x in range(25, 85):
        y = 82 + ((x * 7) % 12)
        array[y:y + 3, x:x + 5, :3] = 0

    return QImage(
        np.ascontiguousarray(array).data,
        320,
        200,
        320 * 4,
        QImage.Format_RGBA8888,
    ).copy()


def test_disabled_enhancer_keeps_image_size():
    source = _image()
    result = enhance_image(
        source,
        EnhancerOptions(enabled=False, scale=3.0),
    )

    assert result.size() == source.size()
    assert result.pixelColor(0, 0) == source.pixelColor(0, 0)


def test_fixed_scale_changes_output_size():
    source = _image(80, 50)
    result = enhance_image(
        source,
        EnhancerOptions(enabled=True, scale=2.0),
    )

    assert result.size().width() == 160
    assert result.size().height() == 100


def test_auto_scale_uses_two_times_for_small_image():
    source = _image(80, 50)
    result = enhance_image(
        source,
        EnhancerOptions(enabled=True, scale="auto"),
    )

    assert result.size().width() == 160
    assert result.size().height() == 100


def test_invert_mode_inverts_pixels():
    source = _image()
    result = enhance_image(
        source,
        EnhancerOptions(enabled=True, scale=1.0, color_mode="invert"),
    )

    assert result.pixelColor(0, 0).red() == 0
    assert result.pixelColor(0, 0).green() == 0
    assert result.pixelColor(0, 0).blue() == 0


def test_invert_mode_respects_scale():
    source = _image(80, 50)
    result = enhance_image(
        source,
        EnhancerOptions(enabled=True, scale=2.0, color_mode="invert"),
    )

    assert result.size().width() == 160
    assert result.size().height() == 100
    # (10, 10) остаётся внутри однородного белого поля после масштабирования.
    assert result.pixelColor(10, 10).red() == 0
    assert result.pixelColor(10, 10).green() == 0
    assert result.pixelColor(10, 10).blue() == 0


def test_invert_mode_preserves_alpha():
    source = QImage(20, 20, QImage.Format_RGBA8888)
    source.fill(QColor(255, 255, 255, 73))

    result = enhance_image(
        source,
        EnhancerOptions(enabled=True, scale=1.0, color_mode="invert"),
    )

    color = result.pixelColor(0, 0)
    assert color.red() == 0
    assert color.green() == 0
    assert color.blue() == 0
    assert color.alpha() == 73


def test_disabled_feature_flags_do_not_build_feature_masks():
    source = _feature_image()
    gray = _gray_array(source)

    masks = _build_feature_masks(
        gray,
        EnhancerOptions(
            enabled=True,
            scale=1.0,
            text=False,
            lines=False,
            ui=False,
            geometry=False,
        ),
    )

    assert all(float(mask.max()) == 0.0 for mask in masks.values())


def test_line_detector_finds_thin_horizontal_and_vertical_lines():
    source = _feature_image()
    gray = _gray_array(source)

    masks = _build_feature_masks(
        gray,
        EnhancerOptions(enabled=True, scale=1.0, text=False, lines=True,
                        ui=False, geometry=False),
    )

    assert float(masks["lines"].max()) > 0.0



def test_directional_boundary_mask_detects_horizontal_and_vertical_cad_edges():
    image = np.full((120, 180), 220, dtype=np.uint8)
    image[35:37, 20:160] = 30
    image[55:105, 90:92] = 30

    mask = _directional_boundary_mask(image)

    assert float(mask[35:37, 40:150].max()) > 0.4
    assert float(mask[65:100, 90:92].max()) > 0.4
    assert float(mask[75:85, 40:70].max()) < 0.15


def test_directional_cad_detail_increases_thin_line_contrast():
    image = np.full((100, 160), 220, dtype=np.uint8)
    image[48:50, 20:140] = 50
    bgr = np.repeat(image[:, :, None], 3, axis=2)

    mask = _directional_boundary_mask(image)
    result = _apply_directional_cad_detail(bgr, mask, gain=0.85)
    result_gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)

    source_edge_contrast = abs(
        float(image[47, 50:120].mean())
        - float(image[48, 50:120].mean())
    )
    result_edge_contrast = abs(
        float(result_gray[47, 50:120].mean())
        - float(result_gray[48, 50:120].mean())
    )

    # Проверяем именно локальную границу, а не среднюю яркость всей линии.
    assert result_edge_contrast > source_edge_contrast


def test_directional_cad_detail_increases_diagonal_line_contrast():
    image = np.full((140, 140), 220, dtype=np.uint8)
    cv2.line(image, (25, 25), (115, 115), 50, 2)
    bgr = np.repeat(image[:, :, None], 3, axis=2)

    mask = _directional_boundary_mask(image)
    result = _apply_directional_cad_detail(bgr, mask, gain=0.85)
    result_gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)

    source_edge_contrast = abs(
        float(image[70, 70])
        - float(image[70, 66])
    )
    result_edge_contrast = abs(
        float(result_gray[70, 70])
        - float(result_gray[70, 66])
    )

    assert float(mask[45:105, 45:105].max()) > 0.25
    assert result_edge_contrast > source_edge_contrast



def test_dark_red_mask_selects_dark_red_but_not_dark_neutral():
    rgb = np.full((20, 30, 3), 20, dtype=np.uint8)
    rgb[5:15, 5:20] = (90, 15, 12)
    rgb[2:4, 2:10] = (20, 20, 20)

    mask = _dark_red_mask(rgb)

    assert float(mask[8:12, 8:18].mean()) > 0.35
    assert float(mask[2:4, 2:10].max()) < 0.01


def test_dark_red_after_inversion_becomes_light_gray_not_white():
    rgb = np.full((30, 40, 3), 20, dtype=np.uint8)
    rgb[10:20, 10:30] = (90, 15, 12)

    dark_red_mask = _dark_red_mask(rgb)
    inverted_gray = np.full((30, 40), 255, dtype=np.uint8)
    inverted_gray[10:20, 10:30] = 229

    result = _tone_map_dark_red_after_inversion(
        inverted_gray,
        dark_red_mask,
    )

    assert 190 <= int(result[15, 20]) <= 220
    assert int(result[0, 0]) == 255


def test_dark_blue_mask_selects_saturated_blue_but_not_dark_neutral():
    rgb = np.full((20, 30, 3), 20, dtype=np.uint8)
    rgb[5:15, 5:20] = (0, 0, 220)
    rgb[2:4, 2:10] = (20, 20, 20)

    mask = _dark_blue_mask(rgb)

    assert float(mask[8:12, 8:18].mean()) > 0.35
    assert float(mask[2:4, 2:10].max()) < 0.01


def test_dark_blue_after_inversion_becomes_light_gray_not_white():
    rgb = np.full((30, 40, 3), 20, dtype=np.uint8)
    rgb[10:20, 10:30] = (0, 0, 220)

    dark_blue_mask = _dark_blue_mask(rgb)
    inverted_gray = np.full((30, 40), 255, dtype=np.uint8)
    inverted_gray[10:20, 10:30] = 230

    result = _tone_map_dark_blue_after_inversion(
        inverted_gray,
        dark_blue_mask,
    )

    assert 190 <= int(result[15, 20]) <= 220
    assert int(result[0, 0]) == 255


def test_monochrome_dark_blue_line_becomes_light_gray():
    source = QImage(40, 30, QImage.Format_RGBA8888)
    source.fill(QColor(20, 20, 20, 255))
    for y in range(10, 20):
        for x in range(10, 30):
            source.setPixelColor(x, y, QColor(0, 0, 220, 255))

    result = enhance_image(
        source,
        EnhancerOptions(
            enabled=True,
            scale=1.0,
            text=False,
            lines=False,
            ui=False,
            geometry=False,
            color_mode="monochrome",
        ),
    )

    line = result.pixelColor(20, 15)
    background = result.pixelColor(0, 0)
    assert line.red() == line.green() == line.blue()
    assert 190 <= line.red() <= 220
    assert background.red() == background.green() == background.blue() == 255


def test_dark_colored_mask_selects_saturated_colors_but_not_dark_neutral():
    rgb = np.full((30, 60, 3), 20, dtype=np.uint8)
    rgb[4:8, 4:14] = (0, 150, 0)
    rgb[10:14, 18:28] = (0, 150, 150)
    rgb[16:20, 32:42] = (110, 0, 110)
    rgb[22:26, 46:56] = (90, 15, 12)

    mask = _dark_colored_mask(rgb)

    assert float(mask[5:7, 6:12].mean()) > 0.35
    assert float(mask[11:13, 20:26].mean()) > 0.35
    assert float(mask[17:19, 34:40].mean()) > 0.35
    assert float(mask[23:25, 48:54].mean()) > 0.35
    assert float(mask[0:3, 0:20].max()) < 0.01


def test_dark_colored_tone_map_normalizes_different_hues_to_light_gray():
    gray = np.full((20, 80), 255, dtype=np.uint8)
    gray[2:5, 5:15] = 180
    gray[7:10, 20:30] = 150
    gray[12:15, 35:45] = 205
    gray[15:18, 55:65] = 165

    mask = np.zeros_like(gray, dtype=np.float32)
    mask[2:5, 5:15] = 1.0
    mask[7:10, 20:30] = 1.0
    mask[12:15, 35:45] = 1.0
    mask[15:18, 55:65] = 1.0

    result = _tone_map_dark_colors_after_inversion(gray, mask)

    assert 210 <= int(result[3, 10]) <= 220
    assert 210 <= int(result[8, 25]) <= 220
    assert 210 <= int(result[13, 40]) <= 220
    assert 210 <= int(result[16, 60]) <= 220
    assert int(result[0, 0]) == 255


def test_monochrome_dark_green_diagonal_stays_sharp_and_light_gray():
    source = QImage(80, 80, QImage.Format_RGBA8888)
    source.fill(QColor(20, 20, 20, 255))
    for i in range(12, 68):
        for offset in range(-1, 2):
            x = i
            y = i + offset
            if 0 <= x < 80 and 0 <= y < 80:
                source.setPixelColor(x, y, QColor(0, 150, 0, 255))

    result = enhance_image(
        source,
        EnhancerOptions(
            enabled=True,
            scale=1.0,
            text=False,
            lines=False,
            ui=False,
            geometry=False,
            color_mode="monochrome",
        ),
    )

    center = result.pixelColor(40, 40)
    side = result.pixelColor(40, 36)
    assert center.red() == center.green() == center.blue()
    assert 205 <= center.red() <= 220
    assert side.red() - center.red() >= 20


def test_cad_highlight_compression_leaves_uniform_background_unchanged():
    gray = np.full((80, 120), 235, dtype=np.uint8)
    gray[39:41, 20:100] = 255

    feature_mask = np.zeros_like(gray, dtype=np.float32)
    feature_mask[38:42, 20:100] = 1.0

    result = _compress_cad_highlights(gray, feature_mask)

    assert int(result[10, 10]) == 235
    assert int(result[40, 60]) < 235
    assert int(result[40, 60]) >= 225

def test_geometry_detector_finds_long_segments():
    source = _feature_image()
    gray = _gray_array(source)

    masks = _build_feature_masks(
        gray,
        EnhancerOptions(enabled=True, scale=1.0, text=False, lines=False,
                        ui=False, geometry=True),
    )

    assert float(masks["geometry"].max()) > 0.0


def test_ui_detector_finds_rectangular_control():
    source = _feature_image()
    gray = _gray_array(source)

    masks = _build_feature_masks(
        gray,
        EnhancerOptions(enabled=True, scale=1.0, text=False, lines=False,
                        ui=True, geometry=False),
    )

    assert float(masks["ui"].max()) > 0.0


def _rgba_array(image):
    source = image.convertToFormat(QImage.Format_RGBA8888)
    data = source.bits()
    data.setsize(source.bytesPerLine() * source.height())
    array = np.frombuffer(data, dtype=np.uint8).reshape(
        (source.height(), source.bytesPerLine())
    )
    return np.ascontiguousarray(array[:, :source.width() * 4]).reshape(
        (source.height(), source.width(), 4)
    )


def test_auto_scale_gives_cad_medium_large_images_a_moderate_upscale():
    assert _choose_scale(3200, 1800, "auto") == 1.25
    assert _choose_scale(3840, 2160, "auto") == 1.25
    assert _choose_scale(4096, 2160, "auto") == 1.0


def test_invert_mode_runs_enhancement_after_inversion(monkeypatch):
    source = _feature_image()
    calls = {}

    class FakeClahe:
        def apply(self, channel):
            calls["clahe_input"] = channel.copy()
            return np.clip(
                channel.astype(np.int16) + 20,
                0,
                255,
            ).astype(np.uint8)

    def fake_build_feature_masks(gray, options, inverted=False):
        calls["gray"] = gray.copy()
        calls["inverted"] = inverted
        return {
            "text": np.zeros_like(gray, dtype=np.float32),
            "lines": np.ones_like(gray, dtype=np.float32),
            "ui": np.zeros_like(gray, dtype=np.float32),
            "geometry": np.zeros_like(gray, dtype=np.float32),
        }

    monkeypatch.setattr(
        "screenshooter.adaptive_enhancer.cv2.createCLAHE",
        lambda clipLimit, tileGridSize: FakeClahe(),
    )
    monkeypatch.setattr(
        "screenshooter.adaptive_enhancer._build_feature_masks",
        fake_build_feature_masks,
    )

    result = enhance_image(
        source,
        EnhancerOptions(
            enabled=True,
            scale=1.0,
            text=False,
            lines=True,
            ui=False,
            geometry=True,
            color_mode="invert",
        ),
    )

    source_gray = _gray_array(source)

    assert result.size() == source.size()
    assert calls["inverted"] is True
    # Белый фон исходника должен попасть в детекторы уже как тёмный фон.
    assert int(calls["gray"].mean()) < int(source_gray.mean())
    # Непосредственно перед CLAHE должен использоваться уже инвертированный L-канал.
    assert int(calls["clahe_input"].mean()) < int(source_gray.mean())
    # CLAHE был реально пропущен через enhancement pipeline.
    assert np.any(calls["clahe_input"] != 0)


def test_inverted_line_detector_finds_light_cad_lines():
    source = _feature_image()
    gray = _gray_array(source)
    inverted_gray = 255 - gray

    masks = _build_feature_masks(
        inverted_gray,
        EnhancerOptions(
            enabled=True,
            scale=1.0,
            text=False,
            lines=True,
            ui=False,
            geometry=False,
            color_mode="invert",
        ),
        inverted=True,
    )

    assert float(masks["lines"].max()) > 0.0

    
def test_enhancer_preserves_uniform_cad_fill():
    source = QImage(240, 160, QImage.Format_RGBA8888)
    source.fill(QColor(235, 235, 235, 255))

    array = np.zeros((160, 240, 4), dtype=np.uint8)
    array[:, :, :3] = 235
    array[:, :, 3] = 255
    array[40:120, 70:170, :3] = 145
    array[78:82, 80:160, :3] = 35

    source = QImage(
        np.ascontiguousarray(array).data,
        240,
        160,
        240 * 4,
        QImage.Format_RGBA8888,
    ).copy()

    result = enhance_image(
        source,
        EnhancerOptions(
            enabled=True,
            scale=1.0,
            text=False,
            lines=True,
            ui=False,
            geometry=True,
        ),
    )

    result_array = _rgba_array(result)
    # Центр однородной CAD-заливки не должен получить контрастный сдвиг.
    assert np.max(np.abs(
        result_array[55:70, 95:145, :3].astype(np.int16) - 145
    )) <= 1
    source_array = _rgba_array(source)
    assert np.array_equal(result_array[:, :, 3], source_array[:, :, 3])


def test_invert_mode_works_without_general_enhancer_toggle():
    source = _image()
    result = enhance_image(
        source,
        EnhancerOptions(
            enabled=True,
            scale=1.0,
            text=False,
            lines=False,
            ui=False,
            geometry=False,
            color_mode="invert",
        ),
    )
    source_gray = _gray_array(source)
    result_gray = _gray_array(result)
    assert int(source_gray.mean()) > 200
    assert int(result_gray.mean()) < 60


def test_monochrome_mode_inverts_and_removes_color():
    source = QImage(20, 20, QImage.Format_RGBA8888)
    source.fill(QColor(255, 255, 0, 255))
    source.setPixelColor(0, 0, QColor(0, 0, 0, 255))

    result = enhance_image(
        source,
        EnhancerOptions(
            enabled=True,
            scale=1.0,
            text=False,
            lines=False,
            ui=False,
            geometry=False,
            color_mode="monochrome",
        ),
    )

    yellow = result.pixelColor(10, 10)
    black = result.pixelColor(0, 0)
    assert yellow.red() == yellow.green() == yellow.blue()
    assert yellow.red() < 255
    assert black.red() == black.green() == black.blue() == 255


def test_monochrome_mode_detects_light_cad_lines():
    source = QImage(320, 200, QImage.Format_RGBA8888)
    source.fill(QColor(20, 20, 20, 255))
    for x in range(20, 301):
        source.setPixelColor(x, 80, QColor(255, 255, 0, 255))

    gray = _gray_array(source)
    masks = _build_feature_masks(
        gray,
        EnhancerOptions(
            enabled=True,
            scale=1.0,
            text=False,
            lines=True,
            ui=False,
            geometry=False,
            color_mode="monochrome",
        ),
        inverted=True,
    )
    assert float(masks["lines"].max()) > 0.0


def test_dark_autocad_scheme_is_detected():
    source = QImage(320, 200, QImage.Format_RGBA8888)
    source.fill(QColor(20, 20, 20, 255))
    for x in range(20, 301):
        source.setPixelColor(x, 80, QColor(255, 255, 0, 255))

    assert is_dark_autocad_scheme(source) is True


def test_light_autocad_scheme_is_not_detected_as_dark():
    source = QImage(320, 200, QImage.Format_RGBA8888)
    source.fill(QColor(235, 235, 235, 255))
    for x in range(20, 301):
        source.setPixelColor(x, 80, QColor(30, 30, 30, 255))

    assert is_dark_autocad_scheme(source) is False

def test_dark_autocad_scheme_ignores_bright_ui_around_canvas():
    source = QImage(320, 200, QImage.Format_RGBA8888)
    source.fill(QColor(25, 25, 25, 255))

    # Яркая верхняя лента и боковая панель занимают значимую часть
    # полного кадра, но центральное поле чертежа остаётся тёмным.
    for y in range(0, 65):
        for x in range(320):
            source.setPixelColor(x, y, QColor(225, 225, 225, 255))
    for y in range(65, 200):
        for x in range(0, 55):
            source.setPixelColor(x, y, QColor(225, 225, 225, 255))

    assert is_dark_autocad_scheme(source) is True
