"""
Пакет контроллеров.
Содержит контроллеры для различных подсистем редактора.
"""

from .clipboard_controller import ClipboardController
from .manipulation_controller import ManipulationController

__all__ = ['ClipboardController', 'ManipulationController']