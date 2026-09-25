"""
Регрессия размещения снимков выбранного экрана на существующей подложке.
"""

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import QGraphicsScene

from screenshooter.view import EditorView


def test_screen_capture_is_60_percent_of_background_and_centered(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)

    background = QPixmap(200, 100)
    background.fill(QColor("gray"))
    view.set_background_from_pixmap(background)

    captured = QPixmap(50, 50)
    captured.fill(QColor("blue"))

    item = view.add_pasted_image(captured, screen_capture=True)

    rect = item.mapRectToScene(item.boundingRect())
    background_rect = view.background_item.sceneBoundingRect()

    assert rect.width() == 60
    assert rect.height() == 60
    assert rect.center() == background_rect.center()
    assert rect.topLeft() == QPointF(70, 20)
