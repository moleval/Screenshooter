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
MENU_LABEL = "Screenshooter"


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
            icon_path = _application_icon_path()
            for extension in EXTENSIONS:
                key_path = REGISTRY_ROOT + "\\" + extension + "\\" + MENU_KEY
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
                    key_path + r"\command",
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
                # Remove the legacy misplaced icon subkey if an older version made it.
                try:
                    winreg.DeleteKey(
                        winreg.HKEY_CURRENT_USER, key_path + r"\DefaultIcon"
                    )
                except FileNotFoundError:
                    pass
        else:
            for extension in EXTENSIONS:
                key_path = REGISTRY_ROOT + "\\" + extension + "\\" + MENU_KEY
                for child_key in (r"\command", r"\DefaultIcon"):
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
