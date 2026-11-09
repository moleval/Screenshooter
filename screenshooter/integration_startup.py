"""Startup audit and consent-based repair for Windows Explorer integrations."""

import os
import subprocess

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox

from .context_menu import (
    EXPECTED_EXECUTABLE,
    STATUS_INSTALLED,
    STATUS_NOT_INSTALLED,
    STATUS_UNAVAILABLE,
    get_classic_menu_status,
    set_context_menu_enabled,
)

MODERN_PACKAGE = "Moleval.Screenshooter.ContextMenu"


def get_modern_menu_status():
    """Read-only package audit. Never installs, removes, or changes registration."""
    if os.name != "nt":
        return {"status": STATUS_UNAVAILABLE, "issues": ["Современное меню доступно только в Windows 11."]}
    try:
        result = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                "$build = [int](Get-CimInstance Win32_OperatingSystem).BuildNumber; "
                "if ($build -lt 22000) { 'UNAVAILABLE' } else { "
                "$p = @(Get-AppxPackage -Name 'Moleval.Screenshooter.ContextMenu' "
                "-ErrorAction SilentlyContinue); "
                "if ($p.Count -eq 0) { 'NOT_INSTALLED' } else { "
                "$exe = Test-Path -LiteralPath 'D:\\Screenshooter\\Screenshooter.exe' -PathType Leaf; "
                "$m = Get-AppxPackageManifest -Package $p[0]; "
                "$xml = $m.OuterXml; "
                "if (-not $exe -or $xml -notmatch '2E50E830-88F2-4A3A-9A6C-6A318C724410' "
                "-or $xml -notmatch 'ScreenshooterOpenImage') { 'BROKEN' } else { 'INSTALLED' } } }",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"status": STATUS_UNAVAILABLE, "issues": [str(error)]}

    if result.returncode != 0:
        return {
            "status": STATUS_UNAVAILABLE,
            "issues": [result.stderr.strip() or "Не удалось проверить пакет MSIX."],
        }
    status = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else STATUS_UNAVAILABLE
    if status not in (STATUS_INSTALLED, STATUS_NOT_INSTALLED, "BROKEN"):
        status = STATUS_UNAVAILABLE
    return {
        "status": status,
        "issues": [] if status == STATUS_INSTALLED else ["Пакет современного меню не зарегистрирован."],
    }


class IntegrationStartupAudit:
    """Runs once after the main UI is initialized and asks before any repair."""

    def __init__(self, settings, parent=None):
        self.settings = settings
        self.parent = parent

    def schedule(self):
        QTimer.singleShot(0, self.run)

    def run(self):
        if getattr(self.settings, "classic_menu_enabled", False):
            self._audit_classic()
        if getattr(self.settings, "modern_menu_enabled", False):
            self._audit_modern()

    def _audit_classic(self):
        report = get_classic_menu_status()
        if report["status"] == STATUS_INSTALLED:
            return
        if report["status"] == STATUS_UNAVAILABLE:
            QMessageBox.warning(
                self.parent, "Проверка контекстного меню",
                "Не удалось проверить классическую интеграцию Windows. "
                "Реестр не изменён.\n\n" + "\n".join(report["issues"]),
            )
            return

        details = "\n".join(report["issues"])
        answer = QMessageBox.question(
            self.parent,
            "Восстановление контекстного меню",
            "Классическое контекстное меню Screenshooter включено в настройках, "
            "но его регистрация отсутствует или повреждена.\n\n"
            + details
            + "\n\nВосстановить пункт меню для PNG, JPG, JPEG и BMP?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        if not os.path.isfile(EXPECTED_EXECUTABLE):
            QMessageBox.warning(
                self.parent, "Восстановление контекстного меню",
                f"Файл не найден: {EXPECTED_EXECUTABLE}\nРеестр не изменён.",
            )
            return
        if not set_context_menu_enabled(True):
            QMessageBox.warning(
                self.parent, "Восстановление контекстного меню",
                "Не удалось восстановить регистрацию. Возможна ошибка доступа "
                "или конфликт существующих записей. Реестр не будет "
                "перезаписываться повторно автоматически.",
            )
            return
        QMessageBox.information(
            self.parent, "Контекстное меню",
            "Классическая интеграция восстановлена.",
        )

    def _audit_modern(self):
        report = get_modern_menu_status()
        if report["status"] == STATUS_INSTALLED:
            return
        if report["status"] == STATUS_UNAVAILABLE:
            QMessageBox.warning(
                self.parent, "Проверка современного меню",
                "Не удалось проверить регистрацию современного меню Windows 11. "
                "Никаких изменений не выполнено.\n\n" + "\n".join(report["issues"]),
            )
            return

        if report["status"] == STATUS_NOT_INSTALLED:
            message = (
                "Современное меню включено в настройках, но пакет MSIX не найден. "
            )
        else:
            message = (
                "Пакет современного меню найден, но проверка обнаружила неполную "
                "регистрацию или отсутствие Screenshooter.exe по ожидаемому пути. "
            )
        QMessageBox.information(
            self.parent,
            "Современное контекстное меню",
            message
            + "Автоматическое восстановление пока недоступно: для него необходимы "
            "подписанный пакет и DLL в подготовленном ExternalLocation. "
            "Никакие системные настройки не изменены.",
        )
