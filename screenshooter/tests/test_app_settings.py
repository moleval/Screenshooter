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


def test_save_and_load(temp_config):
    settings = AppSettings()
    settings.save_directory = "C:/test"
    settings.theme = "dark"
    settings.save()

    settings2 = AppSettings()
    assert settings2.save_directory == "C:/test"
    assert settings2.theme == "dark"


def test_autostart_shortcut_create_and_remove(temp_config, monkeypatch):
    # Мокаем win32com.client.Dispatch
    class FakeShortcut:
        def __init__(self):
            self.Targetpath = None
            self.Arguments = None
            self.WorkingDirectory = None
            self.IconLocation = None

        def save(self):
            pass

    class FakeShell:
        def CreateShortCut(self, path):
            return FakeShortcut()

    fake_dispatch = lambda prog_id: FakeShell()

    # Подменяем модуль win32com.client, если он не установлен
    import types
    fake_module = types.ModuleType("win32com.client")
    fake_module.Dispatch = fake_dispatch
    sys.modules["win32com.client"] = fake_module

    # ВАЖНО: подменяем флаг _HAS_WIN32COM, иначе код решит, что win32com нет
    monkeypatch.setattr("screenshooter.settings._HAS_WIN32COM", True)

    settings = AppSettings()
    assert settings.create_autostart_shortcut() is True
    assert settings.is_autostart_enabled() is True

    assert settings.remove_autostart_shortcut() is True
    assert settings.is_autostart_enabled() is False