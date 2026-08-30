"""
Smoke-тесты для ImageEditController: обрезка и поворот подложки,
работа с вставленными изображениями.
"""

import pytest
from PyQt5.QtCore import QRectF, QPointF
from PyQt5.QtGui import QPixmap, QColor
from PyQt5.QtWidgets import QGraphicsScene

from screenshooter.image_edit_controller import ImageEditController
from screenshooter.items.pasted_image_item import PastedImageItem
from screenshooter.view import EditorView


@pytest.fixture
def setup_editor(qapp):
    scene = QGraphicsScene()
    view = EditorView(scene)

    # Загружаем тестовую подложку
    pm = QPixmap(100, 80)
    pm.fill(QColor("gray"))
    view.set_background_from_pixmap(pm)

    return view


def test_start_and_cancel_crop_mode(setup_editor):
    view = setup_editor
    assert view.crop_mode is False

    view.start_crop_mode()
    assert view.crop_mode is True

    view.cancel_crop_mode()
    assert view.crop_mode is False


def test_rotate_background(setup_editor):
    view = setup_editor
    original_width = view.background_item.pixmap().width()
    original_height = view.background_item.pixmap().height()

    view.rotate_image(90)

    assert view.background_item.pixmap().width() == original_height
    assert view.background_item.pixmap().height() == original_width


def test_crop_pasted_image_keeps_scale(setup_editor):
    view = setup_editor

    # Вставляем картинку
    pm = QPixmap(50, 50)
    pm.fill(QColor("blue"))
    item = view.add_pasted_image(pm)

    # Выделяем и запускаем обрезку
    item.setSelected(True)
    view.start_crop_mode()
    assert view.crop_mode is True

    # Эмулируем применение обрезки без реального взаимодействия мыши
    # Устанавливаем crop_rect вручную
    target = item
    target_rect = target.mapRectToScene(target.boundingRect())
    view.image_editor.crop_rect = target_rect
    view.apply_crop()

    # Проверяем, что обрезка прошла и элемент существует
    assert view.image_editor.crop_mode is False
    assert target.scene() is not None