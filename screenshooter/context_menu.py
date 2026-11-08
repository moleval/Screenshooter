"""Register/unregister and inspect the Screenshooter Explorer menu."""

import ntpath
import os
import subprocess
import sys

try:
    import winreg
except ImportError:  # pragma: no cover - only available on Windows
    winreg = None


EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")
REGISTRY_ROOT = r"Software\\Classes\\SystemFileAssociations"
MENU_KEY = r"shell\\Screenshooter"
MENU_LABEL = "Screenshooter"
EXPECTED_EXECUTABLE = r"D:\\Screenshooter\\Screenshooter.exe"

STATUS_NOT_INSTALLED = "NOT_INSTALLED"
STATUS_INSTALLED = "INSTALLED"
STATUS_PARTIAL = "PARTIAL"
STATUS_BROKEN = "BROKEN"
STATUS_UNAVAILABLE = "UNAVAILABLE"


def _application_icon_path():
    """Return the icon path used by Explorer for the context-menu item."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}",0'
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "resources", "icon.ico")
    )


def _command():
    """Build a quoted command that also works when running from source."""
    if getattr(sys, "frozen", False):
        executable = sys.executable
        arguments = ['"%1"']
    else:
        executable = sys.executable
        main_script = os.path.abspath(
            os.path.join(os.path.dirname(__file__), os.pardir, "main.py")
        )
        arguments = [subprocess.list2cmdline([main_script]), '"%1"']
    return subprocess.list2cmdline([executable]) + " " + " ".join(arguments)


def _normalize_windows_path(path):
    return ntpath.normcase(ntpath.normpath(path.strip().strip('"')))


def _read_default_value(key):
    return winreg.QueryValueEx(key, "")[0]


def get_classic_menu_status(executable_path=EXPECTED_EXECUTABLE):
    """Inspect the current user's classic menu registration without modifying it.

    The returned dictionary contains an overall status, per-extension details,
    and human-readable issues. Registry access errors are reported as
    UNAVAILABLE; missing keys and values are treated as registration findings.
    """
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
        key_path = REGISTRY_ROOT + "\\\\" + extension + "\\\\" + MENU_KEY
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
                    winreg.HKEY_CURRENT_USER, key_path + r"\\command"
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
            report["status"] = STATUS_UNAVAILABLE
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


def set_context_menu_enabled(enabled):
    """Register or remove the menu item for the current Windows user only."""
    if winreg is None:
        return False

    try:
        if enabled:
            command = _command()
            icon_path = _application_icon_path()
            for extension in EXTENSIONS:
                key_path = REGISTRY_ROOT + "\\\\" + extension + "\\\\" + MENU_KEY
                with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    key_path,
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, MENU_LABEL)
                    # Explorer reads a verb's icon from the "Icon" value on the
                    # verb key; a nested "DefaultIcon" key is not the right form.
                    winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon_path)
                with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    key_path + r"\\command",
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
                # Remove the legacy misplaced icon subkey if an older version made it.
                try:
                    winreg.DeleteKey(
                        winreg.HKEY_CURRENT_USER, key_path + r"\\DefaultIcon"
                    )
                except FileNotFoundError:
                    pass
        else:
            for extension in EXTENSIONS:
                key_path = REGISTRY_ROOT + "\\\\" + extension + "\\\\" + MENU_KEY
                for child_key in (r"\\command", r"\\DefaultIcon"):
                    try:
                        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path + child_key)
                    except FileNotFoundError:
                        pass
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
                    ) as key:
                        try:
                            winreg.DeleteValue(key, "Icon")
                        except FileNotFoundError:
                            pass
                except FileNotFoundError:
                    pass
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
