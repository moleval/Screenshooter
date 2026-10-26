"""Register/unregister the Screenshooter item in the current user's Explorer menu."""

import os
import subprocess
import sys

try:
    import winreg
except ImportError:  # pragma: no cover - only available on Windows
    winreg = None


EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")
REGISTRY_ROOT = r"Software\Classes\SystemFileAssociations"
MENU_KEY = r"shell\Screenshooter"
MENU_LABEL = "Открыть в Скриншутере"


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


def is_context_menu_enabled():
    """Return True if our menu item is registered for every supported format."""
    if winreg is None:
        return False
    try:
        for extension in EXTENSIONS:
            key_path = REGISTRY_ROOT + "\\" + extension + "\\" + MENU_KEY
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path):
                pass
        return True
    except OSError:
        return False


def set_context_menu_enabled(enabled):
    """Register or remove the menu item for the current Windows user only."""
    if winreg is None:
        return False

    try:
        if enabled:
            command = _command()
            for extension in EXTENSIONS:
                key_path = REGISTRY_ROOT + "\\" + extension + "\\" + MENU_KEY
                with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    key_path,
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, MENU_LABEL)
                with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    key_path + r"\command",
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
        else:
            for extension in EXTENSIONS:
                key_path = REGISTRY_ROOT + "\\" + extension + "\\" + MENU_KEY
                try:
                    winreg.DeleteKey(
                        winreg.HKEY_CURRENT_USER, key_path + r"\command"
                    )
                except FileNotFoundError:
                    pass
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
