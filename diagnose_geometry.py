"""
Диагностика геометрии UI после рефакторинга (Шаг 8).
Выводит размеры ключевых виджетов и проверяет контракт EditorToolbarStrip.
Запуск: python diagnose_geometry.py
"""

import sys
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtGui import QPixmap, QColor

from screenshooter.app import ScreenshotApp
from screenshooter.theme import theme_manager
from screenshooter.ui.annotation_toolbar import AnnotationToolbar
from screenshooter.ui.image_toolbar import ImageToolbar
from screenshooter.ui.options_toolbar import OptionsToolbar
from screenshooter.ui.editor_toolbar_strip import EditorToolbarStrip


def print_geometry(label, widget):
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


def check_strip_contract(strip, view):
    """Проверяет контракт EditorToolbarStrip и выводит результат."""
    print("\n--- Контракт EditorToolbarStrip ---")
    ann = None
    img = None
    opt = None
    for child in strip.findChildren(QWidget):
        name = child.__class__.__name__
        if name == "AnnotationToolbar":
            ann = child
        elif name == "ImageToolbar":
            img = child
        elif name == "OptionsToolbar":
            opt = child

    if not ann or not img or not opt:
        print("Не удалось найти все тулбары внутри EditorToolbarStrip")
        return

    ann_min = ann.minimumSizeHint().width()
    img_min = img.minimumSizeHint().width()
    opt_min = opt.minimumSizeHint().width()

    strip_min = strip.minimumSizeHint().width()

    sep_widgets = [w for w in strip.findChildren(QWidget) if w.__class__.__name__ == "ToolbarSeparator"]
    sep_width = sum(w.minimumSizeHint().width() for w in sep_widgets)

    expected_min = ann_min + img_min + opt_min + sep_width

    print(f"AnnotationToolbar min width: {ann_min}")
    print(f"ImageToolbar min width: {img_min}")
    print(f"OptionsToolbar min width: {opt_min}")
    print(f"Separator total width: {sep_width}")
    print(f"Ожидаемый strip min: {expected_min}")
    print(f"Фактический strip min: {strip_min}")

    if strip_min >= expected_min:
        print("Контракт выполнен: strip_min >= сумма компонентов")
    else:
        print("НАРУШЕНИЕ: strip_min меньше суммы компонентов")

    if view:
        vp_left = view.geometry().left()
        strip_left = strip.geometry().left()
        vp_right = view.geometry().right()
        strip_right = strip.geometry().right()
        print(f"Left edges: strip={strip_left}, view={vp_left}, diff={abs(strip_left-vp_left)}")
        print(f"Right edges: strip={strip_right}, view={vp_right}, diff={abs(strip_right-vp_right)}")
        if abs(strip_left - vp_left) <= 1 and abs(strip_right - vp_right) <= 1:
            print("Выравнивание границ: OK")
        else:
            print("Выравнивание границ: НАРУШЕНИЕ")


def check_thickness_clipping(app):
    """Проверяет, что тексты x1...x20 не обрезаны, а слайдер не касается соседей."""
    print("\n--- Thickness/Options regression ---")
    tw = app.thickness_widget
    for btn in tw.preset_buttons:
        text_width = btn.fontMetrics().horizontalAdvance(btn.text())
        btn_width = btn.width()
        if btn_width < text_width:
            print(f"Кнопка '{btn.text()}': ТЕКСТ ОБРЕЗАН! ширина кнопки={btn_width}, ширина текста={text_width}")
        else:
            print(f"Кнопка '{btn.text()}': OK (padding={(btn_width-text_width)//2})")

    layout = tw.layout()
    spacing = layout.spacing()
    print(f"Spacing внутри ThicknessWidget: {spacing}")

    slider = tw.slider
    value_edit = tw.value_edit
    slider_right = slider.geometry().right()
    edit_left = value_edit.geometry().left()
    gap = edit_left - slider_right
    print(f"Зазор между слайдером и полем ввода: {gap} px (ожидается >= {spacing})")
    if gap < spacing:
        print("ВОЗМОЖНОЕ КАСАНИЕ!")
    else:
        print("Зазор достаточный")


def main():
    app = QApplication(sys.argv)
    theme_manager.apply(app)

    win = ScreenshotApp()

    pm = QPixmap(800, 600)
    pm.fill(QColor(199, 210, 223))
    win.view.set_background_from_pixmap(pm)

    win.show()
    app.processEvents()

    top_actions_widget = win.top_actions_widget
    editor_toolbar_strip = win.editor_toolbar_strip

    print_geometry("MainActionBar", top_actions_widget)
    print_geometry("EditorToolbarStrip", editor_toolbar_strip)
    print_geometry("EditorView", win.view)

    ann = None
    img = None
    opt = None
    for child in editor_toolbar_strip.findChildren(QWidget):
        name = child.__class__.__name__
        if name == "AnnotationToolbar":
            ann = child
        elif name == "ImageToolbar":
            img = child
        elif name == "OptionsToolbar":
            opt = child
    print_geometry("AnnotationToolbar", ann)
    print_geometry("ImageToolbar", img)
    print_geometry("OptionsToolbar", opt)
    print_geometry("ThicknessWidget", win.thickness_widget)
    print_geometry("ColorPaletteWidget", win.color_palette)

    check_strip_contract(editor_toolbar_strip, win.view)
    check_thickness_clipping(win)

    print(f"\nМинимальная ширина окна: {win.minimumWidth()} px")

    sys.exit(0)


if __name__ == "__main__":
    main()