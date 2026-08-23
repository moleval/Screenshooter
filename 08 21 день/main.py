import sys
import os

from PyQt5.QtCore import Qt, QCoreApplication

# Включаем High DPI scaling ДО создания QApplication
QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from screenshooter.app import ScreenshotApp


def main():
    app = QApplication(sys.argv)
    window = ScreenshotApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()