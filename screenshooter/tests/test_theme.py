import pytest
from PyQt5.QtWidgets import QApplication

from screenshooter.theme import ThemeManager


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def test_dark_theme_makes_color_dialog_values_readable(qapp):
    manager = ThemeManager("dark")
    qss = manager.get_qss()

    assert "QSpinBox, QDoubleSpinBox" in qss
    assert "color: #ffffff;" in qss
    assert "QSpinBox QLineEdit, QDoubleSpinBox QLineEdit" in qss
