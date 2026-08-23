"""Главное окно приложения."""

import sys
import keyboard
from PyQt5.QtCore import Qt, QRectF, QSize, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QImage, QColor, QIcon
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QGraphicsScene, QGraphicsPixmapItem, QToolBar, QActionGroup,
                             QAction, QFileDialog, QMessageBox, QApplication, QSizePolicy, QDialog)

from .capture.screen_overlay import ScreenCaptureOverlay
from .capture.region_overlay import RegionCaptureOverlay
from .capture.window_capture import capture_active_window
from .view import EditorView
from .widgets.thickness import ThicknessWidget
from .widgets.color_palette import ColorPaletteWidget
from .widgets.tool_icons import create_tool_icon


class ScreenshotApp(QMainWindow):
    # Сигналы, соответствующие действиям
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

        cw = QWidget()
        self.setCentralWidget(cw)
        layout = QVBoxLayout(cw)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(4)

        self.capture_btn = QPushButton("Сделать скриншот")
        self.capture_btn.clicked.connect(self.capture_screen)
        layout.addWidget(self.capture_btn)

        self.scene = QGraphicsScene()
        self.view = EditorView(self.scene)
        layout.addWidget(self.view)
        self.view.zoomChangedByWheel.connect(self._on_view_zoom_changed)

        self.thickness_widget = ThicknessWidget()
        self.thickness_widget.valueChanged.connect(self.change_width)
        self.color_palette = ColorPaletteWidget()
        self.color_palette.colorSelected.connect(self.set_color_from_palette)

        # Тулбар
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
        toolbar_tools.setIconSize(QSize(26, 26))
        toolbar_tools.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        toolbar_tools.setMovable(False)
        toolbar_tools.setFloatable(False)
        toolbar_tools.setContentsMargins(0, 0, 0, 0)
        toolbar_tools.layout().setSpacing(0)
        toolbar_tools.setStyleSheet(
            "QToolButton { padding: 0px; margin: 0px; spacing: 0px; font-size: 8pt; min-width: 0px; max-width: 58px; } "
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
                btn.setFixedWidth(58)

        self.top_toolbar.addWidget(toolbar_tools)

        # Разделитель справа от панели Аннотации
        self.top_toolbar.addSeparator()

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

        self.scene.selectionChanged.connect(self.view.update_text_format_widget_visibility)
        QTimer.singleShot(0, self.view.update_text_format_widget_visibility)

        # Подключение сигналов к соответствующим действиям
        self.capture_monitor_requested.connect(self.capture_monitor)
        self.capture_window_requested.connect(self.capture_window)
        self.capture_region_requested.connect(self.capture_region)

        self.setup_global_hotkeys()

        # Возвращаем фокус на холст после инициализации
        self.view.setFocus()

    def setup_global_hotkeys(self):
        self._remove_keyboard_hooks()
        try:
            # Alt+PrintScreen -> захват активного окна
            self._alt_printscreen_hotkey = keyboard.add_hotkey(
                "alt+print screen", self._on_alt_printscreen_hotkey,
                suppress=True, trigger_on_release=False)
            # Ctrl+PrintScreen -> выделение области
            self._ctrl_printscreen_hotkey = keyboard.add_hotkey(
                "ctrl+print screen", self._on_ctrl_printscreen_hotkey,
                suppress=True, trigger_on_release=False)
            # Обычный PrintScreen -> выбор монитора
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
        self.view.set_pen_width(v)
        self.view.setFocus()

    def set_color_from_palette(self, c):
        self.view.set_pen_color(c)
        self.view.apply_current_style_to_selected()
        self.view._update_info_widget_content(c, self.view.get_current_width())
        self.view.setFocus()

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
        self.scene.clear()
        self.view.active_text_item = None
        item = QGraphicsPixmapItem(self.screenshot_pixmap)
        item.setTransformationMode(Qt.SmoothTransformation)
        self.scene.addItem(item)
        self.view.setSceneRect(QRectF(self.screenshot_pixmap.rect()))
        self.view.auto_fit = True
        self.user_zoomed = False
        self.view.fitInView(item, Qt.KeepAspectRatio)
        scale = self.view.transform().m11() * 100
        self.view.zoom_widget.set_zoom(scale)

    def render_scene_to_image(self):
        if not self.screenshot_pixmap:
            return None
        target = self.screenshot_pixmap.rect()
        img = QImage(target.size(), QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        self.scene.render(p, QRectF(img.rect()), QRectF(target))
        p.end()
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

    def _restore_main_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()
        QApplication.processEvents()
        self.view.setFocus()

    # --------------------------------------------------------------
    # Захват монитора (PrintScreen)
    # --------------------------------------------------------------
    def capture_monitor(self):
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        try:
            self.hide()
            QApplication.processEvents()
            overlay = ScreenCaptureOverlay()
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
            print(f"Ошибка захвата монитора: {e}")
        finally:
            self._capture_in_progress = False

    # --------------------------------------------------------------
    # Захват области (Ctrl+PrintScreen)
    # --------------------------------------------------------------
    def capture_region(self):
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        try:
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

    # --------------------------------------------------------------
    # Захват активного окна (Alt+PrintScreen)
    # --------------------------------------------------------------
    def capture_window(self):
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        try:
            self.hide()
            QApplication.processEvents()
            pixmap = capture_active_window()
            QTimer.singleShot(0, self._restore_main_window)
            if pixmap is not None:
                self.screenshot_pixmap = pixmap
                self.display_screenshot()
            else:
                QMessageBox.information(self, "Информация", "Не удалось захватить активное окно.")
        except Exception as e:
            QTimer.singleShot(0, self._restore_main_window)
            print(f"Ошибка захвата активного окна: {e}")
            QMessageBox.warning(self, "Ошибка", "Не удалось захватить активное окно.")
        finally:
            self._capture_in_progress = False