"""
Тесты для AppSettings: загрузка/сохранение ini-файла,
управление автозагрузкой (мокаем win32com).
"""

import os
import sys
import pytest
from PyQt5.QtCore import QSettings

from screenshooter.settings import AppSettings


@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    """Создаёт временный ini-файл и подменяет путь к нему."""
    config_path = tmp_path / "test_settings.ini"

    def fake_get_config_path(self):
        return str(config_path)

    monkeypatch.setattr(AppSettings, "_get_config_path", fake_get_config_path)
    return config_path


def test_default_values(temp_config):
    settings = AppSettings()
    assert settings.save_directory == ""
    assert settings.theme == "system"
    assert settings.enhancer_enabled is False
    assert settings.enhancer_scale == "auto"
    assert settings.enhancer_text is True
    assert settings.enhancer_lines is True
    assert settings.enhancer_ui is True
    assert settings.enhancer_geometry is True
    assert settings.enhancer_color_mode == "auto"


def test_save_and_load(temp_config):
    settings = AppSettings()
    settings.save_directory = "C:/test"
    settings.theme = "dark"
    settings.save()

    settings2 = AppSettings()
    assert settings2.save_directory == "C:/test"
    assert settings2.theme == "dark"
    assert settings2.enhancer_enabled is False
    assert settings2.enhancer_scale == "auto"
    assert settings2.enhancer_color_mode == "auto"


def test_monochrome_color_mode_is_saved_and_legacy_invert_is_migrated(temp_config):
    settings = AppSettings()
    settings.enhancer_color_mode = "monochrome"
    settings.save()

    settings2 = AppSettings()
    assert settings2.enhancer_color_mode == "monochrome"

    temp_config.write_text(
        "[General]\n"
        "save_directory = \n"
        "\n"
        "[Theme]\n"
        "theme = system\n"
        "\n"
        "[Enhancer]\n"
        "color_mode = invert\n",
        encoding="utf-8",
    )
    settings3 = AppSettings()
    assert settings3.enhancer_color_mode == "monochrome"

def test_autostart_shortcut_create_and_remove(temp_config, monkeypatch):
    class FakeShortcut:
        def __init__(self, path):
            self.path = path
            self.Targetpath = None
            self.Arguments = None
            self.WorkingDirectory = None
            self.IconLocation = None

        def save(self):
            # Реально создаём файл, чтобы is_autostart_enabled() вернул True
            with open(self.path, 'w', encoding='utf-8') as f:
                f.write('')

    class FakeShell:
        def CreateShortCut(self, path):
            return FakeShortcut(path)

    fake_dispatch = lambda prog_id: FakeShell()

    # Подменяем Dispatch в самом модуле screenshooter.settings
    monkeypatch.setattr("screenshooter.settings.Dispatch", fake_dispatch)
    # Гарантируем, что флаг _HAS_WIN32COM True
    monkeypatch.setattr("screenshooter.settings._HAS_WIN32COM", True)
    # Подменяем путь к ярлыку на временный
    shortcut_path = temp_config.parent / "Screenshooter.lnk"
    monkeypatch.setattr(AppSettings, "_get_shortcut_path", lambda self: str(shortcut_path))

    settings = AppSettings()

    assert settings.create_autostart_shortcut() is True
    assert settings.is_autostart_enabled() is True

    assert settings.remove_autostart_shortcut() is True
    assert settings.is_autostart_enabled() is False