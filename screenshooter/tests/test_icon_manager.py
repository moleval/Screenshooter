import pytest
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import QApplication

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


def test_icon_manager_uses_semantic_colors(qapp):
    annotation = IconManager.icon("rect").pixmap(20, 20, QIcon.Normal, QIcon.Off)
    editing = IconManager.icon("crop").pixmap(20, 20, QIcon.Normal, QIcon.Off)
    selection = IconManager.icon("pointer").pixmap(20, 20, QIcon.Normal, QIcon.Off)

    assert any(c.red() == 210 and c.green() == 81 and c.blue() == 69
               for c in _nontransparent_pixels(annotation))
    assert any(c.red() == 0 and c.green() == 90 and c.blue() == 158
               for c in _nontransparent_pixels(editing))
    assert any(c.red() == 51 and c.green() == 51 and c.blue() == 51
               for c in _nontransparent_pixels(selection))


def test_icon_manager_disabled_icon_is_transparent(qapp):
    color = IconManager._color_for_category(IconManager.ANNOTATION)
    normal = IconManager._render(
        IconManager._ROOT / "annotation" / "square.svg", color
    ).toImage()
    disabled_color = QColor(color)
    disabled_color.setAlphaF(IconManager.DISABLED_OPACITY)
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
    assert 90 <= disabled_alpha <= 110
