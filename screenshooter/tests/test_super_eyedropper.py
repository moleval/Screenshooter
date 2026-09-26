from PyQt5.QtCore import QPoint, QRect
from PyQt5.QtGui import QColor, QPixmap

from screenshooter.widgets.color_palette import ColorPaletteWidget
from screenshooter.widgets.super_eyedropper import ColorResultPopup, ScreenColorPicker


def test_screen_picker_samples_original_pixel(qapp):
    pixmap = QPixmap(4, 4)
    pixmap.fill(QColor("#123456"))

    picker = ScreenColorPicker()
    picker._captures = [(QRect(100, 50, 4, 4), pixmap)]

    color = picker._sample_global(QPoint(102, 52))

    assert color.name() == "#123456"


def test_color_result_popup_has_common_formats_and_copy_status(qapp):
    popup = ColorResultPopup(QColor("#123456"), QPoint(10, 10))
    formats = popup._formats()

    assert formats["HEX"] == "#123456".upper()
    assert formats["RGB"] == "rgb(18, 52, 86)"
    assert "HSL" in formats
    assert "HSV" in formats
    assert "CMYK" in formats

    popup._copy_value(formats["HEX"])
    assert qapp.clipboard().text() == "#123456".upper()
    assert popup.status.text() == "Скопировано"


def test_color_palette_contains_super_eyedropper(qapp):
    palette = ColorPaletteWidget()
    assert palette.eyedropper_btn.toolTip().startswith("Супер-пипетка")
