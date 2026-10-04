import pytest
from PyQt5.QtWidgets import QApplication, QDialogButtonBox, QGroupBox

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
    assert dialog.enhancer_enabled_check.isChecked() is True
    assert dialog.enhancer_scale_combo.currentData() == "auto"
    assert dialog.enhancer_color_combo.currentData() == "auto"

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


def test_settings_dialog_uses_save_and_cancel_labels(qapp):
    class FakeSettings:
        theme = "system"
        save_directory = ""

        @staticmethod
        def is_autostart_enabled():
            return False

    dialog = SettingsDialog(FakeSettings())

    buttons = dialog.findChildren(QDialogButtonBox)
    assert buttons
    assert buttons[0].button(QDialogButtonBox.Ok).text() == "Сохранить"
    assert buttons[0].button(QDialogButtonBox.Cancel).text() == "Отмена"

    dialog.reject()
