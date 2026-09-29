"""
Модуль: controllers/snap_guides_controller.py
Описание: мягкая привязка перемещаемых объектов к осям подложки
и других объектов с временными направляющими.
"""

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPen
from PyQt5.QtWidgets import QGraphicsLineItem, QGraphicsSimpleTextItem, QGraphicsItem, QGraphicsEllipseItem
from PyQt5.QtGui import QFont


class SnapGuidesController:
    """Вычисляет snap-delta и управляет временными направляющими."""

    SNAP_DISTANCE_PX = 8.0
    GUIDE_Z_VALUE = 9998
    GUIDE_COLOR = QColor(0, 170, 255, 255)
    MULTI_SNAP_COLOR = QColor(255, 215, 0, 255)
    GUIDE_WIDTH = 2
    CROSS_SIZE_PX = 7
    CROSS_WIDTH = 2

    def __init__(self, view):
        self.view = view
        self._scene = view.scene()
        self._drag_rects = []
        self._candidate_x = []
        self._candidate_y = []
        self._guides = []
        self._guide_labels = []

    def begin_drag(self, items, background_item):
        """Фиксирует исходную геометрию drag-группы и оси привязки."""
        self.clear_guides()
        selected = set(items)
        self._drag_rects = [
            item.sceneBoundingRect()
            for item in items
            if item is not None and item.scene() is self._scene
        ]

        self._candidate_x = []
        self._candidate_y = []

        if background_item is not None and background_item.scene() is self._scene:
            self._add_rect_candidates(background_item.sceneBoundingRect())

        for item in self._scene.items():
            if item in selected or item is background_item:
                continue
            if item.scene() is not self._scene:
                continue
            # Направляющие и служебные scene-items не являются целями.
            if item.zValue() >= 2000:
                continue
            self._add_rect_candidates(item.sceneBoundingRect())

    def _add_rect_candidates(self, rect):
        rect = QRectF(rect)
        if rect.isEmpty():
            return
        self._candidate_x.extend((rect.left(), rect.center().x(), rect.right()))
        self._candidate_y.extend((rect.top(), rect.center().y(), rect.bottom()))

    @staticmethod
    def _union_rects(rects):
        if not rects:
            return QRectF()
        result = QRectF(rects[0])
        for rect in rects[1:]:
            result = result.united(rect)
        return result

    def snap_delta(self, delta, snap_x=True, snap_y=True):
        """Возвращает скорректированный delta и показывает активные guides."""
        if not self._drag_rects:
            return QPointF(delta)

        zoom = abs(self.view.transform().m11())
        if zoom < 1e-6:
            zoom = 1.0
        threshold = self.SNAP_DISTANCE_PX / zoom

        group_rect = self._union_rects(
            [QRectF(rect).translated(delta.x(), delta.y()) for rect in self._drag_rects]
        )

        dx = 0.0
        dy = 0.0
        x_guide = None
        y_guide = None

        x_guides = []
        y_guides = []

        background = getattr(self.view.image_editor, "background_item", None)
        background_rect = (
            background.sceneBoundingRect()
            if background is not None and background.scene() is self._scene
            else QRectF()
        )
        full_width = (
            not background_rect.isEmpty()
            and abs(group_rect.width() - background_rect.width()) <= 1e-6
        )
        full_height = (
            not background_rect.isEmpty()
            and abs(group_rect.height() - background_rect.height()) <= 1e-6
        )

        x_values = (
            (group_rect.left(), group_rect.right())
            if full_width
            else (group_rect.left(), group_rect.center().x(), group_rect.right())
        )
        y_values = (
            (group_rect.top(), group_rect.bottom())
            if full_height
            else (group_rect.top(), group_rect.center().y(), group_rect.bottom())
        )

        if snap_x:
            if full_width:
                x_guides = [
                    (
                        background_rect.left(),
                        group_rect.left(),
                        abs(background_rect.left() - group_rect.left()),
                    ),
                    (
                        background_rect.right(),
                        group_rect.right(),
                        abs(background_rect.right() - group_rect.right()),
                    ),
                ]
                x_guides = [
                    guide for guide in x_guides
                    if guide[2] <= threshold
                ]
            else:
                x_guides = self._find_all_best(
                    x_values,
                    self._candidate_x,
                    threshold,
                )
            if x_guides:
                x_guide = min(x_guides, key=lambda guide: guide[2])
                dx = x_guide[0] - x_guide[1]

        if snap_y:
            if full_height:
                y_guides = [
                    (
                        background_rect.top(),
                        group_rect.top(),
                        abs(background_rect.top() - group_rect.top()),
                    ),
                    (
                        background_rect.bottom(),
                        group_rect.bottom(),
                        abs(background_rect.bottom() - group_rect.bottom()),
                    ),
                ]
                y_guides = [
                    guide for guide in y_guides
                    if guide[2] <= threshold
                ]
            else:
                y_guides = self._find_all_best(
                    y_values,
                    self._candidate_y,
                    threshold,
                )
            if y_guides:
                y_guide = min(y_guides, key=lambda guide: guide[2])
                dy = y_guide[0] - y_guide[1]

        result = QPointF(delta.x() + dx, delta.y() + dy)
        self._show_guides(
            x_guides=x_guides,
            y_guides=y_guides,
            group_rect=group_rect,
            multi_snap=(bool(x_guides) and bool(y_guides)),
        )
        return result

    @staticmethod
    def _find_all_best(values, candidates, threshold):
        best_distance = None
        best = []
        for value in values:
            for candidate in candidates:
                distance = abs(candidate - value)
                if distance > threshold:
                    continue
                if best_distance is None or distance < best_distance - 1e-6:
                    best_distance = distance
                    best = [(candidate, value, distance)]
                elif abs(distance - best_distance) <= 1e-6:
                    best.append((candidate, value, distance))

        unique = []
        seen = set()
        for guide in best:
            key = (round(guide[0], 6), round(guide[1], 6))
            if key not in seen:
                seen.add(key)
                unique.append(guide)
        return unique

    @staticmethod
    def _find_best(values, candidates, threshold):
        guides = SnapGuidesController._find_all_best(values, candidates, threshold)
        return guides[0] if guides else None

    def _show_guides(self, x_guides=None, y_guides=None, group_rect=None,
                     multi_snap=False):
        self.clear_guides()
        x_guides = x_guides or []
        y_guides = y_guides or []
        bg = getattr(self.view.image_editor, "background_item", None)
        if bg is not None and bg.scene() is self._scene:
            rect = bg.sceneBoundingRect()
        else:
            rect = self._union_rects(self._drag_rects)

        if rect.isEmpty():
            return

        color = self.MULTI_SNAP_COLOR if multi_snap else self.GUIDE_COLOR
        pen = QPen(color, self.GUIDE_WIDTH, Qt.DashLine)
        pen.setCosmetic(True)

        for x_guide in x_guides:
            x_target, x_value, _ = x_guide
            line = QGraphicsLineItem(x_target, rect.top(), x_target, rect.bottom())
            line.setPen(pen)
            line.setZValue(self.GUIDE_Z_VALUE)
            line.setFlag(QGraphicsLineItem.ItemIsSelectable, False)
            self._scene.addItem(line)
            self._guides.append(line)

            center_y = group_rect.center().y()
            self._add_cross(x_value, center_y, color)
            self._add_cross(x_target, center_y, color)
            self._add_guide_label(
                x_target,
                rect.top(),
                self._axis_label("x", x_target, rect),
                color,
            )

        for y_guide in y_guides:
            y_target, y_value, _ = y_guide
            line = QGraphicsLineItem(rect.left(), y_target, rect.right(), y_target)
            line.setPen(pen)
            line.setZValue(self.GUIDE_Z_VALUE)
            line.setFlag(QGraphicsLineItem.ItemIsSelectable, False)
            self._scene.addItem(line)
            self._guides.append(line)

            center_x = group_rect.center().x()
            self._add_cross(center_x, y_value, color)
            self._add_cross(center_x, y_target, color)
            self._add_guide_label(
                rect.left(),
                y_target,
                self._axis_label("y", y_target, rect),
                color,
            )

    def _axis_label(self, axis, position, background_rect):
        """Возвращает понятную подпись направляющей относительно подложки."""
        if axis == "x":
            if abs(position - background_rect.left()) <= 1e-6:
                return "X: левый край"
            if abs(position - background_rect.center().x()) <= 1e-6:
                return "X: центр"
            if abs(position - background_rect.right()) <= 1e-6:
                return "X: правый край"
            return "X: цель"
        if abs(position - background_rect.top()) <= 1e-6:
            return "Y: верхний край"
        if abs(position - background_rect.center().y()) <= 1e-6:
            return "Y: центр"
        if abs(position - background_rect.bottom()) <= 1e-6:
            return "Y: нижний край"
        return "Y: цель"

    def _add_guide_label(self, x, y, text, color):
        """Добавляет подпись к активной направляющей."""
        label = QGraphicsSimpleTextItem(text)
        label.setBrush(QColor(255, 235, 80, 255))
        label.setZValue(self.GUIDE_Z_VALUE + 2)
        label.setAcceptedMouseButtons(Qt.NoButton)
        label.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        label.setFont(font)
        label_rect = label.boundingRect()
        label_x = (
            x - label_rect.width() - 8
            if "правый край" in text
            else x + 6
        )
        label_y = (
            y - label_rect.height() - 8
            if "нижний край" in text
            else y + 6
        )
        label.setPos(label_x, label_y)
        self._scene.addItem(label)
        self._guide_labels.append(label)

    def _add_cross(self, x, y, color):
        zoom = abs(self.view.transform().m11())
        if zoom < 1e-6:
            zoom = 1.0
        size = self.CROSS_SIZE_PX / zoom
        pen = QPen(color, self.CROSS_WIDTH)
        pen.setCosmetic(True)

        marker = QGraphicsEllipseItem(
            x - size,
            y - size,
            size * 2,
            size * 2,
        )
        marker.setBrush(Qt.NoBrush)
        marker.setPen(pen)
        marker.setZValue(self.GUIDE_Z_VALUE + 1)
        marker.setFlag(QGraphicsEllipseItem.ItemIsSelectable, False)
        self._scene.addItem(marker)
        self._guides.append(marker)

    def clear_guides(self):
        for guide in self._guides:
            if guide.scene() is self._scene:
                self._scene.removeItem(guide)
        for label in self._guide_labels:
            if label.scene() is self._scene:
                self._scene.removeItem(label)
        self._guides.clear()
        self._guide_labels.clear()

    @property
    def guides(self):
        return tuple(self._guides)
