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
        enhancer_layout = QFormLayout(enhancer_group)

        self.enhancer_enabled_check = QCheckBox("Использовать адаптивное улучшение")
        self.enhancer_enabled_check.setChecked(
            getattr(self.settings, "enhancer_enabled", False)
        )
        enhancer_layout.addRow(self.enhancer_enabled_check)

        self.enhancer_scale_combo = QComboBox()
        self.enhancer_scale_combo.addItem("Автоматически", "auto")
        self.enhancer_scale_combo.addItem("1,5×", 1.5)
        self.enhancer_scale_combo.addItem("2×", 2.0)
        self.enhancer_scale_combo.addItem("3×", 3.0)
        index = self.enhancer_scale_combo.findData(
            getattr(self.settings, "enhancer_scale", "auto")
        )
        if index >= 0:
            self.enhancer_scale_combo.setCurrentIndex(index)
        enhancer_layout.addRow("Масштаб:", self.enhancer_scale_combo)

        self.enhancer_text_check = QCheckBox("Текст")
        self.enhancer_text_check.setChecked(
            getattr(self.settings, "enhancer_text", True)
        )
        enhancer_layout.addRow("Оптимизация:", self.enhancer_text_check)

        self.enhancer_lines_check = QCheckBox("Тонкие линии")
        self.enhancer_lines_check.setChecked(
            getattr(self.settings, "enhancer_lines", True)
        )
        enhancer_layout.addRow("", self.enhancer_lines_check)

        self.enhancer_ui_check = QCheckBox("Интерфейс")
        self.enhancer_ui_check.setChecked(
            getattr(self.settings, "enhancer_ui", True)
        )
        enhancer_layout.addRow("", self.enhancer_ui_check)

        self.enhancer_geometry_check = QCheckBox("Геометрия")
        self.enhancer_geometry_check.setChecked(
            getattr(self.settings, "enhancer_geometry", True)
        )
        enhancer_layout.addRow("", self.enhancer_geometry_check)

        self.enhancer_color_combo = QComboBox()
        self.enhancer_color_combo.addItem("Автоматически", "auto")
        self.enhancer_color_combo.addItem("Сохранять оригинал", "original")
        self.enhancer_color_combo.addItem("Монохромное инвертированное", "monochrome")
        # Старое значение "invert" отображаем как новый монохромный режим.
        color_mode = getattr(self.settings, "enhancer_color_mode", "auto")
        if color_mode == "invert":
            color_mode = "monochrome"
        index = self.enhancer_color_combo.findData(color_mode)
        if index >= 0:
            self.enhancer_color_combo.setCurrentIndex(index)
        enhancer_layout.addRow("Цветовая схема:", self.enhancer_color_combo)

        layout.addWidget(enhancer_group)

        layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self,
        )
        buttons.button(QDialogButtonBox.Ok).setText("Сохранить")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
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
        self.settings.enhancer_enabled = self.enhancer_enabled_check.isChecked()
        self.settings.enhancer_scale = self.enhancer_scale_combo.currentData()
        self.settings.enhancer_text = self.enhancer_text_check.isChecked()
        self.settings.enhancer_lines = self.enhancer_lines_check.isChecked()
        self.settings.enhancer_ui = self.enhancer_ui_check.isChecked()
        self.settings.enhancer_geometry = self.enhancer_geometry_check.isChecked()
        self.settings.enhancer_color_mode = self.enhancer_color_combo.currentData()
        self.settings.save()

        enabled = self.autostart_check.isChecked()
        if enabled != self.settings.is_autostart_enabled():
            if enabled:
                self.settings.create_autostart_shortcut()
            else:
                self.settings.remove_autostart_shortcut()

        self.accept()
