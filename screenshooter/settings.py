"""
Модуль: settings.py
Описание: Настройки приложения.
          Загружает и сохраняет пользовательские настройки в ini-файле.
          Использует configparser для читаемого формата с комментариями.
          Управляет автозагрузкой через создание/удаление ярлыка
          в папке автозагрузки Windows (Shell:Startup), без реестра.
"""

import os
import sys
import configparser

# Импортируем Dispatch, чтобы сразу увидеть ошибку, если pywin32 нет
try:
    from win32com.client import Dispatch
    _HAS_WIN32COM = True
except ImportError:
    _HAS_WIN32COM = False


class AppSettings:
    """
    Единый источник настроек приложения.

    INI-файл создаётся рядом с исполняемым файлом (при сборке)
    или рядом с пакетом (при разработке).

    Формат файла:

        ; ============================================
        ; Настройки приложения Screenshooter
        ; ============================================

        [General]
        save_directory = D:/Screenshots

        [Theme]
        theme = system

    Автозагрузка управляется ярлыком в папке Startup,
    а не через реестр.
    """

    CONFIG_FILENAME = "screenshooter.ini"

    def __init__(self):
        self.config_path = self._get_config_path()
        self.config = configparser.ConfigParser()

        # Загружаем существующий файл или создаём новый
        self.load()

    # --------------------------------------------------------------
    # Путь к ini-файлу
    # --------------------------------------------------------------
    @staticmethod
    def _get_config_path():
        """Возвращает путь к ini-файлу."""
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, AppSettings.CONFIG_FILENAME)

    # --------------------------------------------------------------
    # Загрузка / сохранение
    # --------------------------------------------------------------
    def load(self):
        """Загружает настройки из ini-файла."""
        if not os.path.exists(self.config_path):
            # Создаём файл с шапкой, если его нет
            self._create_default_config()

        self.config.read(self.config_path, encoding='utf-8')

        # Читаем настройки с значениями по умолчанию
        self.save_directory = self.config.get(
            'General', 'save_directory', fallback=''
        )
        self.theme = self.config.get('Theme', 'theme', fallback='system')

        # Автозагрузка определяется наличием ярлыка
        self.autostart = self.is_autostart_enabled()

    def save(self):
        """Сохраняет настройки в ini-файл."""
        if not self.config.has_section('General'):
            self.config.add_section('General')
        if not self.config.has_section('Theme'):
            self.config.add_section('Theme')

        self.config.set('General', 'save_directory', self.save_directory)
        self.config.set('Theme', 'theme', self.theme)

        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)

        self.autostart = self.is_autostart_enabled()

    def _create_default_config(self):
        """Создаёт новый ini-файл с шапкой и настройками по умолчанию."""
        config = configparser.ConfigParser()
        config['General'] = {'save_directory': ''}
        config['Theme'] = {'theme': 'system'}

        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.write("; ============================================\n")
            f.write("; Настройки приложения Screenshooter\n")
            f.write("; ============================================\n")
            f.write("\n")
            config.write(f)

    # --------------------------------------------------------------
    # Удобные сеттеры
    # --------------------------------------------------------------
    def set_save_directory(self, directory):
        self.save_directory = directory
        self.save()

    def set_theme(self, theme):
        self.theme = theme
        self.save()

    # --------------------------------------------------------------
    # Управление автозагрузкой (ярлык в Startup)
    # --------------------------------------------------------------
    def _get_startup_dir(self):
        """Возвращает путь к папке автозагрузки Windows."""
        appdata = os.getenv('APPDATA', '')
        return os.path.join(
            appdata,
            'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
        )

    def _get_shortcut_path(self):
        """Возвращает полный путь к ярлыку автозагрузки."""
        return os.path.join(self._get_startup_dir(), 'Screenshooter.lnk')

    def is_autostart_enabled(self):
        """Проверяет, существует ли ярлык автозагрузки."""
        return os.path.exists(self._get_shortcut_path())

    def create_autostart_shortcut(self):
        """Создаёт ярлык в папке автозагрузки."""
        if not _HAS_WIN32COM:
            print("Ошибка: pywin32 не установлен. Ярлык не может быть создан.")
            return False

        try:
            startup_dir = self._get_startup_dir()
            if not os.path.isdir(startup_dir):
                print(f"Папка автозагрузки не найдена: {startup_dir}")
                return False

            shortcut_path = self._get_shortcut_path()
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)

            if getattr(sys, 'frozen', False):
                target = sys.executable
                arguments = '--hidden'
                working_dir = os.path.dirname(sys.executable)
                icon_location = sys.executable
            else:
                target = sys.executable
                main_script = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    '..', 'main.py'
                )
                arguments = main_script
                working_dir = os.path.dirname(main_script)
                icon_location = sys.executable

            shortcut.Targetpath = target
            shortcut.Arguments = arguments
            shortcut.WorkingDirectory = working_dir
            shortcut.IconLocation = icon_location
            shortcut.save()

            self.autostart = True
            print(f"Ярлык автозагрузки создан: {shortcut_path}")
            return True

        except Exception as e:
            print(f"Ошибка создания ярлыка автозагрузки: {e}")
            return False

    def remove_autostart_shortcut(self):
        """Удаляет ярлык из папки автозагрузки."""
        try:
            path = self._get_shortcut_path()
            if os.path.exists(path):
                os.remove(path)
            self.autostart = False
            print(f"Ярлык автозагрузки удалён: {path}")
            return True
        except Exception as e:
            print(f"Ошибка удаления ярлыка автозагрузки: {e}")
            return False