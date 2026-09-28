# tests/test_image_processing.py
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QPixmap, QColor

from screenshooter.image_processing import crop_pixmap, rotate_pixmap, blur_region, trim_white_border


def make_test_pixmap(width=100, height=80):
    pm = QPixmap(width, height)
    pm.fill(QColor("white"))
    return pm


def test_crop_pixmap_returns_correct_size(qapp):
    pm = make_test_pixmap(100, 80)
    cropped = crop_pixmap(pm, QRectF(10, 10, 40, 30))
    assert cropped.width() == 40
    assert cropped.height() == 30


def test_rotate_pixmap_90_swaps_dimensions(qapp):
    pm = make_test_pixmap(100, 80)
    rotated = rotate_pixmap(pm, 90)
    assert rotated.width() == 80
    assert rotated.height() == 100


def test_blur_region_keeps_size_and_is_not_null(qapp):
    pm = make_test_pixmap(100, 80)
    blurred = blur_region(pm, QRectF(20, 20, 40, 30), radius=5.0)
    assert not blurred.isNull()
    assert blurred.size() == pm.size()
def test_trim_white_border_finds_non_white_content(qapp):
    pm = make_test_pixmap(20, 16)
    image = pm.toImage()
    for y in range(4, 12):
        for x in range(5, 15):
            image.setPixelColor(x, y, QColor("black"))
    pm = QPixmap.fromImage(image)

    rect = trim_white_border(pm)

    assert rect.x() == 5
    assert rect.y() == 4
    assert rect.width() == 10
    assert rect.height() == 8


def test_trim_white_border_keeps_all_white_image(qapp):
    pm = make_test_pixmap(20, 16)
    assert trim_white_border(pm) == QRectF(0, 0, 20, 16)
