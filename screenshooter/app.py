"""Главное окно приложения."""

import sys
import os
import time
import keyboard
from PyQt5 import sip
from PyQt5.QtCore import Qt, QRectF, QSize, QTimer, pyqtSignal, QDir, QSettings
from PyQt5.QtGui import QPixmap, QPainter, QImage, QColor, QIcon, QKeySequence
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QGraphicsScene, QGraphicsPixmapItem, QToolBar, QActionGroup,
                             QAction, QFileDialog, QMessageBox, QApplication, QSizePolicy, QDialog,
                             QStyle, QMenu, QLabel, QShortcut)

from .capture.screen_overlay import ScreenCaptureOverlay
from .capture.region_overlay import RegionCaptureOverlay
from .capture.window_capture import capture_active_window
from .view import EditorView
from .widgets.thickness import ThicknessWidget
from .widgets.color_palette import ColorPaletteWidget
from .widgets.tool_icons import (
    create_tool_icon,
    create_crop_icon,
    create_rotate_icon,
    create_blur_icon
)


class ScreenshotApp(QMainWindow):
    TOOL_BUTTON_WIDTH = 59

    capture_monitor_requested = pyqtSignal()
    capture_window_requested = pyqtSignal()
    capture_region_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Скриншотер с редактором")
        self.setGeometry(100, 100, 1000, 750)
        self.setMinimumSize(950, 650)

        self._printscreen_hook = None
        self._alt_printscreen_hotkey = None
        self._ctrl_printscreen_hotkey = None
        self._capture_in_progress = False
        self._window_state_before_capture = None

        settings = QSettings("Screenshooter", "Screenshooter")
        self.save_directory = settings.value("save_directory", None)
        if self.save_directory and not os.path.isdir(self.save_directory):
            self.save_directory = None

        cw = QWidget()
        self.setCentralWidget(cw)
        layout = QVBoxLayout(cw)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(4)

        top_actions_widget = QWidget()
        top_actions_layout = QHBoxLayout(top_actions_widget)
        top_actions_layout.setContentsMargins(0, 0, 0, 0)
        top_actions_layout.setSpacing(6)

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

        top_actions_layout.addWidget(left_group_widget)
        top_actions_layout.addStretch(1)

        self.scene = QGraphicsScene()
        self.view = EditorView(self.scene)
        self.view.zoomChangedByWheel.connect(self._on_view_zoom_changed)

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
        self.apply_crop_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; border: none; padding: 5px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #45a049; }"
            "QPushButton:pressed { background-color: #3d8b40; }"
        )
        self.apply_crop_btn.clicked.connect(self.view.apply_crop)
        crop_buttons_layout.addWidget(self.apply_crop_btn)

        self.cancel_crop_btn = QPushButton("Отмена")
        self.cancel_crop_btn.setFixedWidth(60)
        self.cancel_crop_btn.setStyleSheet(
            "QPushButton { background-color: #F44336; color: white; border: none; padding: 5px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #d32f2f; }"
            "QPushButton:pressed { background-color: #b71c1c; }"
        )
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
        layout.addWidget(self.view)

        self.view.history.stack.canUndoChanged.connect(self._update_undo_buttons)
        self.view.history.stack.canRedoChanged.connect(self._update_undo_buttons)
        self._update_undo_buttons()

        self.thickness_widget = ThicknessWidget()
        self.thickness_widget.valueChanged.connect(self.change_width)
        self.color_palette = ColorPaletteWidget()
        self.color_palette.colorSelected.connect(self.set_color_from_palette)

        self.top_toolbar = QToolBar("Панель инструментов")
        self.top_toolbar.setMovable(False)
        self.top_toolbar.setFloatable(False)
        self.top_toolbar.setIconSize(QSize(32, 32))
        self.top_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.top_toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.top_toolbar.setContentsMargins(0, 0, 0, 0)
        self.top_toolbar.setStyleSheet(
            "QToolButton { padding: 2px; } "
            "QToolButton:checked { background-color: #b0d4f1; border: 2px solid #005a9e; border-radius: 4px; }")
        self.addToolBar(Qt.TopToolBarArea, self.top_toolbar)

        left_spacer = QWidget()
        left_spacer.setFixedWidth(9)
        self.top_toolbar.addWidget(left_spacer)

        toolbar_tools = QToolBar("Аннотации")
        toolbar_tools.setIconSize(QSize(32, 32))
        toolbar_tools.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        toolbar_tools.setMovable(False)
        toolbar_tools.setFloatable(False)
        toolbar_tools.setContentsMargins(0, 0, 0, 0)
        toolbar_tools.layout().setSpacing(0)
        toolbar_tools.setStyleSheet(
            "QToolButton { padding: 0px; margin: 0px; spacing: 0px; font-size: 8pt; } "
            "QToolButton:checked { background-color: #b0d4f1; border: 2px solid #005a9e; border-radius: 4px; }")

        action_group = QActionGroup(self)
        action_group.setExclusive(True)
        ic = QColor(220, 30, 30)

        self.pointer_action = self._create_tool_action("Выбор", None, action_group, toolbar_tools,
                                                       icon=create_tool_icon('pointer', QColor(30, 30, 30)),
                                                       tooltip="Выделение")
        self.line_action = self._create_tool_action("Линия", 'line', action_group, toolbar_tools,
                                                    icon=create_tool_icon('line', ic), tooltip="Линия")
        self.rect_action = self._create_tool_action("Контур", 'rect', action_group, toolbar_tools,
                                                    icon=create_tool_icon('rect', ic), tooltip="Контур")
        self.ellipse_action = self._create_tool_action("Эллипс", 'ellipse', action_group, toolbar_tools,
                                                       icon=create_tool_icon('ellipse', ic), tooltip="Эллипс")
        self.arrow_action = self._create_tool_action("Стрелка", 'arrow', action_group, toolbar_tools,
                                                     icon=create_tool_icon('arrow', ic), tooltip="Стрелка")
        self.text_action = self._create_tool_action("Текст", 'text', action_group, toolbar_tools,
                                                    icon=create_tool_icon('text', ic), tooltip="Текст")
        self.pointer_action.setChecked(True)

        for act in action_group.actions():
            btn = toolbar_tools.widgetForAction(act)
            if btn:
                btn.setFixedWidth(self.TOOL_BUTTON_WIDTH)

        self.top_toolbar.addWidget(toolbar_tools)

        self.top_toolbar.addSeparator()

        self.image_toolbar = QToolBar("Изображение")
        self.image_toolbar.setIconSize(QSize(32, 32))
        self.image_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.image_toolbar.setMovable(False)
        self.image_toolbar.setFloatable(False)
        self.image_toolbar.setContentsMargins(0, 0, 0, 0)
        self.image_toolbar.layout().setSpacing(0)
        self.image_toolbar.setStyleSheet(
            "QToolButton { padding: 0px; margin: 0px; spacing: 0px; font-size: 8pt; } "
            "QToolButton:checked { background-color: #b0d4f1; border: 2px solid #005a9e; border-radius: 4px; }")

        self.crop_action = QAction("Обрезать", self)
        self.crop_action.setCheckable(True)
        self.crop_action.setIcon(create_crop_icon())
        self.crop_action.setToolTip("Обрезать изображение")
        self.crop_action.triggered.connect(self._on_crop_action_triggered)
        self.image_toolbar.addAction(self.crop_action)

        self.rotate_cw_action = QAction("Повернуть", self)
        self.rotate_cw_action.setIcon(create_rotate_icon(clockwise=True))
        self.rotate_cw_action.setToolTip("Повернуть на 90° по часовой")
        self.rotate_cw_action.triggered.connect(lambda: self._rotate_image(90))
        self.image_toolbar.addAction(self.rotate_cw_action)

        self.rotate_ccw_action = QAction("Повернуть", self)
        self.rotate_ccw_action.setIcon(create_rotate_icon(clockwise=False))
        self.rotate_ccw_action.setToolTip("Повернуть на 90° против часовой")
        self.rotate_ccw_action.triggered.connect(lambda: self._rotate_image(-90))
        self.image_toolbar.addAction(self.rotate_ccw_action)

        self.blur_action = QAction("Размыть", self)
        self.blur_action.setCheckable(True)
        self.blur_action.setIcon(create_blur_icon())
        self.blur_action.setToolTip("Размыть область")
        self.blur_action.triggered.connect(self._on_blur_action_triggered)
        self.image_toolbar.addAction(self.blur_action)

        for act in self.image_toolbar.actions():
            btn = self.image_toolbar.widgetForAction(act)
            if btn:
                btn.setFixedWidth(self.TOOL_BUTTON_WIDTH)

        self.top_toolbar.addWidget(self.image_toolbar)

        spacer = QWidget()
        spacer.setMinimumWidth(0)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.top_toolbar.addWidget(spacer)

        settings = QToolBar("Опции аннотаций")
        settings.setIconSize(QSize(32, 32))
        settings.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        settings.setMovable(False)
        settings.setFloatable(False)
        settings.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        settings.setContentsMargins(0, 0, 0, 0)
        settings.addSeparator()

        sw = QWidget()
        sl = QVBoxLayout(sw)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(2)
        tr = QHBoxLayout()
        tr.setContentsMargins(0, 0, 0, 0)
        tr.addWidget(self.thickness_widget)
        sl.addLayout(tr)
        cr = QHBoxLayout()
        cr.setContentsMargins(0, 0, 0, 0)
        cr.addWidget(self.color_palette)
        sl.addLayout(cr)
        settings.addWidget(sw)
        self.top_toolbar.addWidget(settings)

        right_spacer = QWidget()
        right_spacer.setFixedWidth(4)
        self.top_toolbar.addWidget(right_spacer)

        self.color_palette.set_current_color(QColor("#FF0000"))
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

        self.setup_global_hotkeys()

        self._update_image_actions_enabled()

        self.view.setFocus()

    # --------------------------------------------------------------
    # Вставка изображений
    # --------------------------------------------------------------
    def insert_image_from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Вставить изображение", "",
                                             "Изображения (*.png *.jpg *.jpeg *.bmp)")
        if path:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.view.add_pasted_image(pixmap)

    def insert_image_from_clipboard(self):
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()

        # 1. Проверяем наличие изображения в буфере
        if mime.hasImage():
            image = clipboard.image()
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                if not pixmap.isNull():
                    self.view.add_pasted_image(pixmap)
                    return

        # 2. Проверяем файлы (например, скопированный файл .png в проводнике)
        if mime.hasUrls():
            for url in mime.urls():
                local_path = url.toLocalFile()
                if local_path and os.path.isfile(local_path):
                    pixmap = QPixmap(local_path)
                    if not pixmap.isNull():
                        self.view.add_pasted_image(pixmap)
                        return

        # Если ничего не удалось вставить
        self.view.show_status_message("Не удалось вставить изображение из буфера.", 5000)

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
            self.pointer_action.setChecked(True)
            self.view.start_crop_mode()

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
        self.insert_image_from_clipboard()

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
    # Остальные методы
    # --------------------------------------------------------------
    def choose_save_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для сохранения скриншотов",
            self.save_directory or os.path.expanduser("~")
        )
        if directory:
            self.save_directory = directory
            settings = QSettings("Screenshooter", "Screenshooter")
            settings.setValue("save_directory", directory)
            return True
        return False

    def show_quick_save_menu(self, pos):
        menu = QMenu(self)
        choose_action = menu.addAction("Выбрать папку...")
        chosen = menu.exec_(self.quick_save_btn.mapToGlobal(pos))
        if chosen == choose_action:
            self.choose_save_directory()

    def quick_save(self):
        img = self.render_scene_to_image()
        if img is None:
            self.view.show_status_message("Нет изображения для сохранения.", 15000)
            return

        if self.save_directory is None:
            if not self.choose_save_directory():
                return

        timestamp = time.strftime("%Y-%m-%d %H-%M-%S")
        filename = f"{timestamp}.png"
        full_path = os.path.join(self.save_directory, filename)

        if img.save(full_path, "PNG"):
            try:
                os.startfile(self.save_directory)
            except Exception:
                pass

            native_path = QDir.toNativeSeparators(full_path)
            self.view.show_status_message(native_path, 15000)
        else:
            self.view.show_status_message("Не удалось сохранить файл.", 15000)

    def _on_scene_selection_changed(self):
        self.view.update_text_format_widget_visibility()
        sel = self.scene.selectedItems()
        if not sel:
            self.thickness_widget.set_value_silent(self.view.pen_width)
            self.color_palette.set_current_color(self.view.current_pen_color)

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
        if self._capture_in_progress:
            return True
        self.capture_monitor_requested.emit()
        return True

    def _on_alt_printscreen_hotkey(self):
        if self._capture_in_progress:
            return
        self.capture_window_requested.emit()

    def _on_ctrl_printscreen_hotkey(self):
        if self._capture_in_progress:
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

    def closeEvent(self, e):
        try:
            self._remove_keyboard_hooks()
        except Exception:
            pass
        e.accept()

    def _create_tool_action(self, text, tool_name, group, toolbar, icon=None, tooltip=None):
        act = QAction(text, self)
        act.setCheckable(True)
        if icon:
            act.setIcon(icon)
        if tooltip:
            act.setToolTip(tooltip)
        act.triggered.connect(lambda: self.set_tool(tool_name))
        toolbar.addAction(act)
        group.addAction(act)
        return act

    def set_tool(self, tn):
        self.view.set_tool(tn)
        self.thickness_widget.set_value_silent(self.view.get_current_width())
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

    def capture_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            self.screenshot_pixmap = screen.grabWindow(0)
            self.display_screenshot()

    def display_screenshot(self):
        self.view.clear_pasted_images()
        self.scene.clear()
        self.view.active_text_item = None
        self.view.history.clear()

        item = QGraphicsPixmapItem(self.screenshot_pixmap)
        item.setTransformationMode(Qt.SmoothTransformation)
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

    def render_scene_to_image(self):
        bg = self.view.background_item
        if bg is None or sip.isdeleted(bg):
            return None
        bg_pixmap = bg.pixmap()
        if bg_pixmap.isNull():
            return None

        self.view.image_editor.hide_blur_regions_for_render()
        self.view.hide_pasted_image_handles_for_render()

        target = bg_pixmap.rect()
        img = QImage(target.size(), QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        self.scene.render(p, QRectF(img.rect()), QRectF(target))
        p.end()

        self.view.image_editor.show_blur_regions_after_render()
        self.view.show_pasted_image_handles_after_render()
        return img

    def save_image(self):
        img = self.render_scene_to_image()
        if img is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить изображение", "",
                                              "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp)")
        if path:
            img.save(path)

    def copy_to_clipboard(self):
        img = self.render_scene_to_image()
        if img is not None:
            QApplication.clipboard().setImage(img)

    def delete_selected(self):
        self.view.delete_selected()

    def _restore_main_window(self, force_maximized=False):
        if force_maximized:
            self.showMaximized()
        else:
            if self._window_state_before_capture and (self._window_state_before_capture & Qt.WindowMaximized):
                self.showMaximized()
            else:
                self.showNormal()
        self.activateWindow()
        self.raise_()
        QApplication.processEvents()
        self.view.setFocus()

    def capture_monitor(self):
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        try:
            self._window_state_before_capture = self.windowState()
            self.hide()
            QApplication.processEvents()
            overlay = ScreenCaptureOverlay()
            overlay.activateWindow()
            overlay.raise_()
            QApplication.processEvents()
            res = overlay.exec_()
            self._restore_main_window(force_maximized=True)
            if res == QDialog.Accepted:
                pm = overlay.get_pixmap()
                if pm is not None:
                    self.screenshot_pixmap = pm
                    self.display_screenshot()
        except Exception as e:
            self._restore_main_window(force_maximized=True)
            print(f"Ошибка захвата монитора: {e}")
        finally:
            self._capture_in_progress = False

    def capture_region(self):
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        try:
            self._window_state_before_capture = self.windowState()
            self.hide()
            QApplication.processEvents()
            QTimer.singleShot(30, self._start_region_capture)
        except Exception as e:
            self._capture_in_progress = False
            self._restore_main_window()
            print(f"Ошибка запуска захвата области: {e}")

    def _start_region_capture(self):
        try:
            overlay = RegionCaptureOverlay()
            overlay.activateWindow()
            overlay.raise_()
            QApplication.processEvents()
            res = overlay.exec_()
            self._restore_main_window()
            if res == QDialog.Accepted:
                pm = overlay.get_pixmap()
                if pm is not None:
                    self.screenshot_pixmap = pm
                    self.display_screenshot()
        except Exception as e:
            self._restore_main_window()
            print(f"Ошибка захвата области: {e}")
        finally:
            self._capture_in_progress = False

    def capture_window(self):
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        try:
            self._window_state_before_capture = self.windowState()
            self.hide()
            QApplication.processEvents()
            pixmap = capture_active_window()
            QTimer.singleShot(0, self._restore_main_window)
            if pixmap is not None:
                self.screenshot_pixmap = pixmap
                self.display_screenshot()
            else:
                self.view.show_status_message("Не удалось захватить активное окно.", 15000)
        except Exception as e:
            QTimer.singleShot(0, self._restore_main_window)
            print(f"Ошибка захвата активного окна: {e}")
            self.view.show_status_message("Не удалось захватить активное окно.", 15000)
        finally:
            self._capture_in_progress = False