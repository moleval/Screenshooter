"""Register/unregister and inspect the Screenshooter Explorer menu."""

import ntpath
import os

try:
    import winreg
except ImportError:  # pragma: no cover - only available on Windows
    winreg = None


EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")
REGISTRY_ROOT = r"Software\Classes\SystemFileAssociations"
MENU_KEY = r"shell\Screenshooter"
MENU_LABEL = "Screenshooter"
EXPECTED_EXECUTABLE = r"D:\Screenshooter\Screenshooter.exe"
EXPECTED_COMMAND = f'"{EXPECTED_EXECUTABLE}" "%1"'
EXPECTED_ICON = f'"{EXPECTED_EXECUTABLE}",0'

STATUS_NOT_INSTALLED = "NOT_INSTALLED"
STATUS_INSTALLED = "INSTALLED"
STATUS_PARTIAL = "PARTIAL"
STATUS_BROKEN = "BROKEN"
STATUS_UNAVAILABLE = "UNAVAILABLE"


def _normalize_windows_path(path):
    """Normalize a Windows path for case-insensitive comparison."""
    return ntpath.normcase(ntpath.normpath(path.strip().strip('"')))


def _read_default_value(key):
    return winreg.QueryValueEx(key, "")[0]


def _registry_key_path(extension):
    return REGISTRY_ROOT + "\\" + extension + "\\" + MENU_KEY


def get_classic_menu_status(executable_path=EXPECTED_EXECUTABLE):
    """Inspect the current user's classic menu registration without modifying it."""
    report = {
        "status": STATUS_UNAVAILABLE,
        "enabled": False,
        "expected_executable": executable_path,
        "extensions": {},
        "issues": [],
    }
    if winreg is None:
        report["issues"].append("Модуль реестра Windows недоступен.")
        return report

    expected_command = f'"{executable_path}" "%1"'
    expected_icon = _normalize_windows_path(executable_path)
    present_count = 0
    all_valid = True

    for extension in EXTENSIONS:
        key_path = _registry_key_path(extension)
        details = {
            "registered": False,
            "command_exists": False,
            "label": None,
            "command": None,
            "command_valid": False,
            "icon": None,
            "icon_valid": False,
            "executable_exists": os.path.isfile(executable_path),
            "issues": [],
        }
        report["extensions"][extension] = details

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as menu_key:
                details["registered"] = True
                present_count += 1
                try:
                    details["label"] = _read_default_value(menu_key)
                except FileNotFoundError:
                    details["issues"].append("Не задано название пункта меню.")
                try:
                    details["icon"] = winreg.QueryValueEx(menu_key, "Icon")[0]
                    icon_path = details["icon"].rsplit(",", 1)[0]
                    details["icon_valid"] = (
                        _normalize_windows_path(icon_path) == expected_icon
                    )
                    if not details["icon_valid"]:
                        details["issues"].append("Путь к иконке не соответствует EXE.")
                except FileNotFoundError:
                    details["issues"].append("Не задан значок пункта меню.")

            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, key_path + r"\command"
                ) as command_key:
                    details["command_exists"] = True
                    details["command"] = _read_default_value(command_key)
                    details["command_valid"] = (
                        details["command"].strip().casefold()
                        == expected_command.casefold()
                    )
                    if not details["command_valid"]:
                        details["issues"].append(
                            "Команда запуска не соответствует ожидаемой."
                        )
            except FileNotFoundError:
                details["issues"].append("Отсутствует подраздел command.")
        except FileNotFoundError:
            details["issues"].append("Пункт меню для расширения не зарегистрирован.")
        except OSError as error:
            report["issues"].append(
                f"Не удалось прочитать реестр для {extension}: {error}"
            )
            return report

        if details["registered"]:
            if details["label"] != MENU_LABEL:
                details["issues"].append("Название пункта меню некорректно.")
            if not details["executable_exists"]:
                details["issues"].append("Исполняемый файл Screenshooter.exe не найден.")
            if details["issues"]:
                all_valid = False

    if present_count == 0:
        report["status"] = STATUS_NOT_INSTALLED
        report["issues"].append("Классическая интеграция не обнаружена.")
    elif present_count < len(EXTENSIONS):
        report["status"] = STATUS_PARTIAL
        report["issues"].append(
            f"Зарегистрировано расширений: {present_count} из {len(EXTENSIONS)}."
        )
    elif all_valid:
        report["status"] = STATUS_INSTALLED
        report["enabled"] = True
    else:
        report["status"] = STATUS_BROKEN

    for extension, details in report["extensions"].items():
        for issue in details["issues"]:
            report["issues"].append(f"{extension}: {issue}")

    return report


def is_context_menu_enabled():
    """Return True only when the complete classic menu registration is valid."""
    return get_classic_menu_status()["status"] == STATUS_INSTALLED


def _delete_value_if_owned(key, name, expected):
    """Delete a value only when it still contains the exact value we own."""
    try:
        current = winreg.QueryValueEx(key, name)[0]
    except FileNotFoundError:
        return
    if current == expected:
        winreg.DeleteValue(key, name)


def _registration_has_conflict(key_path, value_name, expected):
    """Return True if an existing value is not one of our expected values."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            current = winreg.QueryValueEx(key, value_name)[0]
    except FileNotFoundError:
        return False
    return current != expected


def set_context_menu_enabled(enabled):
    """Register or remove only our known values for the current Windows user.

    Registration is idempotent. If a write fails partway through, already
    completed entries are left in place and can be repaired by retrying.
    Removal never deletes a registry key or an unknown value/subkey.
    """
    if winreg is None:
        return False

    try:
        if enabled:
            # Preflight every target before the first write. Never overwrite an
            # existing value whose ownership cannot be established.
            for extension in EXTENSIONS:
                key_path = _registry_key_path(extension)
                if (
                    _registration_has_conflict(key_path, "", MENU_LABEL)
                    or _registration_has_conflict(key_path, "Icon", EXPECTED_ICON)
                    or _registration_has_conflict(
                        key_path + r"\command", "", EXPECTED_COMMAND
                    )
                ):
                    return False

            for extension in EXTENSIONS:
                key_path = _registry_key_path(extension)
                with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    key_path,
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, MENU_LABEL)
                    winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, EXPECTED_ICON)
                with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    key_path + r"\command",
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.SetValueEx(
                        key, "", 0, winreg.REG_SZ, EXPECTED_COMMAND
                    )
        else:
            for extension in EXTENSIONS:
                key_path = _registry_key_path(extension)
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        key_path,
                        0,
                        winreg.KEY_SET_VALUE,
                    ) as key:
                        _delete_value_if_owned(key, "", MENU_LABEL)
                        _delete_value_if_owned(key, "Icon", EXPECTED_ICON)
                except FileNotFoundError:
                    pass

                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        key_path + r"\command",
                        0,
                        winreg.KEY_SET_VALUE,
                    ) as key:
                        _delete_value_if_owned(key, "", EXPECTED_COMMAND)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
