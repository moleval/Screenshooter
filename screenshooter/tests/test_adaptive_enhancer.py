""" 
Тесты адаптивного улучшайзера.
"""

import numpy as np
from PyQt5.QtGui import QColor, QImage

from screenshooter.adaptive_enhancer import (
    EnhancerOptions,
    _build_feature_masks,
    enhance_image,
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
