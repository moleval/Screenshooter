"""
Модуль: tray.py
Описание: Управление иконкой в системном трее и контекстным меню.
"""

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication


class TrayManager(QObject):
    def __init__(self, window_manager):
        super().__init__(window_manager)
        self.window_manager = window_manager
        self.window_manager.tray_manager = self

        current_window = self._current_window()
        icon = current_window.windowIcon() if current_window is not None else QIcon()
        if icon.isNull():
            icon = QIcon()

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("Скриншотер")

        self.menu = QMenu()
        self.update_windows_menu()

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self._on_activated)
        self.tray_icon.show()

    def _current_window(self):
        if self.window_manager is None:
            return None
        if self.window_manager.active_window is not None:
            return self.window_manager.active_window
        windows = self.window_manager.windows
        return windows[-1] if windows else None

    def _window_title(self, window):
        if window is None:
            return "Скриншотер"
        title = window.windowTitle()
        if title and title.strip():
            return title
        return f"Скриншотер {getattr(window, '_window_number', '')}" if getattr(window, '_window_number', None) else "Скриншотер"

    def _build_menu(self):
        self.update_windows_menu()

    def update_windows_menu(self):
        self.menu.clear()

        self.show_hide_action = QAction("Показать/Скрыть все", self)
        self.show_hide_action.setCheckable(False)
        self.show_hide_action.triggered.connect(self._toggle_all_windows)
        self.menu.addAction(self.show_hide_action)

        self.menu.addSeparator()

        if self.window_manager is None or not self.window_manager.windows:
            no_windows_action = QAction("Нет открытых окон", self)
            no_windows_action.setEnabled(False)
            self.menu.addAction(no_windows_action)
        else:
            windows = sorted(
                self.window_manager.windows,
                key=lambda w: getattr(w, "_window_number", 0) or 0
            )
            for window in windows:
                action = QAction(self._window_title(window), self)
                action.setCheckable(True)
                action.triggered.connect(lambda checked, target=window: self._activate_window(target))
                action.setChecked(window.isVisible() and not window.isMinimized())
                self.menu.addAction(action)

        self.menu.addSeparator()

        self.autostart_action = QAction("Автозагрузка", self)
        self.autostart_action.setCheckable(True)
        current_window = self._current_window()
        self.autostart_action.setChecked(current_window.settings.is_autostart_enabled() if current_window is not None else False)
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

    def _activate_window(self, window):
        if window is None:
            return
        if window.isMinimized():
            window.showNormal()
        else:
            window.show()
        window.raise_()
        window.activateWindow()
        if hasattr(window, "_window_manager"):
            window._window_manager.set_active_window(window)
        self.update_windows_menu()

    def _build_theme_menu(self):
        self.theme_actions = {}
        current_window = self._current_window()
        current_theme = current_window.settings.theme if current_window is not None else "system"
        themes = [("light", "Светлая"), ("dark", "Тёмная"), ("system", "Системная")]
        for key, label in themes:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(current_theme == key)
            action.triggered.connect(lambda checked, k=key: self._on_theme_selected(k))
            self.theme_actions[key] = action
            self.theme_menu.addAction(action)

    def _toggle_all_windows(self):
        if self.window_manager is None:
            return
        self.window_manager.toggle_all_windows()
        self.update_windows_menu()

    def _toggle_window(self):
        self._toggle_all_windows()

    def _on_autostart_toggled(self, enabled: bool):
        target = self._current_window()
        if target is None:
            return
        if enabled:
            success = target.settings.create_autostart_shortcut()
        else:
            success = target.settings.remove_autostart_shortcut()

        self.autostart_action.setChecked(target.settings.is_autostart_enabled())

        if success:
            msg = "Автозагрузка включена" if enabled else "Автозагрузка выключена"
            self.tray_icon.showMessage("Скриншотер", msg, QSystemTrayIcon.Information, 2000)
            target.view.show_status_message(msg, 3000)
        else:
            err = "Не удалось изменить автозагрузку"
            self.tray_icon.showMessage("Скриншотер", err, QSystemTrayIcon.Warning, 2000)
            target.view.show_status_message(err, 5000)

    def _on_theme_selected(self, theme_key: str):
        target = self._current_window()
        if target is None:
            return
        target.apply_theme(theme_key)
        self._update_theme_checks(theme_key)

    def _update_theme_checks(self, selected_key: str):
        for key, action in self.theme_actions.items():
            action.setChecked(key == selected_key)

    def _choose_save_directory(self):
        target = self._current_window()
        if target is not None:
            target.choose_save_directory()

    def _quit_app(self):
        target = self._current_window()
        if target is not None:
            target.quit_app()
        else:
            QApplication.quit()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._toggle_all_windows()
            return
        target = self._current_window()
        if target is None:
            return
        if reason == QSystemTrayIcon.DoubleClick:
            target.show_from_tray()

    def show_message(self, title: str, message: str):
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 3000)
