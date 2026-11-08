"""Tests for read-only classic Explorer menu diagnostics."""

import pytest

from screenshooter import context_menu


class FakeRegistryKey:
    def __init__(self, values):
        self.values = values

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeWinreg:
    HKEY_CURRENT_USER = object()

    def __init__(self, values=None, denied_paths=()):
        self.values = values or {}
        self.denied_paths = set(denied_paths)

    def OpenKey(self, root, path):
        if path in self.denied_paths:
            raise PermissionError("access denied")
        if path not in self.values:
            raise FileNotFoundError(path)
        return FakeRegistryKey(self.values[path])

    @staticmethod
    def QueryValueEx(key, name):
        if name not in key.values:
            raise FileNotFoundError(name)
        return key.values[name], 1


def make_registry(*, missing_extension=None, bad_command=False, missing_command=False):
    values = {}
    command = f'"{context_menu.EXPECTED_EXECUTABLE}" "%1"'
    if bad_command:
        command = '"C:\\Other\\Screenshooter.exe" "%1"'

    for extension in context_menu.EXTENSIONS:
        if extension == missing_extension:
            continue
        menu_path = (
            context_menu.REGISTRY_ROOT
            + "\\"
            + extension
            + "\\"
            + context_menu.MENU_KEY
        )
        values[menu_path] = {
            "": context_menu.MENU_LABEL,
            "Icon": f'"{context_menu.EXPECTED_EXECUTABLE}",0',
        }
        if not (missing_command and extension == context_menu.EXTENSIONS[0]):
            values[menu_path + r"\command"] = {"": command}
    return values


@pytest.fixture
def registry(monkeypatch):
    fake = FakeWinreg()
    monkeypatch.setattr(context_menu, "winreg", fake)
    monkeypatch.setattr(context_menu.os.path, "isfile", lambda path: True)
    return fake


def test_status_is_not_installed_when_no_registry_entries(registry):
    result = context_menu.get_classic_menu_status()

    assert result["status"] == context_menu.STATUS_NOT_INSTALLED
    assert result["enabled"] is False
    assert all(
        details["registered"] is False
        for details in result["extensions"].values()
    )


def test_status_is_installed_when_all_entries_are_valid(registry):
    registry.values = make_registry()

    result = context_menu.get_classic_menu_status()

    assert result["status"] == context_menu.STATUS_INSTALLED
    assert result["enabled"] is True
    assert all(
        details["command_valid"] and details["icon_valid"]
        for details in result["extensions"].values()
    )
    assert context_menu.is_context_menu_enabled() is True


def test_status_is_partial_when_an_extension_is_missing(registry):
    registry.values = make_registry(missing_extension=".bmp")

    result = context_menu.get_classic_menu_status()

    assert result["status"] == context_menu.STATUS_PARTIAL
    assert result["enabled"] is False


def test_status_is_broken_when_command_is_invalid(registry):
    registry.values = make_registry(bad_command=True)

    result = context_menu.get_classic_menu_status()

    assert result["status"] == context_menu.STATUS_BROKEN
    assert result["enabled"] is False
    assert any(
        "Команда запуска" in issue
        for issue in result["extensions"][".png"]["issues"]
    )


def test_status_is_broken_when_executable_is_missing(registry, monkeypatch):
    registry.values = make_registry()
    monkeypatch.setattr(context_menu.os.path, "isfile", lambda path: False)

    result = context_menu.get_classic_menu_status()

    assert result["status"] == context_menu.STATUS_BROKEN
    assert all(
        details["executable_exists"] is False
        for details in result["extensions"].values()
    )


def test_status_is_unavailable_when_registry_access_is_denied(monkeypatch):
    denied = (
        context_menu.REGISTRY_ROOT
        + "\\"
        + context_menu.EXTENSIONS[0]
        + "\\"
        + context_menu.MENU_KEY
    )
    monkeypatch.setattr(
        context_menu, "winreg", FakeWinreg(denied_paths={denied})
    )

    result = context_menu.get_classic_menu_status()

    assert result["status"] == context_menu.STATUS_UNAVAILABLE
    assert result["enabled"] is False


def test_status_is_broken_when_command_subkey_is_missing(registry):
    registry.values = make_registry(missing_command=True)

    result = context_menu.get_classic_menu_status()

    assert result["status"] == context_menu.STATUS_BROKEN
    assert result["extensions"][".png"]["command_exists"] is False
    assert any(
        "подраздел command" in issue
        for issue in result["extensions"][".png"]["issues"]
    )
