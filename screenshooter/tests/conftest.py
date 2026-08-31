# tests/conftest.py
import sys
import pytest
from PyQt5.QtWidgets import QApplication

# Отключаем реальные глобальные хуки клавиатуры и системный трей,
# чтобы тесты могли работать в любой среде.
@pytest.fixture(autouse=True)
def disable_external_services(monkeypatch):
    monkeypatch.setattr("keyboard.add_hotkey", lambda *a, **k: None)
    monkeypatch.setattr("keyboard.hook_key", lambda *a, **k: lambda: None)
    monkeypatch.setattr("keyboard.unhook_key", lambda *a, **k: None)
    monkeypatch.setattr("keyboard.remove_hotkey", lambda *a, **k: None)

    # Заглушка для TrayManager, чтобы не создавать реальный QSystemTrayIcon.
    class FakeTrayManager:
        def __init__(self, *args, **kwargs):
            pass
        def show_message(self, *args, **kwargs):
            pass

    monkeypatch.setattr("screenshooter.tray.TrayManager", FakeTrayManager)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app