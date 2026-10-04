# tests/test_smoke.py
import pytest
from PyQt5.QtGui import QPixmap, QColor

from screenshooter.app import ScreenshotApp


@pytest.mark.parametrize("tool_name", [None, 'line', 'rect', 'ellipse', 'arrow', 'text'])
def test_app_starts_and_tools_switch(qapp, tool_name):
    app = ScreenshotApp()

    pm = QPixmap(200, 150)
    pm.fill(QColor("gray"))
    app.view.set_background_from_pixmap(pm)

    app.set_tool(tool_name)

    assert app.view.scene().items() is not None
    assert app.print_btn.isEnabled()

    app.close()


def test_undo_redo_after_add_item(qapp):
    app = ScreenshotApp()

    pm = QPixmap(200, 150)
    pm.fill(QColor("gray"))
    app.view.set_background_from_pixmap(pm)

    app.set_tool('rect')
    # В реальности здесь было бы рисование, но мы просто проверяем вызовы
    app.undo_action()
    app.redo_action()

    app.close()

def test_captured_screenshot_is_preprocessed_and_not_enhanced_twice(qapp, monkeypatch):
    import screenshooter.app as app_module
    import screenshooter.export as export_module
    from PyQt5.QtGui import QImage

    app = ScreenshotApp()
    app.settings.enhancer_enabled = True
    app.settings.enhancer_scale = 1.0
    app.settings.enhancer_text = False
    app.settings.enhancer_lines = False
    app.settings.enhancer_ui = False
    app.settings.enhancer_geometry = False
    app.settings.enhancer_color_mode = "monochrome"

    calls = {"count": 0}

    def fake_enhance(image, options):
        calls["count"] += 1
        result = image.convertToFormat(QImage.Format_ARGB32)
        result.invertPixels()
        return result

    monkeypatch.setattr(app_module, "enhance_image", fake_enhance)
    monkeypatch.setattr(export_module, "enhance_image", fake_enhance)

    pm = QPixmap(20, 10)
    pm.fill(QColor("black"))
    app.screenshot_pixmap = pm
    app.display_screenshot(source_is_autocad=True)

    shown = app.view.background_item.pixmap().toImage()
    assert QColor(shown.pixel(0, 0)) == QColor("white")
    assert calls["count"] == 1

    rendered = app.exporter.render_scene_to_image()
    assert not rendered.isNull()
    assert calls["count"] == 1

    app.close()


def test_monochrome_capture_is_limited_to_autocad(qapp, monkeypatch):
    import screenshooter.app as app_module
    import screenshooter.export as export_module
    from PyQt5.QtGui import QImage

    app = ScreenshotApp()
    app.settings.enhancer_enabled = False
    app.settings.enhancer_color_mode = "monochrome"

    calls = {"count": 0}

    def fake_enhance(image, options):
        calls["count"] += 1
        result = image.copy()
        result.invertPixels()
        return result

    monkeypatch.setattr(app_module, "enhance_image", fake_enhance)
    monkeypatch.setattr(export_module, "enhance_image", fake_enhance)

    pm = QPixmap(20, 10)
    pm.fill(QColor("black"))

    app.screenshot_pixmap = pm
    app.display_screenshot(source_is_autocad=False)
    ordinary = app.view.background_item.pixmap().toImage()
    assert QColor(ordinary.pixel(0, 0)) == QColor("black")
    assert calls["count"] == 0
    assert not app.exporter.render_scene_to_image().isNull()
    assert calls["count"] == 0

    app.screenshot_pixmap = pm
    app.display_screenshot(source_is_autocad=True)
    autocad = app.view.background_item.pixmap().toImage()
    assert QColor(autocad.pixel(0, 0)) == QColor("white")
    assert calls["count"] == 1
    assert not app.exporter.render_scene_to_image().isNull()
    assert calls["count"] == 1

    app.close()
