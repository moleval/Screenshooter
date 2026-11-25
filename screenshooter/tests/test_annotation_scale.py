import pytest
from PyQt5.QtWidgets import QApplication, QGraphicsScene

from screenshooter.view import EditorView
from screenshooter.items.text_item import TextItem


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def test_annotation_scale_changes_default_stroke_and_font(qapp):
    view = EditorView(QGraphicsScene())
    view.annotation_scale = 2.5
    assert view.scaled_pen_width() == pytest.approx(5.0)
    assert view.scaled_text_point_size() == 100


def test_text_annotation_padding_uses_scale(qapp):
    view = EditorView(QGraphicsScene())
    normal = TextItem(view)
    normal.setPlainText("Test")
    normal_rect = normal.boundingRect()
    view.annotation_scale = 2.0
    enlarged = TextItem(view)
    enlarged.setPlainText("Test")
    enlarged_rect = enlarged.boundingRect()
    assert enlarged_rect.width() - normal_rect.width() == pytest.approx(32.0)
