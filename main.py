"""
Модуль: main.py
Описание: Точка входа приложения Screenshooter.
Обрабатывает запуск в фоне, открытие изображений из Проводника
и передачу файлов уже запущенному экземпляру.
"""

import sys
import os
import ctypes
import tempfile
import platform

from PyQt5.QtCore import QLockFile, QLocalServer, QLocalSocket
from PyQt5.QtWidgets import QApplication, QMessageBox

if platform.system() == "Windows":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Screenshooter.App.1.0")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screenshooter.dpi import configure_windows_dpi_awareness
from screenshooter.window_manager import WindowManager
from screenshooter.hotkey_manager import HotkeyManager
from screenshooter.tray import TrayManager
from screenshooter.utils import load_app_icon


LOCAL_SERVER_NAME = "Screenshooter.App.1.0"


def get_lock_file_path():
    """Возвращает путь к файлу блокировки приложения."""
    return os.path.join(tempfile.gettempdir(), "Screenshooter.lock")


def try_acquire_lock():
    """Пытается получить блокировку единственного экземпляра приложения."""
    lock_file = QLockFile(get_lock_file_path())
    lock_file.setStaleLockTime(60000)
    if lock_file.tryLock():
        return lock_file, True
    return None, False


def _image_argument():
    """Возвращает путь изображения из аргументов командной строки, если он есть."""
    return next(
        (arg for arg in sys.argv[1:] if not arg.startswith("--")),
        None,
    )


def _send_to_running_instance(image_path):
    """Передаёт путь уже работающему экземпляру через локальный сокет."""
    socket = QLocalSocket()
    socket.connectToServer(LOCAL_SERVER_NAME)
    if not socket.waitForConnected(1500):
        return False
    payload = (image_path or "").encode("utf-8") + b"\n"
    socket.write(payload)
    socket.flush()
    delivered = socket.waitForBytesWritten(1500)
    socket.disconnectFromServer()
    return delivered


def main():
    configure_windows_dpi_awareness()
    image_path = _image_argument()

    lock_file, success = try_acquire_lock()
    if not success:
        # Контекстное меню должно передавать файл уже запущенному приложению,
        # а не показывать пользователю ошибку о второй копии.
        app = QApplication(sys.argv)
        app.setApplicationName("Screenshooter")
        if _send_to_running_instance(image_path):
            return
        QMessageBox.critical(
            None,
            "Ошибка запуска",
            "Другой экземпляр Screenshooter уже запущен, но связь с ним "
            "установить не удалось. Попробуйте повторить действие.",
        )
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("Screenshooter")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(load_app_icon())

    window_manager = WindowManager(app)
    tray_manager = TrayManager(window_manager)
    window_manager.tray_manager = tray_manager

    hotkey_manager = HotkeyManager(window_manager, app)
    window_manager.hotkey_manager = hotkey_manager
    app.aboutToQuit.connect(hotkey_manager.cleanup)

    def open_image(path):
        path = path.strip()
        if not path:
            return
        window = window_manager.create_editor_window(show=True)
        if not window.open_image_path(path):
            window.close()

    # Сокет позволяет Проводнику передать изображение уже работающему приложению.
    local_server = QLocalServer(app)
    QLocalServer.removeServer(LOCAL_SERVER_NAME)
    if not local_server.listen(LOCAL_SERVER_NAME):
        QMessageBox.warning(
            None,
            "Screenshooter",
            "Не удалось создать канал связи для открытия файлов.",
        )

    def receive_connections():
        while local_server.hasPendingConnections():
            socket = local_server.nextPendingConnection()
            socket.setParent(local_server)
            socket.readyRead.connect(
                lambda current_socket=socket: receive_payload(current_socket)
            )

    def receive_payload(socket):
        data = bytes(socket.readAll())
        for line in data.splitlines():
            try:
                path = line.decode("utf-8").strip()
            except UnicodeDecodeError:
                continue
            if path:
                open_image(path)
        socket.disconnectFromServer()

    local_server.newConnection.connect(receive_connections)

    if image_path:
        open_image(image_path)

    # Удерживаем блокировку и сервер до завершения приложения.
    app._lock_file = lock_file
    app._local_server = local_server
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
