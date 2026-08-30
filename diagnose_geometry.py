"""
Диагностика геометрии для UI-рефакторинга Шаг 5.

Запуск:
    python diagnose_geometry.py

Создаёт приложение, показывает окно, обрабатывает события,
выводит фактические размеры и отступы ключевых виджетов.
"""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPixmap, QColor

from screenshooter.app import ScreenshotApp
from screenshooter.theme import theme_manager
from screenshooter.ui.annotation_toolbar import AnnotationToolbar
from screenshooter.ui.image_toolbar import ImageToolbar
from screenshooter.ui.options_toolbar import OptionsToolbar
from screenshooter.ui.editor_toolbar_strip import EditorToolbarStrip


def print_geometry(label, widget):
    """Печатает geometry(), sizeHint() и minimumSizeHint() виджета."""
    if widget is None:
        print(f"{label:20s} | NOT FOUND")
        return
    geo = widget.geometry()
    sh = widget.sizeHint()
    msh = widget.minimumSizeHint()
    print(
        f"{label:20s} | geometry=({geo.x()},{geo.y()},{geo.width()}x{geo.height()}) "
        f"sizeHint=({sh.width()}x{sh.height()}) "
        f"minSizeHint=({msh.width()}x{msh.height()})"
    )


def main():
    app = QApplication(sys.argv)
    theme_manager.apply(app)

    win = ScreenshotApp()

    # Загружаем тестовую подложку
    pm = QPixmap(800, 600)
    pm.fill(QColor(199, 210, 223))
    win.view.set_background_from_pixmap(pm)

    win.show()
    app.processEvents()

    # Получаем компоненты по типам
    annotation_toolbar = win.findChild(AnnotationToolbar)
    image_toolbar = win.findChild(ImageToolbar)
    options_toolbar = win.findChild(OptionsToolbar)
    editor_toolbar_strip = win.findChild(EditorToolbarStrip)

    # MainActionBar — первый виджет в центральном layout
    central_layout = win.centralWidget().layout()
    top_actions_widget = central_layout.itemAt(0).widget() if central_layout.count() > 0 else None

    # Вывод основных строк
    print_geometry("MainActionBar", top_actions_widget)
    print_geometry("EditorToolbarStrip", editor_toolbar_strip)
    print_geometry("EditorView", win.view)

    # Вывод компонентов полосы
    print_geometry("AnnotationToolbar", annotation_toolbar)
    print_geometry("ImageToolbar", image_toolbar)
    print_geometry("OptionsToolbar", options_toolbar)
    print_geometry("ThicknessWidget", win.thickness_widget)
    print_geometry("ColorPaletteWidget", win.color_palette)

    # Внутренняя геометрия EditorView
    if win.view:
        print(f"EditorView.contentsRect: {win.view.contentsRect()}")
        print(f"EditorView.viewport geometry: {win.view.viewport().geometry()}")

    # Горизонтальные/вертикальные отступы
    if editor_toolbar_strip and win.view:
        print(
            f"EditorToolbarStrip.left={editor_toolbar_strip.geometry().left()} "
            f"EditorView.left={win.view.geometry().left()}"
        )
        print(
            f"EditorToolbarStrip.right={editor_toolbar_strip.geometry().right()} "
            f"EditorView.right={win.view.geometry().right()}"
        )
    if top_actions_widget and editor_toolbar_strip:
        print(
            f"MainActionBar.bottom={top_actions_widget.geometry().bottom()} "
            f"EditorToolbarStrip.top={editor_toolbar_strip.geometry().top()}"
        )
        print(
            f"EditorToolbarStrip.bottom={editor_toolbar_strip.geometry().bottom()} "
            f"EditorView.top={win.view.geometry().top()}"
        )

    sys.exit(0)


if __name__ == "__main__":
    main()