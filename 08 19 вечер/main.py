import sys
import os

# Добавляем корень проекта в sys.path, чтобы Python мог найти пакет screenshooter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screenshooter.app import ScreenshotApp
from PyQt5.QtWidgets import QApplication


def main():
    app = QApplication(sys.argv)
    window = ScreenshotApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()