"""
Модуль: theme.py
Описание: Менеджер тем оформления приложения.
          Централизованное хранилище цветов, стилей и QSS.
          Поддерживает светлую, тёмную и системную темы.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication


class ThemeManager:
    """Управляет темами оформления приложения."""

    COLORS_LIGHT = {
        'window_bg': QColor(240, 240, 240),
        'panel_bg': QColor(240, 240, 240),
        'text': QColor(51, 51, 51),
        'text_light': QColor(255, 255, 255),
        'border': QColor(200, 200, 200),
        'selection_bg': QColor(176, 212, 241),
        'selection_border': QColor(0, 90, 158),

        'btn_bg': QColor(240, 240, 240),
        'btn_hover': QColor(220, 220, 220),
        'btn_pressed': QColor(200, 200, 200),
        'btn_text': QColor(51, 51, 51),
        'btn_green': QColor(76, 175, 80),
        'btn_red': QColor(244, 67, 54),

        'editor_bg': QColor(199, 210, 223),

        'crop_bg': QColor(90, 90, 90),
        'crop_overlay': QColor(0, 0, 0, 120),
        'crop_rect': QColor(0, 120, 215),
        'crop_label_text': QColor(51, 51, 51),
        'crop_label_bg': QColor(255, 255, 255, 180),
        'crop_cursor_outline': QColor(255, 255, 255),
        'crop_cursor_line': QColor(0, 0, 0),

        'status_normal_bg': QColor(255, 255, 255, 180),
        'status_normal_text': QColor(51, 51, 51),
        'status_crop_bg': QColor(0, 0, 0, 180),
        'status_crop_text': QColor(255, 255, 255),

        'float_bg': QColor(200, 200, 200, 100),
        'float_border': QColor(80, 80, 80, 180),

        'text_bg_white': QColor(255, 255, 255, 200),
        'text_bg_black': QColor(0, 0, 0, 200),

        'rubber_band': QColor(255, 200, 0),
    }

    COLORS_DARK = {
        'window_bg': QColor(83, 83, 83),
        'panel_bg': QColor(83, 83, 83),
        'text': QColor(220, 220, 220),
        'text_light': QColor(255, 255, 255),
        'border': QColor(80, 80, 80),
        'selection_bg': QColor(0, 90, 158),
        'selection_border': QColor(176, 212, 241),

        'btn_bg': QColor(83, 83, 83),
        'btn_hover': QColor(100, 100, 100),
        'btn_pressed': QColor(120, 120, 120),
        'btn_text': QColor(220, 220, 220),
        'btn_green': QColor(76, 175, 80),
        'btn_red': QColor(244, 67, 54),

        'editor_bg': QColor(135, 135, 135),

        'crop_bg': QColor(50, 50, 50),
        'crop_overlay': QColor(0, 0, 0, 150),
        'crop_rect': QColor(0, 150, 255),
        'crop_label_text': QColor(220, 220, 220),
        'crop_label_bg': QColor(0, 0, 0, 180),
        'crop_cursor_outline': QColor(0, 0, 0),
        'crop_cursor_line': QColor(255, 255, 255),

        'status_normal_bg': QColor(60, 60, 60, 200),
        'status_normal_text': QColor(220, 220, 220),
        'status_crop_bg': QColor(0, 0, 0, 180),
        'status_crop_text': QColor(255, 255, 255),

        'float_bg': QColor(80, 80, 80, 160),
        'float_border': QColor(150, 150, 150, 180),

        'text_bg_white': QColor(255, 255, 255, 200),
        'text_bg_black': QColor(0, 0, 0, 200),

        'rubber_band': QColor(255, 255, 0),
    }

    def __init__(self, theme_key: str = 'light'):
        self._theme_key = theme_key
        self._effective_theme = self._resolve_theme(theme_key)

    @staticmethod
    def _resolve_theme(theme_key: str) -> str:
        if theme_key == 'system':
            return 'light'
        return theme_key if theme_key in ('light', 'dark') else 'light'

    @property
    def current_theme(self) -> str:
        return self._theme_key

    @property
    def effective_theme(self) -> str:
        return self._effective_theme

    def set_theme(self, theme_key: str):
        self._theme_key = theme_key
        self._effective_theme = self._resolve_theme(theme_key)

    def get_color(self, key: str) -> QColor:
        if self._effective_theme == 'dark':
            return self.COLORS_DARK.get(key, QColor(0, 0, 0))
        return self.COLORS_LIGHT.get(key, QColor(0, 0, 0))

    def get_qss(self) -> str:
        c = {k: self.get_color(k).name() for k in self.COLORS_LIGHT.keys()}

        # Отдельно получаем QColor для цветов с альфой
        float_bg = self.get_color('float_bg')
        float_border = self.get_color('float_border')
        status_normal_bg = self.get_color('status_normal_bg')
        status_normal_text = self.get_color('status_normal_text')
        selection_bg = self.get_color('selection_bg')
        selection_border = self.get_color('selection_border')

        return f"""
        QMainWindow {{
            background-color: {c['window_bg']};
        }}
        QToolBar {{
            background-color: {c['panel_bg']};
            border: 1px solid {c['border']};
            padding: 2px;
            spacing: 2px;
        }}
        QToolButton {{
            padding: 2px;
            margin: 0px;
            spacing: 0px;
            font-size: 8pt;
            background-color: transparent;
            border: none;
            color: {c['text']};
        }}
        QToolButton:checked {{
            background-color: {selection_bg.name()};
            border: 2px solid {selection_border.name()};
            border-radius: 4px;
        }}
        QPushButton {{
            background-color: {c['btn_bg']};
            color: {c['btn_text']};
            border: 1px solid {c['border']};
            border-radius: 3px;
            padding: 4px 8px;
        }}
        QPushButton:hover {{
            background-color: {c['btn_hover']};
        }}
        QPushButton:pressed {{
            background-color: {c['btn_pressed']};
        }}
        QPushButton#applyCropBtn {{
            background-color: {c['btn_green']};
            color: {c['text_light']};
            border: none;
        }}
        QPushButton#applyCropBtn:hover {{
            background-color: #45a049;
        }}
        QPushButton#applyCropBtn:pressed {{
            background-color: #3d8b40;
        }}
        QPushButton#cancelCropBtn {{
            background-color: {c['btn_red']};
            color: {c['text_light']};
            border: none;
        }}
        QPushButton#cancelCropBtn:hover {{
            background-color: #d32f2f;
        }}
        QPushButton#cancelCropBtn:pressed {{
            background-color: #b71c1c;
        }}
        QLineEdit {{
            background-color: {c['btn_bg']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 2px;
            padding: 2px;
        }}
        QSlider::groove:horizontal {{
            background: {selection_bg.name()};
            height: 6px;
        }}
        QSlider::handle:horizontal {{
            background: {c['btn_bg']};
            border: 1px solid {c['border']};
            width: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }}
        QFrame[frameShape="5"] {{
            background-color: rgba({float_bg.red()}, {float_bg.green()}, {float_bg.blue()}, {float_bg.alpha()});
            border-radius: 12px;
            border: 2px solid rgba({float_border.red()}, {float_border.green()}, {float_border.blue()}, {float_border.alpha()});
            padding: 2px;
        }}
        QLabel#statusLabel {{
            background-color: rgba({status_normal_bg.red()}, {status_normal_bg.green()}, {status_normal_bg.blue()}, {status_normal_bg.alpha()});
            color: {status_normal_text.name()};
            border-radius: 6px;
            padding: 4px 8px;
        }}
        QToolTip {{
            background-color: {c['panel_bg']};
            color: {c['text']};
            border: 1px solid {c['border']};
            padding: 2px;
        }}
        QWidget#zoomWidget {{
            background-color: rgba({float_bg.red()}, {float_bg.green()}, {float_bg.blue()}, {float_bg.alpha()});
            border-radius: 6px;
        }}
        """

    def apply(self, app: QApplication):
        app.setStyleSheet(self.get_qss())
        palette = QPalette()
        palette.setColor(QPalette.Window, self.get_color('window_bg'))
        palette.setColor(QPalette.WindowText, self.get_color('text'))
        palette.setColor(QPalette.Base, self.get_color('panel_bg'))
        palette.setColor(QPalette.AlternateBase, self.get_color('panel_bg'))
        palette.setColor(QPalette.Text, self.get_color('text'))
        palette.setColor(QPalette.Button, self.get_color('btn_bg'))
        palette.setColor(QPalette.ButtonText, self.get_color('btn_text'))
        palette.setColor(QPalette.Highlight, self.get_color('selection_bg'))
        palette.setColor(QPalette.HighlightedText, self.get_color('text'))
        app.setPalette(palette)


# Глобальный экземпляр менеджера тем
theme_manager = ThemeManager()