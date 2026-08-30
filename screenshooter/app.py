"""
Модуль: app.py
Описание: Главное окно приложения ScreenshotApp.
          Создаёт тулбары с инструментами аннотаций, кнопки захвата,
          управляет горячими клавишами. Интегрирует настройки, системный трей
          и темы оформления.
"""

import sys
import os
import time
import keyboard
from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QTimer, pyqtSignal, QDir, QSettings, QEvent
from PyQt5.QtGui import QPixmap, QPainter, QImage, QColor, QIcon, QKeySequence
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QGraphicsScene, QGraphicsPixmapItem, QActionGroup,
                             QAction, QFileDialog, QMessageBox, QApplication, QSizePolicy, QDialog,
                             QStyle, QMenu, QLabel, QShortcut)

from .screen_capture import ScreenCapture
from .export import Exporter
from .view import EditorView
from .widgets.thickness import ThicknessWidget
from .widgets.color_palette import ColorPaletteWidget
from .widgets.tool_icons import (
    create_tool_icon,
    create_crop_icon,
    create_rotate_icon,
    create_blur_icon
)
from .settings import AppSettings
from .tray import TrayManager
from .utils import load_app_icon
from .theme import theme_manager
from .controllers.crop_cursor_factory import CropCursorFactory
from .ui.layout_metrics import (
    MAIN_LAYOUT_MARGIN,
    MAIN_LAYOUT_SPACING,
    TOP_ACTIONS_SPACING,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    WINDOW_INITIAL_WIDTH,
    WINDOW_INITIAL_HEIGHT,
)
from .ui.annotation_toolbar import AnnotationToolbar
from .ui.image_toolbar import ImageToolbar
from .ui.options_toolbar import OptionsToolbar
from .ui.editor_toolbar_strip import EditorToolbarStrip


class ScreenshotApp(QMainWindow):
    capture_monitor_requested = pyqtSignal()
    capture_window_requested = pyqtSignal()
    capture_region_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Скриншотер с редактором")
        self.setGeometry(100, 100, WINDOW_INITIAL_WIDTH, WINDOW_INITIAL_HEIGHT)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # Настройки приложения
        self.settings = AppSettings()

        # Загружаем сохранённую тему и применяем её ДО создания виджетов
        theme_manager.set_theme(self.settings.theme)
        theme_manager.apply(QApplication.instance())

        # Иконка окна из ресурсов
        self.setWindowIcon(load_app_icon())

        # Флаг для различения закрытия и сворачивания
        self._force_quit = False
        self._saved_window_state = None

        self._printscreen_hook = None
        self._alt_printscreen_hotkey = None
        self._ctrl_printscreen_hotkey = None

        cw = QWidget()
        self.setCentralWidget(cw)
        layout = QVBoxLayout(cw)
        layout.setContentsMargins(MAIN_LAYOUT_MARGIN, MAIN_LAYOUT_MARGIN,
                                  MAIN_LAYOUT_MARGIN, MAIN_LAYOUT_MARGIN)
        layout.setSpacing(MAIN_LAYOUT_SPACING)

        top_actions_widget = QWidget()
        top_actions_layout = QHBoxLayout(top_actions_widget)
        top_actions_layout.setContentsMargins(0, 0, 0, 0)
        top_actions_layout.setSpacing(TOP_ACTIONS_SPACING)

        left_group_widget = QWidget()
        left_group_layout = QHBoxLayout(left_group_widget)
        left_group_layout.setContentsMargins(0, 0, 0, 0)
        left_group_layout.setSpacing(6)

        self.undo_btn = QPushButton()
        self.undo_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.undo_btn.setToolTip("Отменить")
        self.undo_btn.clicked.connect(self.undo_action)
        left_group_layout.addWidget(self.undo_btn)

        self.redo_btn = QPushButton()
        self.redo_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.redo_btn.setToolTip("Повторить")
        self.redo_btn.clicked.connect(self.redo_action)
        left_group_layout.addWidget(self.redo_btn)

        self.capture_btn = QPushButton("Снимок")
        self.capture_btn.clicked.connect(self.capture_screen)
        left_group_layout.addWidget(self.capture_btn)

        self.clear_btn = QPushButton("Очистить")
        self.clear_btn.clicked.connect(self.clear_scene_action)
        left_group_layout.addWidget(self.clear_btn)

        top_actions_layout.addWidget(left_group_widget)
        top_actions_layout.addStretch(1)

        self.scene = QGraphicsScene()
        self.view = EditorView(self.scene)
        self.view.zoomChangedByWheel.connect(self._on_view_zoom_changed)

        # Контроллеры захвата и экспорта
        self.capture = ScreenCapture(self)
        self.exporter = Exporter(self.view, self.scene, self.settings)
        self.exporter.load_save_directory_from_settings()

        # Инициализация трея после создания основного окна
        self.tray_manager = TrayManager(self)

        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self._on_undo_shortcut)
        self.redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.redo_shortcut.activated.connect(self._on_redo_shortcut)
        self.paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        self.paste_shortcut.activated.connect(self._on_paste_shortcut)

        self.crop_buttons_widget = QWidget()
        crop_buttons_layout = QHBoxLayout(self.crop_buttons_widget)
        crop_buttons_layout.setContentsMargins(0, 0, 0, 0)
        crop_buttons_layout.setSpacing(6)

        self.apply_crop_btn = QPushButton("Применить")
        self.apply_crop_btn.setFixedWidth(80)
        self.apply_crop_btn.setObjectName("applyCropBtn")
        self.apply_crop_btn.clicked.connect(self.view.apply_crop)
        crop_buttons_layout.addWidget(self.apply_crop_btn)

        self.cancel_crop_btn = QPushButton("Отмена")
        self.cancel_crop_btn.setFixedWidth(60)
        self.cancel_crop_btn.setObjectName("cancelCropBtn")
        self.cancel_crop_btn.clicked.connect(self.view.cancel_crop_mode)
        crop_buttons_layout.addWidget(self.cancel_crop_btn)

        self.crop_buttons_widget.setVisible(False)
        top_actions_layout.addWidget(self.crop_buttons_widget)
        top_actions_layout.addStretch(1)

        right_group_widget = QWidget()
        right_group_layout = QHBoxLayout(right_group_widget)
        right_group_layout.setContentsMargins(0, 0, 0, 0)
        right_group_layout.setSpacing(6)

        self.copy_btn = QPushButton("В буфер")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        right_group_layout.addWidget(self.copy_btn)

        self.insert_file_btn = QPushButton("Вставить файл")
        self.insert_file_btn.clicked.connect(self.insert_image_from_file)
        right_group_layout.addWidget(self.insert_file_btn)

        self.insert_clipboard_btn = QPushButton("Из буфера")
        self.insert_clipboard_btn.clicked.connect(self.insert_image_from_clipboard)
        right_group_layout.addWidget(self.insert_clipboard_btn)

        self.save_as_btn = QPushButton(" Сохранить как ")
        self.save_as_btn.clicked.connect(self.save_image)
        right_group_layout.addWidget(self.save_as_btn)

        self.quick_save_btn = QPushButton("Сохранить")
        self.quick_save_btn.clicked.connect(self.quick_save)
        self.quick_save_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.quick_save_btn.customContextMenuRequested.connect(self.show_quick_save_menu)
        right_group_layout.addWidget(self.quick_save_btn)

        top_actions_layout.addWidget(right_group_widget)
        layout.addWidget(top_actions_widget)

        # ================== РЕДАКТОР ТУЛБАРОВ ==================
        self.view.history.stack.canUndoChanged.connect(self._update_undo_buttons)
        self.view.history.stack.canRedoChanged.connect(self._update_undo_buttons)
        self._update_undo_buttons()

        self.thickness_widget = ThicknessWidget()
        self.thickness_widget.valueChanged.connect(self.change_width)
        self.color_palette = ColorPaletteWidget()
        self.color_palette.colorSelected.connect(self.set_color_from_palette)

        # Связываем изменение режима прямоугольника с обновлением цвета палитры
        self.view.shape_mode_widget.modeChanged.connect(self._on_shape_mode_changed_for_color)

        action_group = QActionGroup(self)
        action_group.setExclusive(True)

        pointer_action = self._create_tool_action(
            "Выбор", None, action_group,
            icon=create_tool_icon('pointer', QColor(30, 30, 30)),
            tooltip="Выделение")
        line_action = self._create_tool_action(
            "Линия", 'line', action_group,
            icon=create_tool_icon('line', QColor(220, 30, 30)),
            tooltip="Линия")
        rect_action = self._create_tool_action(
            "Контур", 'rect', action_group,
            icon=create_tool_icon('rect', QColor(220, 30, 30)),
            tooltip="Контур")
        ellipse_action = self._create_tool_action(
            "Эллипс", 'ellipse', action_group,
            icon=create_tool_icon('ellipse', QColor(220, 30, 30)),
            tooltip="Эллипс")
        arrow_action = self._create_tool_action(
            "Стрелка", 'arrow', action_group,
            icon=create_tool_icon('arrow', QColor(220, 30, 30)),
            tooltip="Стрелка")
        text_action = self._create_tool_action(
            "Текст", 'text', action_group,
            icon=create_tool_icon('text', QColor(220, 30, 30)),
            tooltip="Текст")

        self.pointer_action = pointer_action
        self.line_action = line_action
        self.rect_action = rect_action
        self.ellipse_action = ellipse_action
        self.arrow_action = arrow_action
        self.text_action = text_action

        annotation_actions = [
            pointer_action, line_action, rect_action,
            ellipse_action, arrow_action, text_action
        ]

        crop_action = QAction("Обрезать", self)
        crop_action.setCheckable(True)
        crop_action.setIcon(create_crop_icon())
        crop_action.setToolTip("Обрезать изображение")
        crop_action.triggered.connect(self._on_crop_action_triggered)

        rotate_cw_action = QAction("Повернуть", self)
        rotate_cw_action.setIcon(create_rotate_icon(clockwise=True))
        rotate_cw_action.setToolTip("Повернуть на 90° по часовой")
        rotate_cw_action.triggered.connect(lambda: self._rotate_image(90))

        rotate_ccw_action = QAction("Повернуть", self)
        rotate_ccw_action.setIcon(create_rotate_icon(clockwise=False))
        rotate_ccw_action.setToolTip("Повернуть на 90° против часовой")
        rotate_ccw_action.triggered.connect(lambda: self._rotate_image(-90))

        blur_action = QAction("Размыть", self)
        blur_action.setCheckable(True)
        blur_action.setIcon(create_blur_icon())
        blur_action.setToolTip("Размыть область")
        blur_action.triggered.connect(self._on_blur_action_triggered)

        self.crop_action = crop_action
        self.rotate_cw_action = rotate_cw_action
        self.rotate_ccw_action = rotate_ccw_action
        self.blur_action = blur_action

        image_actions = [crop_action, rotate_cw_action, rotate_ccw_action, blur_action]

        # Создаём компоненты тулбаров
        annotation_toolbar = AnnotationToolbar(annotation_actions)
        image_toolbar = ImageToolbar(image_actions)
        options_toolbar = OptionsToolbar(self.thickness_widget, self.color_palette)

        # Создаём плоскую панель
        editor_toolbar_strip = EditorToolbarStrip(
            annotation_toolbar,
            image_toolbar,
            options_toolbar,
            parent=cw
        )

        # Добавляем панель между MainActionBar и EditorView
        layout.addWidget(editor_toolbar_strip)
        layout.addWidget(self.view)

        # Устанавливаем текущий инструмент
        self.pointer_action.setChecked(True)
        self._sync_palette_to_tool(None)

        self.color_palette.set_current_color(QColor("#D25145"))
        self.screenshot_pixmap = None
        self.user_zoomed = False
        self.thickness_widget.set_value_silent(2)

        self.statusBar().hide()

        self.scene.selectionChanged.connect(self._on_scene_selection_changed)
        QTimer.singleShot(0, self.view.update_text_format_widget_visibility)

        self.capture_monitor_requested.connect(self.capture_monitor)
        self.capture_window_requested.connect(self.capture_window)
        self.capture_region_requested.connect(self.capture_region)

        self.view.crop_mode_changed.connect(self._on_crop_mode_changed)
        self.view.blur_mode_changed.connect(self._on_blur_mode_changed)
        self.view.background_changed.connect(self._update_image_actions_enabled)

        self.setup_global_hotkeys()
        self._update_image_actions_enabled()
        self.view.setFocus()

    # --------------------------------------------------------------
    # Вспомогательный метод создания tool action
    # --------------------------------------------------------------
    def _create_tool_action(self, text, tool_name, group, icon=None, tooltip=None):
        act = QAction(text, self)
        act.setCheckable(True)
        if icon:
            act.setIcon(icon)
        if tooltip:
            act.setToolTip(tooltip)
        act.triggered.connect(lambda: self.set_tool(tool_name))
        group.addAction(act)
        return act

    # --------------------------------------------------------------
    # Синхронизация палитры с инструментом
    # --------------------------------------------------------------
    def _sync_palette_to_tool(self, tool_name):
        """Устанавливает цвет пера и палитры в зависимости от выбранного инструмента."""
        if tool_name == 'text':
            new_color = QColor("#F9D556")
        elif tool_name == 'rect':
            new_color = QColor("#F9D556") if self.view.shape_mode == 'filled' else QColor("#D25145")
        else:
            new_color = QColor("#D25145")

        # Обновляем текущий цвет пера
        self.view.current_pen_color = new_color

        # Обновляем палитру и информационный виджет
        self.color_palette.set_current_color(new_color)
        self.view.widget_manager.update_info_widget_content(new_color, self.view.pen_width)

    def _on_shape_mode_changed_for_color(self, mode):
        """Обрабатывает смену режима прямоугольника для обновления цвета."""
        if self.view.current_tool == 'rect':
            self._sync_palette_to_tool('rect')

    # --------------------------------------------------------------
    # Интеграция с системным треем
    # --------------------------------------------------------------
    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange and self.isMinimized():
            self._saved_window_state = self.windowState()
            QTimer.singleShot(0, self.hide)
            self.tray_manager.show_message(
                "Скриншотер",
                "Приложение свёрнуто в трей"
            )
        super().changeEvent(event)

    def show_from_tray(self):
        if self._saved_window_state and (self._saved_window_state & Qt.WindowMaximized):
            self.showMaximized()
        else:
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        self.settings.save()
        self._remove_keyboard_hooks()
        event.accept()

    def quit_app(self):
        self._force_quit = True
        self.settings.save()
        self._remove_keyboard_hooks()
        QApplication.quit()

    # --------------------------------------------------------------
    # Применение темы
    # --------------------------------------------------------------
    def apply_theme(self, theme_key: str):
        theme_manager.set_theme(theme_key)
        theme_manager.apply(QApplication.instance())
        self.view.update_theme_colors()
        self.settings.set_theme(theme_key)

        self.view.image_editor.status_bar_manager.reset_to_normal()

        CropCursorFactory.reset()

        theme_names = {"light": "Светлая", "dark": "Тёмная", "system": "Системная"}
        label = theme_names.get(theme_key, theme_key)
        self.view.show_status_message(f"Тема: {label}", 2000)

    # --------------------------------------------------------------
    # Вставка изображений
    # --------------------------------------------------------------
    def insert_image_from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Вставить изображение", "",
                                             "Изображения (*.png *.jpg *.jpeg *.bmp)")
        if path:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                if self.view.background_item is None or sip.isdeleted(self.view.background_item):
                    self.view.set_background_from_pixmap(pixmap)
                else:
                    self.view.add_pasted_image(pixmap)

    def insert_image_from_clipboard(self):
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()

        if mime.hasImage():
            image = clipboard.image()
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                if not pixmap.isNull():
                    if self.view.background_item is None or sip.isdeleted(self.view.background_item):
                        self.view.set_background_from_pixmap(pixmap)
                    else:
                        self.view.add_pasted_image(pixmap)
                    return

        if mime.hasUrls():
            for url in mime.urls():
                local_path = url.toLocalFile()
                if local_path and os.path.isfile(local_path):
                    pixmap = QPixmap(local_path)
                    if not pixmap.isNull():
                        if self.view.background_item is None or sip.isdeleted(self.view.background_item):
                            self.view.set_background_from_pixmap(pixmap)
                        else:
                            self.view.add_pasted_image(pixmap)
                        return

        if mime.hasText():
            text = mime.text().strip()
            if text.startswith('file:///'):
                text = text[8:]
            text = os.path.normpath(text)
            if os.path.isfile(text):
                pixmap = QPixmap(text)
                if not pixmap.isNull():
                    if self.view.background_item is None or sip.isdeleted(self.view.background_item):
                        self.view.set_background_from_pixmap(pixmap)
                    else:
                        self.view.add_pasted_image(pixmap)
                    return

        self.view.show_status_message("Не удалось вставить изображение из буфера.", 5000)

    # --------------------------------------------------------------
    # Очистка сцены
    # --------------------------------------------------------------
    def clear_scene_action(self):
        has_bg = self.view.background_item is not None and not sip.isdeleted(self.view.background_item)
        has_items = len(self.view.scene().items()) > 0

        if not has_bg and not has_items:
            return

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Очистить сцену")
        msg_box.setText("Вы уверены, что хотите очистить сцену?")
        msg_box.setInformativeText("Все изображения, аннотации и история будут удалены.")
        msg_box.setIcon(QMessageBox.Question)

        yes_btn = msg_box.addButton("Да", QMessageBox.YesRole)
        no_btn = msg_box.addButton("Нет", QMessageBox.NoRole)

        yes_btn.setMinimumSize(60, 24)
        no_btn.setMinimumSize(60, 24)

        msg_box.setDefaultButton(yes_btn)

        msg_box.exec_()

        if msg_box.clickedButton() == yes_btn:
            self.view.clear_scene()
            self._update_image_actions_enabled()
            self._update_undo_buttons()

    # --------------------------------------------------------------
    # Активация кнопок тулбара изображения
    # --------------------------------------------------------------
    def _update_image_actions_enabled(self):
        has_bg = self.view.background_item is not None and not sip.isdeleted(self.view.background_item)
        self.crop_action.setEnabled(has_bg)
        self.rotate_cw_action.setEnabled(has_bg)
        self.rotate_ccw_action.setEnabled(has_bg)
        self.blur_action.setEnabled(has_bg)

    # --------------------------------------------------------------
    # Обработчики режимов изображения
    # --------------------------------------------------------------
    def _on_crop_action_triggered(self):
        if self.view.blur_mode:
            self.view.cancel_blur_mode()
        if self.view.crop_mode:
            self.view.cancel_crop_mode()
        else:
            self.view.start_crop_mode()
            self.pointer_action.setChecked(True)

    def _on_blur_action_triggered(self):
        if self.view.crop_mode:
            self.view.cancel_crop_mode()
        if self.view.blur_mode:
            self.view.cancel_blur_mode()
        else:
            self.pointer_action.setChecked(True)
            self.view.start_blur_mode()

    def _on_crop_mode_changed(self, active):
        self.crop_action.setChecked(active)
        self.crop_buttons_widget.setVisible(active)
        if active:
            self.blur_action.setChecked(False)

    def _on_blur_mode_changed(self, active):
        self.blur_action.setChecked(active)
        if active:
            self.crop_action.setChecked(False)

    def _rotate_image(self, angle):
        if self.view.blur_mode:
            self.view.cancel_blur_mode()
        if self.view.crop_mode:
            self.view.cancel_crop_mode()
        self.pointer_action.setChecked(True)
        self.view.rotate_image(angle)
        if self.view.background_item:
            self.view.setSceneRect(QRectF(self.view.background_item.pixmap().rect()))
        self.view.viewport().update()

    # --------------------------------------------------------------
    # Undo/Redo и горячие клавиши
    # --------------------------------------------------------------
    def _on_undo_shortcut(self):
        from PyQt5.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit
        widget = QApplication.focusWidget()
        if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            return
        if self.view.active_text_item and self.view.active_text_item._editable:
            return
        self.undo_action()

    def _on_redo_shortcut(self):
        from PyQt5.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit
        widget = QApplication.focusWidget()
        if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            return
        if self.view.active_text_item and self.view.active_text_item._editable:
            return
        self.redo_action()

    def _on_paste_shortcut(self):
        from PyQt5.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit
        widget = QApplication.focusWidget()
        if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            return
        if self.view.active_text_item and self.view.active_text_item._editable:
            return

        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()

        # Проверяем маркер внутреннего копирования
        if mime.hasFormat("application/x-screenshooter-internal"):
            if self.view.clipboard_controller.has_clipboard:
                self.view.clipboard_controller.paste()
            else:
                self.view.show_status_message("Буфер обмена пуст", 3000)
            return

        # Если маркера нет — работаем с системным буфером
        if mime.hasImage() or mime.hasUrls() or mime.hasText():
            self.insert_image_from_clipboard()
            return

        # Если системный буфер пуст, пробуем внутренний
        if self.view.clipboard_controller.has_clipboard:
            self.view.clipboard_controller.paste()
        else:
            self.view.show_status_message("Буфер обмена пуст", 3000)

    def undo_action(self):
        self.view.undo()

    def redo_action(self):
        self.view.redo()

    def _update_undo_buttons(self):
        try:
            if hasattr(self, 'view') and self.view and hasattr(self.view, 'history'):
                self.undo_btn.setEnabled(self.view.history.can_undo())
                self.redo_btn.setEnabled(self.view.history.can_redo())
            else:
                self.undo_btn.setEnabled(False)
                self.redo_btn.setEnabled(False)
        except (RuntimeError, AttributeError):
            self.undo_btn.setEnabled(False)
            self.redo_btn.setEnabled(False)

    # --------------------------------------------------------------
    # Захват экрана — делегирование в ScreenCapture
    # --------------------------------------------------------------
    def capture_screen(self):
        self.capture.capture_screen()

    def capture_monitor(self):
        if self.capture.is_capturing():
            return
        self.capture.capture_monitor()

    def capture_window(self):
        if self.capture.is_capturing():
            return
        self.capture.capture_window()

    def capture_region(self):
        if self.capture.is_capturing():
            return
        self.capture.capture_region()

    # --------------------------------------------------------------
    # Экспорт — делегирование в Exporter
    # --------------------------------------------------------------
    def render_scene_to_image(self):
        return self.exporter.render_scene_to_image()

    def save_image(self):
        self.exporter.save_image()

    def copy_to_clipboard(self):
        self.exporter.copy_to_clipboard()

    def quick_save(self):
        self.exporter.quick_save()

    def choose_save_directory(self):
        return self.exporter.choose_save_directory()

    def show_quick_save_menu(self, pos):
        self.exporter.show_quick_save_menu(pos, self.quick_save_btn)

    # --------------------------------------------------------------
    # Отображение скриншота
    # --------------------------------------------------------------
    def display_screenshot(self):
        self.view.clear_pasted_images()
        self.scene.clear()
        self.view.active_text_item = None
        self.view.history.clear()

        item = QGraphicsPixmapItem(self.screenshot_pixmap)
        item.setTransformationMode(Qt.SmoothTransformation)

        item.setAcceptedMouseButtons(Qt.NoButton)
        item.setZValue(-1)

        self.scene.addItem(item)
        self.view.set_background_item(item)

        self.view.setSceneRect(QRectF(self.screenshot_pixmap.rect()))
        self.view.auto_fit = True
        self.user_zoomed = False
        self.view.fitInView(item, Qt.KeepAspectRatio)
        scale = self.view.transform().m11() * 100
        self.view.zoom_widget.set_zoom(scale)

        if self.screenshot_pixmap:
            w = self.screenshot_pixmap.width()
            h = self.screenshot_pixmap.height()
            self.view.set_resolution_text(f"{w}×{h}")
        else:
            self.view.set_resolution_text("")

        self.crop_action.setChecked(False)
        self.blur_action.setChecked(False)
        self.crop_buttons_widget.setVisible(False)

        self._update_image_actions_enabled()

    # --------------------------------------------------------------
    # Горячие клавиши
    # --------------------------------------------------------------
    def setup_global_hotkeys(self):
        self._remove_keyboard_hooks()
        try:
            self._alt_printscreen_hotkey = keyboard.add_hotkey(
                "alt+print screen", self._on_alt_printscreen_hotkey,
                suppress=True, trigger_on_release=False)
            self._ctrl_printscreen_hotkey = keyboard.add_hotkey(
                "ctrl+print screen", self._on_ctrl_printscreen_hotkey,
                suppress=True, trigger_on_release=False)
            self._printscreen_hook = keyboard.hook_key(
                "print screen", self._on_printscreen_key, suppress=True)
            print("Горячие клавиши зарегистрированы: PrintScreen (монитор), Alt+PrintScreen (окно), Ctrl+PrintScreen (область)")
        except Exception as e:
            self._printscreen_hook = None
            self._alt_printscreen_hotkey = None
            self._ctrl_printscreen_hotkey = None
            print(f"Ошибка регистрации горячих клавиш: {e}")

    def _on_printscreen_key(self, event):
        if event.event_type != keyboard.KEY_DOWN:
            return True
        if getattr(event, "is_keypad", False):
            return True
        if keyboard.is_pressed("ctrl") or keyboard.is_pressed("alt"):
            return True
        if self.capture.is_capturing():
            return True
        self.capture_monitor_requested.emit()
        return True

    def _on_alt_printscreen_hotkey(self):
        if self.capture.is_capturing():
            return
        self.capture_window_requested.emit()

    def _on_ctrl_printscreen_hotkey(self):
        if self.capture.is_capturing():
            return
        self.capture_region_requested.emit()

    def _remove_keyboard_hooks(self):
        if self._printscreen_hook is not None:
            try:
                keyboard.unhook_key(self._printscreen_hook)
            except Exception:
                pass
            self._printscreen_hook = None
        if self._alt_printscreen_hotkey is not None:
            try:
                keyboard.remove_hotkey(self._alt_printscreen_hotkey)
            except Exception:
                pass
            self._alt_printscreen_hotkey = None
        if self._ctrl_printscreen_hotkey is not None:
            try:
                keyboard.remove_hotkey(self._ctrl_printscreen_hotkey)
            except Exception:
                pass
            self._ctrl_printscreen_hotkey = None

    # --------------------------------------------------------------
    # Прочие методы
    # --------------------------------------------------------------
    def set_tool(self, tn):
        self.view.set_tool(tn)
        self.thickness_widget.set_value_silent(self.view.get_current_width())
        self._sync_palette_to_tool(tn)
        self.view.setFocus()

    def change_width(self, v):
        transform = self.view.transform()
        self.view.auto_fit = False
        self.view.set_pen_width(v)
        self.view.setFocus()
        self.view.setTransform(transform)

    def set_color_from_palette(self, c):
        transform = self.view.transform()
        self.view.auto_fit = False
        self.view.set_pen_color(c)
        self.view.setFocus()
        self.view.setTransform(transform)

    def set_zoom(self, p):
        self.user_zoomed = True
        self.view.auto_fit = False
        scale = p / 100
        self.view.resetTransform()
        self.view.scale(scale, scale)
        self.view.zoom_widget.set_zoom(p)

    def _on_view_zoom_changed(self, p):
        self.set_zoom(p)

    def _on_scene_selection_changed(self):
        if sip.isdeleted(self.scene):
            return
        self.view.update_text_format_widget_visibility()
        sel = self.scene.selectedItems()
        if not sel:
            self.thickness_widget.set_value_silent(self.view.pen_width)
            self.color_palette.set_current_color(self.view.current_pen_color)

    def delete_selected(self):
        self.view.delete_selected()