"""
Модуль: tray.py
Описание: Управление иконкой в системном трее и контекстным меню.
"""

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication


class TrayManager(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.app = app

        icon = self.app.windowIcon()
        if icon.isNull():
            icon = QIcon()

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("Скриншотер с редактором")

        self.menu = QMenu()
        self._build_menu()

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self._on_activated)
        self.tray_icon.show()

    def _build_menu(self):
        self.show_hide_action = QAction("Показать/Скрыть", self)
        self.show_hide_action.triggered.connect(self._toggle_window)
        self.menu.addAction(self.show_hide_action)

        self.menu.addSeparator()

        self.autostart_action = QAction("Автозагрузка", self)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(self.app.settings.is_autostart_enabled())
        self.autostart_action.toggled.connect(self._on_autostart_toggled)
        self.menu.addAction(self.autostart_action)

        self.theme_menu = self.menu.addMenu("Тема")
        self._build_theme_menu()

        self.save_dir_action = QAction("Выбрать папку сохранения...", self)
        self.save_dir_action.triggered.connect(self._choose_save_directory)
        self.menu.addAction(self.save_dir_action)

        self.menu.addSeparator()

        self.quit_action = QAction("Выход", self)
        self.quit_action.triggered.connect(self._quit_app)
        self.menu.addAction(self.quit_action)

    def _build_theme_menu(self):
        self.theme_actions = {}
        themes = [("light", "Светлая"), ("dark", "Тёмная"), ("system", "Системная")]
        current_theme = self.app.settings.theme
        for key, label in themes:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(current_theme == key)
            action.triggered.connect(lambda checked, k=key: self._on_theme_selected(k))
            self.theme_actions[key] = action
            self.theme_menu.addAction(action)

    def _toggle_window(self):
        if self.app.isVisible():
            self.app.hide()
        else:
            self.app.show_from_tray()

    def _on_autostart_toggled(self, enabled: bool):
        if enabled:
            success = self.app.settings.create_autostart_shortcut()
        else:
            success = self.app.settings.remove_autostart_shortcut()

        self.autostart_action.setChecked(self.app.settings.is_autostart_enabled())

        if success:
            msg = "Автозагрузка включена" if enabled else "Автозагрузка выключена"
            # Индикация в системном трее
            self.tray_icon.showMessage(
                "Скриншотер",
                msg,
                QSystemTrayIcon.Information,
                2000
            )
            # Индикация в строке состояния окна программы
            self.app.view.show_status_message(msg, 3000)
        else:
            err = "Не удалось изменить автозагрузку"
            self.tray_icon.showMessage(
                "Скриншотер",
                err,
                QSystemTrayIcon.Warning,
                2000
            )
            self.app.view.show_status_message(err, 5000)

    def _on_theme_selected(self, theme_key: str):
        self.app.apply_theme(theme_key)
        self._update_theme_checks(theme_key)

    def _update_theme_checks(self, selected_key: str):
        for key, action in self.theme_actions.items():
            action.setChecked(key == selected_key)

    def _choose_save_directory(self):
        self.app.choose_save_directory()

    def _quit_app(self):
        self.app.quit_app()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._toggle_window()
        elif reason == QSystemTrayIcon.DoubleClick:
            self.app.show_from_tray()

    def show_message(self, title: str, message: str):
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 3000)