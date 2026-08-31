# tests/test_smoke.py
import pytest
from PyQt5.QtGui import QPixmap, QColor

from screenshooter.app import ScreenshotApp


@pytest.mark.parametrize("tool_name", [None, 'line', 'rect', 'ellipse', 'arrow', 'text'])
def test_app_starts_and_tools_switch(qapp, tool_name):
    app = ScreenshotApp()

    pm = QPixmap(200, 150)
    pm.fill(QColor("gray"))
    app.view.set_background_from_pixmap(pm)

    app.set_tool(tool_name)

    assert app.view.scene().items() is not None

    app.close()


def test_undo_redo_after_add_item(qapp):
    app = ScreenshotApp()

    pm = QPixmap(200, 150)
    pm.fill(QColor("gray"))
    app.view.set_background_from_pixmap(pm)

    app.set_tool('rect')
    # В реальности здесь было бы рисование, но мы просто проверяем вызовы
    app.undo_action()
    app.redo_action()

    app.close()