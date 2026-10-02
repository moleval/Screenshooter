"""
Тесты адаптивного улучшайзера.
"""

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter

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
    return np.frombuffer(data, dtype=np.uint8).reshape(
        (gray_image.height(), gray_image.bytesPerLine())
    )[:, :gray_image.width()]


def _feature_image():
    image = QImage(320, 200, QImage.Format_RGBA8888)
    image.fill(QColor("white"))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, False)
    painter.setPen(QColor("black"))
    painter.setBrush(Qt.NoBrush)

    painter.drawLine(20, 20, 300, 20)
    painter.drawLine(160, 35, 160, 170)
    painter.drawRect(210, 70, 80, 50)

    painter.setFont(QFont("Arial", 18))
    painter.drawText(25, 90, "Test")
    painter.end()
    return image


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
    gray_image = source.convertToFormat(QImage.Format_Grayscale8)
    data = gray_image.bits()
    data.setsize(gray_image.bytesPerLine() * gray_image.height())
    gray = np.frombuffer(data, dtype=np.uint8).reshape(
        (gray_image.height(), gray_image.bytesPerLine())
    )[:, :gray_image.width()]

    masks = _build_feature_masks(
        gray,
        EnhancerOptions(enabled=True, scale=1.0, text=False, lines=False,
                        ui=False, geometry=True),
    )

    assert float(masks["geometry"].max()) > 0.0


def test_ui_detector_finds_rectangular_control():
    source = _feature_image()
    gray_image = source.convertToFormat(QImage.Format_Grayscale8)
    data = gray_image.bits()
    data.setsize(gray_image.bytesPerLine() * gray_image.height())
    gray = np.frombuffer(data, dtype=np.uint8).reshape(
        (gray_image.height(), gray_image.bytesPerLine())
    )[:, :gray_image.width()]

    masks = _build_feature_masks(
        gray,
        EnhancerOptions(enabled=True, scale=1.0, text=False, lines=False,
                        ui=True, geometry=False),
    )

    assert float(masks["ui"].max()) > 0.0
