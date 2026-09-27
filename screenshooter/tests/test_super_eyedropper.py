from PyQt5.QtCore import QPoint, QRect, Qt
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import QToolButton

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

    assert formats["HEX/HTML"] == "#123456".upper()
    assert formats["RGB"] == "rgb(18, 52, 86)"
    assert "HSL" in formats
    assert "HSV" in formats
    assert "CMYK" in formats
    assert popup._formats()["HEX/HTML"] == "#123456".upper()

    popup._copy_value(formats["HEX"])
    assert qapp.clipboard().text() == "#123456".upper()
    assert popup.status.text() == "Скопировано"


def test_color_palette_contains_super_eyedropper(qapp):
    palette = ColorPaletteWidget()
    assert palette.eyedropper_btn.toolTip().startswith("Супер-пипетка")

def test_color_palette_uses_local_palette_icon(qapp):
    palette = ColorPaletteWidget()
    assert not palette.palette_btn.icon().isNull()


def test_screen_picker_emits_sampled_color(qapp):
    picker = ScreenColorPicker()
    pixmap = QPixmap(2, 2)
    pixmap.fill(QColor("#ABCDEF"))
    picker._captures = [(QRect(100, 50, 2, 2), pixmap)]
    received = []
    picker.colorPicked.connect(lambda color, pos: received.append((color.name(), pos)))

    class Event:
        def button(self):
            return Qt.LeftButton

        def globalPos(self):
            return QPoint(101, 51)

    picker.mousePressEvent(Event())

    assert received
    assert received[0][0] == "#abcdef"

def test_screen_picker_accepts_mouse_events(qapp):
    picker = ScreenColorPicker()
    assert not picker.testAttribute(Qt.WA_TransparentForMouseEvents)


def test_color_result_popup_uses_mirrored_copy_icon(qapp):
    popup = ColorResultPopup(QColor("#123456"), QPoint(10, 10))
    assert not popup.findChildren(QToolButton)[0].icon().isNull()
