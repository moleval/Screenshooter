"""
Прототип Шаг 4 (версия 4): проверка плоской композиции тулбаров.

Использует реальные метрики из layout_metrics.py, тему из theme.py
и иконки из widgets/tool_icons.py.

Компоненты тулбаров созданы локально на основе QWidget (имитация конвертации).

Окна:
  1. БЫЛО  — текущая архитектура: QToolBar через addToolBar
  2. СТАЛО — новая архитектура: EditorToolbarStrip (QWidget + QHBoxLayout)

Запуск из корня проекта:
    python prototype_step4_v4.py
"""

import sys
sys.path.insert(0, '.')

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QIcon, QPixmap, QPainter
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                             QToolBar, QAction, QVBoxLayout, QLabel,
                             QFrame, QSizePolicy, QToolButton, QPushButton)

from screenshooter.ui.layout_metrics import (
    TOOL_BUTTON_WIDTH,
    TOOLBAR_ICON_SIZE,
    TOOLBAR_SPACING,
    TOOLBAR_MARGIN,
    MAIN_LAYOUT_MARGIN,
    MAIN_LAYOUT_SPACING,
    TOP_ACTIONS_SPACING,
    LEFT_SPACER_WIDTH,
    RIGHT_SPACER_WIDTH,
)
from screenshooter.widgets.tool_icons import (
    create_tool_icon,
    create_crop_icon,
    create_rotate_icon,
    create_blur_icon,
)
from screenshooter.theme import theme_manager

# ==============================================================
# Метрики разделителя (войдут в layout_metrics на Шаге 5)
# ==============================================================
SEPARATOR_LINE_WIDTH = 1
SEPARATOR_H_MARGIN = 6
SEPARATOR_V_MARGIN = 8


# ==============================================================
# Измерение эталонной высоты кнопки
# ==============================================================
def measure_button_height():
    """Измеряет высоту кнопки тулбара (иконка + текст)."""
    btn = QToolButton()
    btn.setText("Измерение")
    btn.setIcon(create_tool_icon('pointer', QColor(30, 30, 30)))
    btn.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
    btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    return btn.sizeHint().height()


# ==============================================================
# Локальные компоненты (имитация конвертированных тулбаров)
# ==============================================================
class AnnotationToolbarLocal(QWidget):
    """Аннотации: 6 кнопок на основе QToolButton."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(TOOLBAR_MARGIN, TOOLBAR_MARGIN,
                                  TOOLBAR_MARGIN, TOOLBAR_MARGIN)
        layout.setSpacing(TOOLBAR_SPACING)

        icons = [
            ("Выбор",   create_tool_icon('pointer', QColor(30, 30, 30))),
            ("Линия",   create_tool_icon('line', QColor(220, 30, 30))),
            ("Контур",  create_tool_icon('rect', QColor(220, 30, 30))),
            ("Эллипс",  create_tool_icon('ellipse', QColor(220, 30, 30))),
            ("Стрелка", create_tool_icon('arrow', QColor(220, 30, 30))),
            ("Текст",   create_tool_icon('text', QColor(220, 30, 30))),
        ]

        self._buttons = []
        for name, icon in icons:
            btn = QToolButton(self)
            btn.setText(name)
            btn.setIcon(icon)
            btn.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setCheckable(True)
            btn.setFixedWidth(TOOL_BUTTON_WIDTH)
            btn.setToolTip(name)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            layout.addWidget(btn)
            self._buttons.append(btn)


class ImageToolbarLocal(QWidget):
    """Изображение: 4 кнопки на основе QToolButton."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(TOOLBAR_MARGIN, TOOLBAR_MARGIN,
                                  TOOLBAR_MARGIN, TOOLBAR_MARGIN)
        layout.setSpacing(TOOLBAR_SPACING)

        icons = [
            ("Обрезать",  create_crop_icon()),
            ("Повернуть", create_rotate_icon(clockwise=True)),
            ("Повернуть", create_rotate_icon(clockwise=False)),
            ("Размыть",   create_blur_icon()),
        ]

        self._buttons = []
        for name, icon in icons:
            btn = QToolButton(self)
            btn.setText(name)
            btn.setIcon(icon)
            btn.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setFixedWidth(TOOL_BUTTON_WIDTH)
            btn.setToolTip(name)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            layout.addWidget(btn)
            self._buttons.append(btn)


class OptionsToolbarLocal(QWidget):
    """Опции: двухрядный виджет (толщина + палитра)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        thickness = QLabel("Толщина: [======|=====]")
        thickness.setStyleSheet("color: #333; font-size: 11px;")
        thickness.setAlignment(Qt.AlignCenter)

        palette = QLabel("● ● ● ● ● ● ● ● ●")
        palette.setStyleSheet("color: #c00; font-size: 14px;")
        palette.setAlignment(Qt.AlignCenter)

        layout.addStretch(1)
        layout.addWidget(thickness)
        layout.addStretch(2)
        layout.addWidget(palette)
        layout.addStretch(1)


class ToolbarSeparatorLocal(QWidget):
    """Разделитель: обёртка с отступами вокруг тонкой линии."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toolbarSeparator")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            SEPARATOR_H_MARGIN, SEPARATOR_V_MARGIN,
            SEPARATOR_H_MARGIN, SEPARATOR_V_MARGIN,
        )
        layout.setSpacing(0)

        line = QFrame(self)
        line.setObjectName("toolbarSeparatorLine")
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Plain)
        line.setFixedWidth(SEPARATOR_LINE_WIDTH)
        layout.addWidget(line)


class EditorToolbarStripLocal(QWidget):
    """Плоская композиция тулбаров."""

    def __init__(self, annotation_toolbar, image_toolbar, options_toolbar, parent=None):
        super().__init__(parent)
        self.setObjectName("editorToolbarStrip")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TOOLBAR_SPACING)

        layout.addWidget(annotation_toolbar)
        layout.addWidget(ToolbarSeparatorLocal())
        layout.addWidget(image_toolbar)
        layout.addStretch(1)
        layout.addWidget(options_toolbar)


# ==============================================================
# MainActionBar
# ==============================================================
def create_main_action_bar(parent=None):
    widget = QWidget(parent)
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(TOP_ACTIONS_SPACING)

    for text in ["Отменить", "Повторить", "Снимок", "Очистить"]:
        layout.addWidget(QPushButton(text))

    layout.addStretch(1)

    for text in ["В буфер", "Вставить файл", "Из буфера", "Сохранить как", "Сохранить"]:
        layout.addWidget(QPushButton(text))

    return widget


# ==============================================================
# ОКНО 1: БЫЛО — текущая архитектура
# ==============================================================
def create_old_window():
    win = QMainWindow()
    win.setWindowTitle("БЫЛО: QToolBar через addToolBar")
    win.resize(1000, 400)

    top_toolbar = QToolBar("Панель инструментов")
    top_toolbar.setMovable(False)
    top_toolbar.setFloatable(False)
    top_toolbar.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
    top_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    top_toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    top_toolbar.setContentsMargins(0, 0, 0, 0)

    left_spacer = QWidget()
    left_spacer.setFixedWidth(LEFT_SPACER_WIDTH)
    top_toolbar.addWidget(left_spacer)

    # Аннотации
    ann_tb = QToolBar("Аннотации")
    ann_tb.setMovable(False)
    ann_tb.setFloatable(False)
    ann_tb.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
    ann_tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    ann_tb.setContentsMargins(0, 0, 0, 0)
    ann_tb.layout().setSpacing(0)

    icons = [
        ("Выбор",   create_tool_icon('pointer', QColor(30, 30, 30))),
        ("Линия",   create_tool_icon('line', QColor(220, 30, 30))),
        ("Контур",  create_tool_icon('rect', QColor(220, 30, 30))),
        ("Эллипс",  create_tool_icon('ellipse', QColor(220, 30, 30))),
        ("Стрелка", create_tool_icon('arrow', QColor(220, 30, 30))),
        ("Текст",   create_tool_icon('text', QColor(220, 30, 30))),
    ]
    for name, icon in icons:
        act = QAction(name, ann_tb)
        act.setIcon(icon)
        act.setCheckable(True)
        ann_tb.addAction(act)
        btn = ann_tb.widgetForAction(act)
        if btn:
            btn.setFixedWidth(TOOL_BUTTON_WIDTH)
    top_toolbar.addWidget(ann_tb)

    # Изображение
    img_tb = QToolBar("Изображение")
    img_tb.setMovable(False)
    img_tb.setFloatable(False)
    img_tb.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
    img_tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    img_tb.setContentsMargins(0, 0, 0, 0)
    img_tb.layout().setSpacing(0)

    icons = [
        ("Обрезать",  create_crop_icon()),
        ("Повернуть", create_rotate_icon(clockwise=True)),
        ("Повернуть", create_rotate_icon(clockwise=False)),
        ("Размыть",   create_blur_icon()),
    ]
    for name, icon in icons:
        act = QAction(name, img_tb)
        act.setIcon(icon)
        img_tb.addAction(act)
        btn = img_tb.widgetForAction(act)
        if btn:
            btn.setFixedWidth(TOOL_BUTTON_WIDTH)
    top_toolbar.addWidget(img_tb)

    # Растягивающийся спейсер
    expanding_spacer = QWidget()
    expanding_spacer.setMinimumWidth(0)
    expanding_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    top_toolbar.addWidget(expanding_spacer)

    # Опции
    opts = QToolBar("Опции")
    opts.setMovable(False)
    opts.setFloatable(False)
    opts.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
    opts.setContentsMargins(0, 0, 0, 0)

    container = QWidget()
    vlayout = QVBoxLayout(container)
    vlayout.setContentsMargins(0, 0, 0, 0)
    vlayout.setSpacing(2)
    t = QLabel("Толщина: [======|=====]")
    t.setStyleSheet("color: #333; font-size: 11px;")
    p = QLabel("● ● ● ● ● ● ● ● ●")
    p.setStyleSheet("color: #c00; font-size: 14px;")
    vlayout.addWidget(t)
    vlayout.addWidget(p)
    opts.addWidget(container)
    top_toolbar.addWidget(opts)

    right_spacer = QWidget()
    right_spacer.setFixedWidth(RIGHT_SPACER_WIDTH)
    top_toolbar.addWidget(right_spacer)

    win.addToolBar(Qt.TopToolBarArea, top_toolbar)

    central = QWidget()
    v_layout = QVBoxLayout(central)
    v_layout.setContentsMargins(MAIN_LAYOUT_MARGIN, MAIN_LAYOUT_MARGIN,
                               MAIN_LAYOUT_MARGIN, MAIN_LAYOUT_MARGIN)
    v_layout.setSpacing(MAIN_LAYOUT_SPACING)
    v_layout.addWidget(create_main_action_bar())

    editor = QLabel("Центральный виджет (поле редактирования)")
    editor.setAlignment(Qt.AlignCenter)
    editor.setStyleSheet("background-color: #e8f0f8; border: 1px solid #b0c4de;")
    editor.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
    v_layout.addWidget(editor, 1)

    win.setCentralWidget(central)
    return win


# ==============================================================
# ОКНО 2: СТАЛО — плоская композиция
# ==============================================================
def create_new_window():
    win = QMainWindow()
    win.setWindowTitle("СТАЛО: EditorToolbarStrip (плоская композиция)")
    win.resize(1000, 400)

    central = QWidget()
    main_layout = QVBoxLayout(central)
    main_layout.setContentsMargins(MAIN_LAYOUT_MARGIN, MAIN_LAYOUT_MARGIN,
                                   MAIN_LAYOUT_MARGIN, MAIN_LAYOUT_MARGIN)
    main_layout.setSpacing(MAIN_LAYOUT_SPACING)

    main_layout.addWidget(create_main_action_bar())

    ann = AnnotationToolbarLocal()
    img = ImageToolbarLocal()
    opts = OptionsToolbarLocal()
    strip = EditorToolbarStripLocal(ann, img, opts)

    # Фиксируем высоту полосы по высоте кнопки
    button_height = measure_button_height()
    strip.setFixedHeight(button_height)

    main_layout.addWidget(strip)

    editor = QLabel("Центральный виджет (поле редактирования)")
    editor.setAlignment(Qt.AlignCenter)
    editor.setStyleSheet("background-color: #e8f0f8; border: 1px solid #b0c4de;")
    editor.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
    main_layout.addWidget(editor, 1)

    win.setCentralWidget(central)
    return win


# ==============================================================
# Запуск
# ==============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    theme_manager.apply(app)

    win_old = create_old_window()
    win_new = create_new_window()

    win_old.move(50, 50)
    win_new.move(100, 500)

    win_old.show()
    win_new.show()

    sys.exit(app.exec_())