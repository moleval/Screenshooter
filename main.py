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

    # Пытаемся получить блокировку
    if lock_file.tryLock():
        return lock_file, True, None

    # Не удалось получить блокировку — проверяем, не завис ли процесс
    # QLockFile автоматически определяет, жив ли процесс, удерживающий блокировку
    # Если процесс мёртв, tryLock может не сработать из-за stale lock
    # В этом случае пытаемся удалить старый файл и получить блокировку снова

    # Проверяем возраст файла блокировки
    try:
        lock_info = lock_file.staleLockTime()
        # Если файл старше 60 секунд, считаем его зависшим и удаляем
        if lock_info > 60000:  # 60 секунд в миллисекундах
            os.remove(lock_path)
            # Пробуем снова
            if lock_file.tryLock():
                return lock_file, True, None
    except (OSError, AttributeError):
        # staleLockTime может быть недоступен в старых версиях Qt
        pass

    # Если всё ещё не удалось получить блокировку — значит, работает другой экземпляр
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

    # Устанавливаем иконку приложения глобально
    app.setWindowIcon(load_app_icon())

    window = ScreenshotApp()

    # Если приложение запущено с флагом --hidden — не показываем окно
    if '--hidden' not in sys.argv:
        window.show()

    # lock_file должен оставаться в памяти до завершения приложения
    # Сохраняем ссылку в app для предотвращения сборки мусором
    app._lock_file = lock_file

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()