"""Tests for classic Explorer menu diagnostics and registry operations."""

import pytest

from screenshooter import context_menu


class FakeRegistryKey:
    def __init__(self, registry, path):
        self.registry = registry
        self.path = path

    @property
    def values(self):
        return self.registry.values[self.path]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeWinreg:
    HKEY_CURRENT_USER = object()
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self, values=None, denied_paths=(), fail_create_path=None):
        self.values = values or {}
        self.denied_paths = set(denied_paths)
        self.fail_create_path = fail_create_path

    def OpenKey(self, root, path, *args):
        if path in self.denied_paths:
            raise PermissionError("access denied")
        if path not in self.values:
            raise FileNotFoundError(path)
        return FakeRegistryKey(self, path)

    def CreateKeyEx(self, root, path, *args):
        if path == self.fail_create_path:
            raise PermissionError("write denied")
        self.values.setdefault(path, {})
        return FakeRegistryKey(self, path)

    @staticmethod
    def QueryValueEx(key, name):
        if name not in key.values:
            raise FileNotFoundError(name)
        return key.values[name], 1

    @staticmethod
    def SetValueEx(key, name, reserved, value_type, value):
        key.values[name] = value

    @staticmethod
    def DeleteValue(key, name):
        if name not in key.values:
            raise FileNotFoundError(name)
        del key.values[name]


def menu_path(extension):
    return (
        context_menu.REGISTRY_ROOT
        + "\\"
        + extension
        + "\\"
        + context_menu.MENU_KEY
    )


def make_registry(*, missing_extension=None, bad_command=False, missing_command=False):
    values = {}
    command = context_menu.EXPECTED_COMMAND
    if bad_command:
        command = '"C:\\Other\\Screenshooter.exe" "%1"'

    for extension in context_menu.EXTENSIONS:
        if extension == missing_extension:
            continue
        path = menu_path(extension)
        values[path] = {
            "": context_menu.MENU_LABEL,
            "Icon": context_menu.EXPECTED_ICON,
        }
        if not (missing_command and extension == context_menu.EXTENSIONS[0]):
            values[path + r"\command"] = {"": command}
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
    assert all(not item["registered"] for item in result["extensions"].values())


def test_status_is_installed_when_all_entries_are_valid(registry):
    registry.values = make_registry()
    result = context_menu.get_classic_menu_status()
    assert result["status"] == context_menu.STATUS_INSTALLED
    assert result["enabled"] is True
    assert all(
        item["command_valid"] and item["icon_valid"]
        for item in result["extensions"].values()
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
        item["executable_exists"] is False
        for item in result["extensions"].values()
    )


def test_status_is_unavailable_when_registry_access_is_denied(monkeypatch):
    denied = menu_path(context_menu.EXTENSIONS[0])
    monkeypatch.setattr(context_menu, "winreg", FakeWinreg(denied_paths={denied}))
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


def test_enable_registers_fixed_executable_for_every_extension(registry):
    assert context_menu.set_context_menu_enabled(True) is True
    for extension in context_menu.EXTENSIONS:
        path = menu_path(extension)
        assert registry.values[path][""] == context_menu.MENU_LABEL
        assert registry.values[path]["Icon"] == context_menu.EXPECTED_ICON
        assert registry.values[path + r"\command"][""] == (
            context_menu.EXPECTED_COMMAND
        )


def test_disable_removes_only_values_owned_by_screenshooter(registry):
    registry.values = make_registry()
    for extension in context_menu.EXTENSIONS:
        registry.values[menu_path(extension)]["ThirdParty"] = "keep-me"
        registry.values[menu_path(extension) + r"\command"]["Other"] = "keep-command"
    assert context_menu.set_context_menu_enabled(False) is True
    for extension in context_menu.EXTENSIONS:
        path = menu_path(extension)
        assert registry.values[path] == {"ThirdParty": "keep-me"}
        assert registry.values[path + r"\command"] == {"Other": "keep-command"}


def test_disable_does_not_remove_values_that_no_longer_match_ours(registry):
    registry.values = make_registry(bad_command=True)
    foreign_icon = '"C:\\Other\\app.exe",0'
    foreign_label = "Other application"
    for extension in context_menu.EXTENSIONS:
        registry.values[menu_path(extension)]["Icon"] = foreign_icon
        registry.values[menu_path(extension)][""] = foreign_label
    assert context_menu.set_context_menu_enabled(False) is True
    for extension in context_menu.EXTENSIONS:
        path = menu_path(extension)
        assert registry.values[path][""] == foreign_label
        assert registry.values[path]["Icon"] == foreign_icon
        assert registry.values[path + r"\command"][""] == (
            '"C:\\Other\\Screenshooter.exe" "%1"'
        )


def test_enable_reports_partial_write_failure(registry):
    failing_extension = context_menu.EXTENSIONS[1]
    registry.fail_create_path = menu_path(failing_extension)
    assert context_menu.set_context_menu_enabled(True) is False
    assert menu_path(context_menu.EXTENSIONS[0]) in registry.values
    assert menu_path(failing_extension) not in registry.values
