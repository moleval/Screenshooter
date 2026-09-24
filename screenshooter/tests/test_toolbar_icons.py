import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAction, QApplication, QActionGroup, QToolButton

from screenshooter.ui.annotation_toolbar import AnnotationToolbar
from screenshooter.ui.image_toolbar import ImageToolbar
from screenshooter.widgets.icon_manager import IconManager


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize(
    "toolbar_cls",
    [AnnotationToolbar, ImageToolbar],
)
def test_toolbar_buttons_are_36px_icon_only(qapp, toolbar_cls):
    actions = []
    group = QActionGroup(qapp)
    group.setExclusive(True)

    for name in ("pointer", "crop"):
        action = QAction(qapp)
        action.setCheckable(True)
        action.setIcon(IconManager.icon(name))
        group.addAction(action)
        actions.append(action)

    toolbar = toolbar_cls(actions)
    buttons = toolbar.findChildren(QToolButton)

    assert buttons
    for button in buttons:
        assert button.width() == 36
        assert button.height() == 36
        assert button.toolButtonStyle() == Qt.ToolButtonIconOnly
