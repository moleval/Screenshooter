"""
Модуль: tray.py
Описание: Управление иконкой в системном трее и контекстным меню.
          Обеспечивает сворачивание в трей, переключение темы,
          управление автозагрузкой и выход из приложения.
"""

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication


class TrayManager(QObject):
    """
    Менеджер иконки в системном трее.

    Создаёт иконку, контекстное меню и обрабатывает действия пользователя.
    Работает с AppSettings для сохранения настроек.
    """

    def __init__(self, app):
        """
        :param app: главное окно приложения (ScreenshotApp)
        """
        super().__init__(app)
        self.app = app

        # Иконка: сначала пытаемся взять из окна, иначе — стандартная
        icon = self.app.windowIcon()
        if icon.isNull():
            icon = QIcon()

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("Скриншотер с редактором")

        # Строим контекстное меню
        self.menu = QMenu()
        self._build_menu()

        self.tray_icon.setContextMenu(self.menu)

        # Обработка кликов по иконке
        self.tray_icon.activated.connect(self._on_activated)

        self.tray_icon.show()

    # --------------------------------------------------------------
    # Построение меню
    # --------------------------------------------------------------
    def _build_menu(self):
        """Создаёт все пункты контекстного меню."""
        # Показать/Скрыть
        self.show_hide_action = QAction("Показать/Скрыть", self)
        self.show_hide_action.triggered.connect(self._toggle_window)
        self.menu.addAction(self.show_hide_action)

        self.menu.addSeparator()

        # Автозагрузка
        self.autostart_action = QAction("Автозагрузка", self)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(self.app.settings.is_autostart_enabled())
        self.autostart_action.toggled.connect(self._on_autostart_toggled)
        self.menu.addAction(self.autostart_action)

        # Подменю «Тема»
        self.theme_menu = self.menu.addMenu("Тема")
        self._build_theme_menu()

        # Выбор папки сохранения
        self.save_dir_action = QAction("Выбрать папку сохранения...", self)
        self.save_dir_action.triggered.connect(self._choose_save_directory)
        self.menu.addAction(self.save_dir_action)

        self.menu.addSeparator()

        # Выход
        self.quit_action = QAction("Выход", self)
        self.quit_action.triggered.connect(self._quit_app)
        self.menu.addAction(self.quit_action)

    def _build_theme_menu(self):
        """Создаёт подменю выбора темы."""
        self.theme_actions = {}

        themes = [
            ("light", "Светлая"),
            ("dark", "Тёмная"),
            ("system", "Системная"),
        ]

        current_theme = self.app.settings.theme

        for key, label in themes:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(current_theme == key)
            action.triggered.connect(lambda checked, k=key: self._on_theme_selected(k))
            self.theme_actions[key] = action
            self.theme_menu.addAction(action)

    # --------------------------------------------------------------
    # Обработчики действий меню
    # --------------------------------------------------------------
    def _toggle_window(self):
        """Показывает или скрывает главное окно."""
        if self.app.isVisible():
            self.app.hide()
        else:
            self.app.showNormal()
            self.app.raise_()
            self.app.activateWindow()

    def _on_autostart_toggled(self, enabled: bool):
        """Обрабатывает переключение автозагрузки."""
        if enabled:
            self.app.settings.create_autostart_shortcut()
        else:
            self.app.settings.remove_autostart_shortcut()
        # Обновляем чекбокс в соответствии с фактическим результатом
        self.autostart_action.setChecked(self.app.settings.is_autostart_enabled())

    def _on_theme_selected(self, theme_key: str):
        """Передаёт выбор темы в главное окно."""
        self.app.apply_theme(theme_key)
        self._update_theme_checks(theme_key)

    def _update_theme_checks(self, selected_key: str):
        """Обновляет чекбоксы подменю темы."""
        for key, action in self.theme_actions.items():
            action.setChecked(key == selected_key)

    def _choose_save_directory(self):
        """Открывает диалог выбора папки сохранения."""
        self.app.choose_save_directory()

    def _quit_app(self):
        """Полностью завершает приложение."""
        self.app.quit_app()

    # --------------------------------------------------------------
    # Обработка активации иконки
    # --------------------------------------------------------------
    def _on_activated(self, reason):
        """Обрабатывает клики по иконке в трее."""
        if reason == QSystemTrayIcon.Trigger:          # Одинарный клик
            self._toggle_window()
        elif reason == QSystemTrayIcon.DoubleClick:    # Двойной клик
            self.app.showNormal()
            self.app.raise_()
            self.app.activateWindow()

    # --------------------------------------------------------------
    # Вспомогательные методы
    # --------------------------------------------------------------
    def show_message(self, title: str, message: str):
        """Показывает всплывающее сообщение в трее."""
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 3000)