import pytest
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import QApplication
from screenshooter.theme import theme_manager

from screenshooter.widgets.icon_manager import IconManager


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.mark.parametrize(
    "name",
    [
        "pointer",
        "line",
        "rect",
        "ellipse",
        "arrow",
        "text",
        "crop",
        "blur",
        "rotate-cw",
        "undo",
        "redo",
    ],
)
def test_icon_manager_loads_all_local_icons(qapp, name):
    icon = IconManager.icon(name)

    assert not icon.isNull()
    normal = icon.pixmap(IconManager.ICON_SIZE, QIcon.Normal, QIcon.Off)
    disabled = icon.pixmap(IconManager.ICON_SIZE, QIcon.Disabled, QIcon.Off)

    assert not normal.isNull()
    assert not disabled.isNull()


def _nontransparent_pixels(pixmap):
    image = pixmap.toImage()
    return [
        QColor(image.pixel(x, y))
        for y in range(image.height())
        for x in range(image.width())
        if QColor(image.pixel(x, y)).alpha() > 0
    ]


def _has_color_close_to(pixmap, expected, tolerance=8):
    return any(
        abs(c.red() - expected[0]) <= tolerance
        and abs(c.green() - expected[1]) <= tolerance
        and abs(c.blue() - expected[2]) <= tolerance
        for c in _nontransparent_pixels(pixmap)
    )


def test_icon_manager_uses_semantic_colors(qapp):
    annotation = IconManager._render(
        IconManager._ROOT / "annotation" / "square.svg",
        IconManager._color_for_category(IconManager.ANNOTATION),
    )
    editing = IconManager._render(
        IconManager._ROOT / "editing" / "crop.svg",
        IconManager._color_for_category(IconManager.EDITING),
    )
    selection = IconManager._render(
        IconManager._ROOT / "selection" / "mouse-pointer-2.svg",
        IconManager._color_for_category(IconManager.SELECTION),
    )

    assert _has_color_close_to(annotation, (210, 81, 69))
    assert _has_color_close_to(editing, (0, 90, 158))
    assert _has_color_close_to(selection, (51, 51, 51))


def test_icon_manager_uses_bright_editing_color_in_dark_theme(qapp):
    previous = theme_manager.current_theme
    try:
        theme_manager.set_theme("dark")
        editing = IconManager._render(
            IconManager._ROOT / "editing" / "crop.svg",
            IconManager._color_for_category(IconManager.EDITING),
        )
        assert _has_color_close_to(editing, (93, 173, 226))
    finally:
        theme_manager.set_theme(previous)


def test_icon_manager_disabled_icon_is_transparent(qapp):
    color = IconManager._color_for_category(IconManager.ANNOTATION)
    normal = IconManager._render(
        IconManager._ROOT / "annotation" / "square.svg", color
    ).toImage()

    disabled_color = QColor(color)
    disabled_color.setAlpha(round(255 * IconManager.DISABLED_OPACITY))
    disabled = IconManager._render(
        IconManager._ROOT / "annotation" / "square.svg", disabled_color
    ).toImage()

    normal_alpha = max(
        QColor(normal.pixel(x, y)).alpha()
        for y in range(normal.height())
        for x in range(normal.width())
    )
    disabled_alpha = max(
        QColor(disabled.pixel(x, y)).alpha()
        for y in range(disabled.height())
        for x in range(disabled.width())
    )

    assert normal_alpha == 255
    assert disabled_alpha <= round(255 * IconManager.DISABLED_OPACITY)
