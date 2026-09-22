"""Команды изменения слоя объектов."""

from PyQt5.QtWidgets import QUndoCommand


class ChangeLayerCommand(QUndoCommand):
    def __init__(self, items, old_layers, new_layer):
        super().__init__("Изменить слой")
        self.items = list(items)
        self.old_layers = list(old_layers)
        self.new_layer = int(new_layer)

    def _apply(self, layers):
        for item, layer in zip(self.items, layers):
            if item is not None:
                item.set_layer(layer)

    def redo(self):
        self._apply([self.new_layer] * len(self.items))

    def undo(self):
        self._apply(self.old_layers)
