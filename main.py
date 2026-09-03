"""
Модуль: main.py
Описание: Точка входа в приложение «Скриншотер с редактором аннотаций».
          Настраивает High DPI, создаёт QApplication и главное окно,
          обрабатывает аргумент --hidden для запуска в фоне.
          Реализует защиту от запуска второй копии через QLockFile.
"""

import sys
import os
import ctypes
import tempfile
import platform

from PyQt5.QtCore import Qt, QCoreApplication, QLockFile
from PyQt5.QtWidgets import QApplication, QMessageBox

# Устанавливаем идентификатор приложения для корректной иконки в панели задач
# Только для Windows
if platform.system() == "Windows":
    app_id = "Screenshooter.App.1.0"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screenshooter.app import ScreenshotApp
from screenshooter.window_manager import WindowManager
from screenshooter.hotkey_manager import HotkeyManager
from screenshooter.utils import load_app_icon


def get_lock_file_path():
    """Возвращает путь к файлу блокировки для предотвращения второго экземпляра."""
    # Для Windows используем %TEMP%/Screenshooter.lock
    # Для Linux/macOS используем /tmp/Screenshooter.lock
    temp_dir = tempfile.gettempdir()
    return os.path.join(temp_dir, "Screenshooter.lock")


def try_acquire_lock():
    """
    Пытается получить блокировку приложения.

    Returns:
        tuple: (QLockFile или None, success: bool, error_message: str или None)
    """
    lock_path = get_lock_file_path()
    lock_file = QLockFile(lock_path)
    lock_file.setStaleLockTime(60000)

    if lock_file.tryLock():
        return lock_file, True, None

    return None, False, "Другой экземпляр приложения уже запущен."


def main():
    # Пытаемся получить блокировку ДО создания QApplication
    lock_file, success, error_message = try_acquire_lock()

    if not success:
        # Показываем сообщение об ошибке
        # Создаём минимальный QApplication для показа диалога
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Ошибка запуска",
            f"{error_message}\n\nПожалуйста, закройте существующее окно приложения перед запуском новой копии."
        )
        sys.exit(1)

    # Блокировка получена успешно — создаём полноценное приложение
    app = QApplication(sys.argv)
    # Окна редактора могут быть скрыты в трее во время захвата.
    app.setQuitOnLastWindowClosed(False)

    # Устанавливаем иконку приложения глобально
    app.setWindowIcon(load_app_icon())

    window_manager = WindowManager(app)
    window = window_manager.create_editor_window(reusable=True)
    hotkey_manager = HotkeyManager(window_manager, app)
    window_manager.hotkey_manager = hotkey_manager
    for editor_window in window_manager.windows:
        editor_window._hotkey_manager = hotkey_manager
    app.aboutToQuit.connect(hotkey_manager.cleanup)

    # Если приложение запущено с флагом --hidden — не показываем окно
    if '--hidden' not in sys.argv:
        window.show()
    else:
        window.hide()

    # lock_file должен оставаться в памяти до завершения приложения
    # Сохраняем ссылку в app для предотвращения сборки мусором
    app._lock_file = lock_file

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()