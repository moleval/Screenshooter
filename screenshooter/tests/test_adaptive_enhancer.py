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
    return np.ascontiguousarray(array[:, :gray_image.width()])


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

    assert result.pixelColor(0, 0).red() < 10
    assert result.pixelColor(0, 0).green() < 10
    assert result.pixelColor(0, 0).blue() < 10


def test_invert_mode_respects_scale():
    source = _image(80, 50)
    result = enhance_image(
        source,
        EnhancerOptions(enabled=True, scale=2.0, color_mode="invert"),
    )

    assert result.size().width() == 160
    assert result.size().height() == 100
    assert result.pixelColor(0, 0).red() < 10
    assert result.pixelColor(0, 0).green() < 10
    assert result.pixelColor(0, 0).blue() < 10

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
