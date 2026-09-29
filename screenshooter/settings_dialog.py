"""Диалог настроек Screenshooter."""

import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    """Показывает пользовательские настройки и сохраняет их после подтверждения."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)

        general_group = QGroupBox("Основные")
        general_layout = QFormLayout(general_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Системная", "system")
        self.theme_combo.addItem("Светлая", "light")
        self.theme_combo.addItem("Тёмная", "dark")
        index = self.theme_combo.findData(self.settings.theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        general_layout.addRow("Тема:", self.theme_combo)

        save_layout = QHBoxLayout()
        self.save_directory_edit = QLineEdit(self.settings.save_directory)
        self.save_directory_edit.setPlaceholderText("По умолчанию")
        save_layout.addWidget(self.save_directory_edit, 1)
        self.browse_button = QPushButton("Выбрать…")
        self.browse_button.clicked.connect(self._choose_save_directory)
        save_layout.addWidget(self.browse_button)
        general_layout.addRow("Папка сохранения:", save_layout)

        self.autostart_check = QCheckBox("Запускать Screenshooter вместе с Windows")
        self.autostart_check.setChecked(self.settings.is_autostart_enabled())
        general_layout.addRow("Автозагрузка:", self.autostart_check)

        layout.addWidget(general_group)

        enhancer_group = QGroupBox("Адаптивный улучшайзер")
        enhancer_layout = QVBoxLayout(enhancer_group)
        enhancer_layout.addWidget(
            QLabel("Настройки улучшения качества будут добавлены следующим этапом.")
        )
        enhancer_layout.addWidget(
            QLabel("На этом этапе существующий захват и обработка изображения не изменяются.")
        )
        layout.addWidget(enhancer_group)

        layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _choose_save_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для сохранения скриншотов",
            self.save_directory_edit.text() or os.path.expanduser("~"),
        )
        if directory:
            self.save_directory_edit.setText(directory)

    def _accept(self):
        theme = self.theme_combo.currentData()
        self.settings.theme = theme
        self.settings.save_directory = self.save_directory_edit.text().strip()
        self.settings.save()

        enabled = self.autostart_check.isChecked()
        if enabled != self.settings.is_autostart_enabled():
            if enabled:
                self.settings.create_autostart_shortcut()
            else:
                self.settings.remove_autostart_shortcut()

        self.accept()
