"""
Модуль: main.py
Описание: Точка входа в приложение «Скриншотер с редактором аннотаций».
          Настраивает High DPI, создаёт QApplication и главное окно,
          обрабатывает аргумент --hidden для запуска в фоне.
"""

import sys
import os
import ctypes

from PyQt5.QtCore import Qt, QCoreApplication

# Включаем High DPI scaling ДО создания QApplication
QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# Устанавливаем идентификатор приложения для корректной иконки в панели задач
app_id = "Screenshooter.App.1.0"
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from screenshooter.app import ScreenshotApp
from screenshooter.utils import load_app_icon


def main():
    app = QApplication(sys.argv)

    # Устанавливаем иконку приложения глобально
    app.setWindowIcon(load_app_icon())

    window = ScreenshotApp()

    # Если приложение запущено с флагом --hidden — не показываем окно
    if '--hidden' not in sys.argv:
        window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()