import pytest
from PyQt5.QtWidgets import QApplication, QGroupBox

from screenshooter.settings_dialog import SettingsDialog


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def test_settings_dialog_uses_current_values(qapp, tmp_path):
    class FakeSettings:
        theme = "dark"
        save_directory = str(tmp_path)

        @staticmethod
        def is_autostart_enabled():
            return False

    dialog = SettingsDialog(FakeSettings())

    assert dialog.theme_combo.currentData() == "dark"
    assert dialog.save_directory_edit.text() == str(tmp_path)
    assert dialog.autostart_check.isChecked() is False

    dialog.reject()


def test_settings_dialog_has_adaptive_enhancer_section(qapp):
    class FakeSettings:
        theme = "system"
        save_directory = ""

        @staticmethod
        def is_autostart_enabled():
            return False

    dialog = SettingsDialog(FakeSettings())

    assert dialog.windowTitle() == "Настройки"
    assert any(
        widget.title() == "Адаптивный улучшайзер"
        for widget in dialog.findChildren(QGroupBox)
    )

    dialog.reject()
