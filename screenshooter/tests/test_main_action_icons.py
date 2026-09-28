import pytest
from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QApplication

from screenshooter.ui.layout_metrics import MAIN_ACTION_ICON_SIZE, TOOLBAR_CONTROL_HEIGHT
from screenshooter.widgets.icon_manager import IconManager

@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])

def test_main_action_icon_set_is_available(qapp):
    names = ("undo","redo","screen-1","screen-2","clear","clipboard-copy","image-plus","clipboard-paste","save-all","save","help")
    for name in names:
        icon = IconManager.icon(name, size=MAIN_ACTION_ICON_SIZE)
        assert icon.actualSize(QSize(100, 100)) == QSize(MAIN_ACTION_ICON_SIZE, MAIN_ACTION_ICON_SIZE)

def test_main_action_button_metrics_are_explicit():
    assert TOOLBAR_CONTROL_HEIGHT == 26
    assert MAIN_ACTION_ICON_SIZE > 0
