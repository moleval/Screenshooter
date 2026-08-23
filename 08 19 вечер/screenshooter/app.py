"""Главное окно приложения."""

import sys
import keyboard
from PyQt5.QtCore import Qt, QRectF, QSize, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QImage, QColor, QIcon
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsScene,
                             QGraphicsPixmapItem, QToolBar, QActionGroup, QAction, QFileDialog,
                             QMessageBox, QApplication, QSizePolicy, QDialog)

from .capture.screen_overlay import ScreenCaptureOverlay
from .capture.region_overlay import RegionCaptureOverlay
from .capture.window_capture import capture_active_window
from .view import EditorView
from .widgets.thickness import ThicknessWidget
from .widgets.color_palette import ColorPaletteWidget
from .widgets.tool_icons import create_tool_icon


class ScreenshotApp(QMainWindow):
    capture_printscreen_requested = pyqtSignal()
    capture_alt_printscreen_requested = pyqtSignal()
    capture_ctrl_printscreen_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Скриншотер с редактором")
        self.setGeometry(100, 100, 1000, 750)
        self.setMinimumSize(950, 650)

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
        p_icon = create_tool_icon('pointer', QColor(30, 30, 30))
        l_icon = create_tool_icon('line', ic)
        r_icon = create_tool_icon('rect', ic)
        e_icon = create_tool_icon('ellipse', ic)
        a_icon = create_tool_icon('arrow', ic)
        t_icon = create_tool_icon('text', ic)

        self.pointer_action = self._create_tool_action("Выбор", None, action_group, toolbar_tools, icon=p_icon, tooltip="Выделение")
        self.line_action = self._create_tool_action("Линия", 'line', action_group, toolbar_tools, icon=l_icon, tooltip="Линия")
        self.rect_action = self._create_tool_action("Контур", 'rect', action_group, toolbar_tools, icon=r_icon, tooltip="Контур")
        self.ellipse_action = self._create_tool_action("Эллипс", 'ellipse', action_group, toolbar_tools, icon=e_icon, tooltip="Эллипс")
        self.arrow_action = self._create_tool_action("Стрелка", 'arrow', action_group, toolbar_tools, icon=a_icon, tooltip="Стрелка")
        self.text_action = self._create_tool_action("Текст", 'text', action_group, toolbar_tools, icon=t_icon, tooltip="Текст")
        self.pointer_action.setChecked(True)

        for act in action_group.actions():
            btn = toolbar_tools.widgetForAction(act)
            if btn:
                btn.setFixedWidth(58)

        self.top_toolbar.addWidget(toolbar_tools)

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

        self.capture_printscreen_requested.connect(self.capture_printscreen)
        self.capture_alt_printscreen_requested.connect(self.capture_alt_printscreen)
        self.capture_ctrl_printscreen_requested.connect(self.capture_ctrl_printscreen)

        self.setup_global_hotkeys()

    def setup_global_hotkeys(self):
        try:
            keyboard.add_hotkey('print screen', self._on_printscreen, suppress=True)
            keyboard.add_hotkey('alt+print screen', self._on_alt_printscreen, suppress=True)
            keyboard.add_hotkey('ctrl+print screen', self._on_ctrl_printscreen, suppress=True)
            print("Глобальные горячие клавиши зарегистрированы.")
        except Exception as e:
            print(f"Ошибка регистрации горячих клавиш: {e}")

    def _on_printscreen(self):
        self.capture_printscreen_requested.emit()

    def _on_alt_printscreen(self):
        self.capture_alt_printscreen_requested.emit()

    def _on_ctrl_printscreen(self):
        self.capture_ctrl_printscreen_requested.emit()

    def closeEvent(self, e):
        try:
            keyboard.unhook_all()
        except:
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

    def change_width(self, v):
        self.view.set_pen_width(v)

    def set_color_from_palette(self, c):
        self.view.set_pen_color(c)
        self.view.apply_current_style_to_selected()

    def set_zoom(self, p):
        self.user_zoomed = True
        self.view.auto_fit = False
        scale = p / 100
        self.view.resetTransform()
        self.view.scale(scale, scale)
        self.view.zoom_widget.set_zoom(p)

    def _on_view_zoom_changed(self, p):
        self.user_zoomed = True
        self.view.auto_fit = False
        self.view.zoom_widget.set_zoom(p)

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

    def capture_printscreen(self):
        self.hide()
        overlay = ScreenCaptureOverlay()
        res = overlay.exec_()
        self.show()
        if res == QDialog.Accepted:
            pm = overlay.get_pixmap()
            if pm is not None:
                self.screenshot_pixmap = pm
                self.display_screenshot()

    def capture_alt_printscreen(self):
        self.hide()
        overlay = RegionCaptureOverlay()
        res = overlay.exec_()
        self.show()
        if res == QDialog.Accepted:
            pm = overlay.get_pixmap()
            if pm is not None:
                self.screenshot_pixmap = pm
                self.display_screenshot()

    def capture_ctrl_printscreen(self):
        pixmap = capture_active_window()
        if pixmap is not None:
            self.screenshot_pixmap = pixmap
            self.display_screenshot()
        else:
            QMessageBox.information(self, "Информация", "Не удалось захватить активное окно.")