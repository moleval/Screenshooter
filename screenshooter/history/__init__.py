"""
Модуль: history/__init__.py
Описание: Менеджер истории Undo/Redo на базе QUndoStack.
          Экспортирует все команды из подмодулей для обратной совместимости.
"""

from PyQt5 import sip
from PyQt5.QtWidgets import QUndoStack

from .item_commands import (AddItemCommand, RemoveItemCommand,
                            MoveItemCommand, MoveItemsCommand,
                            ResizeItemCommand, ChangePenCommand,
                            ChangeTextCommand)
from .background_commands import CropCommand, RotateCommand, BlurCommand
from .blur_commands import (AddBlurRegionCommand, RemoveBlurRegionCommand,
                            MoveBlurRegionCommand, ResizeBlurRegionCommand)
from .image_commands import (AddPastedImageCommand, RemovePastedImageCommand,
                             ResizePastedImageCommand, CropPastedImageCommand,
                             RotatePastedImageCommand)
from .composite_commands import RemoveSelectedItemsCommand, PasteItemsCommand

__all__ = [
    'HistoryManager',
    # Команды элементов
    'AddItemCommand', 'RemoveItemCommand',
    'MoveItemCommand', 'MoveItemsCommand',
    'ResizeItemCommand', 'ChangePenCommand', 'ChangeTextCommand',
    # Команды фона
    'CropCommand', 'RotateCommand', 'BlurCommand',
    # Команды зон размытия
    'AddBlurRegionCommand', 'RemoveBlurRegionCommand',
    'MoveBlurRegionCommand', 'ResizeBlurRegionCommand',
    # Команды вставленных изображений
    'AddPastedImageCommand', 'RemovePastedImageCommand',
    'ResizePastedImageCommand', 'CropPastedImageCommand',
    'RotatePastedImageCommand',
    # Составные команды
    'RemoveSelectedItemsCommand', 'PasteItemsCommand',
]


class HistoryManager:
    """Обёртка над QUndoStack для работы с графической сценой."""

    def __init__(self):
        self.stack = QUndoStack()

    def push(self, command):
        self.stack.push(command)

    def undo(self):
        self.stack.undo()

    def redo(self):
        self.stack.redo()

    def clear(self):
        self.stack.clear()

    def can_undo(self):
        if sip.isdeleted(self.stack):
            return False
        return self.stack.canUndo()

    def can_redo(self):
        if sip.isdeleted(self.stack):
            return False
        return self.stack.canRedo()