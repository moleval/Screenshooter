"""
Тесты для ClipboardController: копирование и вставка аннотаций,
вставленных изображений и зон размытия.
"""

import pytest
from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtGui import QPen, QColor, QPixmap
from PyQt5.QtWidgets import QGraphicsScene

from screenshooter.controllers.clipboard_controller import ClipboardController
from screenshooter.items.shape_items import RectangleItem
from screenshooter.items.text_item import TextItem
from screenshooter.items.pasted_image_item import PastedImageItem
from screenshooter.items.blur_region_item import BlurRegionItem


class FakeBlurController:
    """Заглушка для BlurController, используемая в тестах."""
    def __init__(self):
        self.blur_regions = []
        self.blur_region_items = []

    def _invalidate_blur_cache(self):
        pass

    def _recompute_blurred_pixmap(self):
        pass


class FakeView:
    """Минимальная заглушка EditorView, достаточная для ClipboardController."""
    def __init__(self):
        self._scene = QGraphicsScene()
        self.pasted_images = []
        self.blur_controller = FakeBlurController()
        self.history = None
        self._background_item = None

    def scene(self):
        return self._scene

    def _is_background_item(self, item):
        return item is self._background_item

    def _item_for_manipulation(self, item):
        return item

    def _update_pasted_image_handles(self):
        pass

    def _invalidate_cursor_cache(self):
        pass

    def _update_blur_region_handles(self):
        pass

    def show_status_message(self, *args, **kwargs):
        pass


@pytest.fixture
def view():
    return FakeView()


@pytest.fixture
def controller(view):
    return ClipboardController(view)


def test_copy_and_paste_rectangle(qapp, view, controller):
    rect_item = RectangleItem(QRectF(10, 10, 50, 30), QPen(QColor("red"), 2))
    view.scene().addItem(rect_item)
    rect_item.setSelected(True)

    assert controller.copy_selected() is True
    assert controller.has_clipboard is True

    controller.paste()

    items = view.scene().items()
    assert len(items) == 2


def test_copy_and_paste_text(qapp, view, controller):
    text_item = TextItem(view, bg_color=None)
    text_item.setPlainText("Test")
    view.scene().addItem(text_item)
    text_item.setSelected(True)

    assert controller.copy_selected() is True
    controller.paste()

    texts = [item.toPlainText() for item in view.scene().items()
             if isinstance(item, TextItem)]
    assert texts.count("Test") == 2


def test_copy_and_paste_pasted_image(qapp, view, controller):
    pixmap = QPixmap(20, 20)
    pixmap.fill(QColor("green"))
    img_item = PastedImageItem(pixmap, view)
    view.scene().addItem(img_item)
    view.pasted_images.append(img_item)
    img_item.setSelected(True)

    assert controller.copy_selected() is True
    controller.paste()

    pasted = [item for item in view.scene().items()
              if isinstance(item, PastedImageItem)]
    assert len(pasted) == 2


def test_copy_and_paste_blur_region(qapp, view, controller):
    blur_item = BlurRegionItem(QRectF(5, 5, 40, 40), view, mode='inactive')
    view.scene().addItem(blur_item)
    view.blur_controller.blur_regions.append(blur_item.rect())
    view.blur_controller.blur_region_items.append(blur_item)
    blur_item.setSelected(True)

    assert controller.copy_selected() is True
    controller.paste()

    assert len(view.blur_controller.blur_region_items) == 2