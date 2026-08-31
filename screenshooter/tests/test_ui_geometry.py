"""
Тесты геометрии UI после рефакторинга (Шаг 8).
"""

import pytest
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import QPixmap, QColor

from screenshooter.app import ScreenshotApp
from screenshooter.ui.editor_toolbar_strip import EditorToolbarStrip
from screenshooter.ui.toolbar_separator import ToolbarSeparator
from screenshooter.ui.annotation_toolbar import AnnotationToolbar
from screenshooter.ui.image_toolbar import ImageToolbar
from screenshooter.ui.options_toolbar import OptionsToolbar
from screenshooter.widgets.thickness import ThicknessWidget


@pytest.fixture
def app(qapp):
    app = ScreenshotApp()
    pm = QPixmap(100, 80)
    pm.fill(QColor("gray"))
    app.view.set_background_from_pixmap(pm)
    yield app
    app.close()


def test_window_minimum_width_is_dynamic(app):
    min_width = app.minimumWidth()
    assert min_width > 0


def test_editor_toolbar_strip_has_two_separators(app):
    strip = app.editor_toolbar_strip
    separators = strip.findChildren(ToolbarSeparator)
    assert len(separators) == 2


def test_thickness_widget_has_no_fixed_width(app):
    tw = app.thickness_widget
    assert tw.sizePolicy().horizontalPolicy() == tw.sizePolicy().Expanding


def test_editor_toolbar_strip_minimum_width_sufficient(app):
    strip = app.editor_toolbar_strip
    ann = strip.findChild(AnnotationToolbar)
    img = strip.findChild(ImageToolbar)
    opt = strip.findChild(OptionsToolbar)

    assert ann is not None
    assert img is not None
    assert opt is not None

    sum_min = ann.minimumSizeHint().width() + img.minimumSizeHint().width() + opt.minimumSizeHint().width()
    # добавляем ширину двух разделителей (получаем фактическую)
    separators = strip.findChildren(ToolbarSeparator)
    sep_width = sum(s.minimumSizeHint().width() for s in separators)
    expected_min = sum_min + sep_width

    assert strip.minimumSizeHint().width() >= expected_min