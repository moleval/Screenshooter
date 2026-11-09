"""Startup audit and consent-based guidance for Windows Explorer integrations."""

import json
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

MODERN_APPLICATION_ROOT = r"D:\Screenshooter"
MODERN_EXECUTABLE = os.path.join(MODERN_APPLICATION_ROOT, "Screenshooter.exe")
MODERN_DLL = os.path.join(MODERN_APPLICATION_ROOT, "ContextMenu", "ScreenshooterContextMenu.dll")
MODERN_PACKAGE = "Moleval.Screenshooter.ContextMenu"
MODERN_PUBLISHER = "CN=Screenshooter Developer"
MODERN_CLSID = "2E50E830-88F2-4A3A-9A6C-6A318C724410"
MODERN_VERB = "ScreenshooterOpenImage"
MODERN_DLL_RELATIVE_PATH = r"ContextMenu\ScreenshooterContextMenu.dll"


def get_modern_menu_status():
    """Read-only audit of package identity, manifest contract and fixed external files."""
    if os.name != "nt":
        return {"status": STATUS_UNAVAILABLE, "issues": ["Современное меню доступно только в Windows 11."]}

    script = r"""
$ErrorActionPreference = 'Stop'
try {
    $os = Get-CimInstance Win32_OperatingSystem
    if ([int]$os.BuildNumber -lt 22000) {
        [pscustomobject]@{ status = 'UNAVAILABLE'; issues = @('Требуется Windows 11, сборка 22000 или новее.') } | ConvertTo-Json -Compress
        exit 0
    }
    $exe = 'D:\Screenshooter\Screenshooter.exe'
    $dll = 'D:\Screenshooter\ContextMenu\ScreenshooterContextMenu.dll'
    $logo150 = 'D:\Screenshooter\ContextMenu\Assets\Square150x150Logo.png'
    $logo44 = 'D:\Screenshooter\ContextMenu\Assets\Square44x44Logo.png'
    $packages = @(Get-AppxPackage -Name 'Moleval.Screenshooter.ContextMenu' -ErrorAction Stop)
    if ($packages.Count -eq 0) {
        [pscustomobject]@{ status = 'NOT_INSTALLED'; issues = @('Пакет MSIX не зарегистрирован для текущего пользователя.') } | ConvertTo-Json -Compress
        exit 0
    }
    $issues = [System.Collections.Generic.List[string]]::new()
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { $issues.Add("Не найден $exe") }
    if (-not (Test-Path -LiteralPath $dll -PathType Leaf)) { $issues.Add("Не найдена $dll") }
    if (-not (Test-Path -LiteralPath $logo150 -PathType Leaf)) { $issues.Add("Не найден ресурс $logo150") }
    if (-not (Test-Path -LiteralPath $logo44 -PathType Leaf)) { $issues.Add("Не найден ресурс $logo44") }

    foreach ($package in $packages) {
        if ($package.Publisher -ne 'CN=Screenshooter Developer') { $issues.Add('Издатель установленного пакета не совпадает с ожидаемым.') }
        if ($package.Architecture -ne 'X64') { $issues.Add('Архитектура пакета не x64.') }
        [xml]$manifest = Get-AppxPackageManifest -Package $package.PackageFullName
        $identity = $manifest.Package.Identity
        if ($identity.Name -ne 'Moleval.Screenshooter.ContextMenu' -or $identity.Publisher -ne 'CN=Screenshooter Developer') {
            $issues.Add('Identity или Publisher манифеста не соответствует ожидаемым значениям.')
        }
        $application = $manifest.Package.Applications.Application
        if ($application.Executable -ne 'Screenshooter.exe') { $issues.Add('Application Executable должен быть Screenshooter.exe в корне ExternalLocation.') }
        $visual = $application.SelectSingleNode("*[local-name()='VisualElements']")
        if (-not $visual -or $visual.Square150x150Logo -ne 'ContextMenu\\Assets\\Square150x150Logo.png' -or $visual.Square44x44Logo -ne 'ContextMenu\\Assets\\Square44x44Logo.png') {
            $issues.Add('Пути к визуальным ресурсам не соответствуют ExternalLocation.')
        }
        $classes = @($manifest.Package.Applications.Application.Extensions.Extension |
            Where-Object { $_.ComServer } | ForEach-Object { $_.ComServer.SurrogateServer.Class })
        $class = $classes | Where-Object { $_.Id -eq '2E50E830-88F2-4A3A-9A6C-6A318C724410' } | Select-Object -First 1
        if (-not $class -or $class.Path -ne 'ContextMenu\ScreenshooterContextMenu.dll') {
            $issues.Add('COM CLSID или путь DLL в манифесте неверен.')
        }
        $verbs = @($manifest.Package.Applications.Application.Extensions.Extension |
            Where-Object { $_.FileExplorerContextMenus } |
            ForEach-Object { $_.FileExplorerContextMenus.ItemType.Verb })
        if (-not ($verbs | Where-Object { $_.Id -eq 'ScreenshooterOpenImage' -and $_.Clsid -eq '2E50E830-88F2-4A3A-9A6C-6A318C724410' })) {
            $issues.Add('Не найдена регистрация ожидаемой команды File Explorer.')
        }
        if ([version]$manifest.Package.Dependencies.TargetDeviceFamily.MinVersion -lt [version]'10.0.22000.0') {
            $issues.Add('Минимальная версия Windows в манифесте ниже 22000.')
        }
    }
    $status = if ($issues.Count -eq 0) { 'INSTALLED' } else { 'BROKEN' }
    [pscustomobject]@{ status = $status; issues = @($issues); package_count = $packages.Count } | ConvertTo-Json -Compress
}
catch {
    [pscustomobject]@{ status = 'UNAVAILABLE'; issues = @($_.Exception.Message) } | ConvertTo-Json -Compress
}
"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"status": STATUS_UNAVAILABLE, "issues": [str(error)]}

    if result.returncode != 0:
        return {
            "status": STATUS_UNAVAILABLE,
            "issues": [result.stderr.strip() or "PowerShell не смог проверить пакет MSIX."],
        }
    try:
        report = json.loads(result.stdout.strip())
    except (json.JSONDecodeError, TypeError):
        return {
            "status": STATUS_UNAVAILABLE,
            "issues": ["Не удалось разобрать результат проверки современного меню."],
        }
    if report.get("status") not in (STATUS_INSTALLED, STATUS_NOT_INSTALLED, "BROKEN", STATUS_UNAVAILABLE):
        return {"status": STATUS_UNAVAILABLE, "issues": ["Проверка вернула неизвестный статус."]}
    report.setdefault("issues", [])
    return report


class IntegrationStartupAudit:
    """Runs once after UI initialization; never repairs without explicit consent."""

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
                "Не удалось проверить классическую интеграцию Windows. Реестр не изменён.\n\n"
                + "\n".join(report["issues"]),
            )
            return
        answer = QMessageBox.question(
            self.parent, "Восстановление контекстного меню",
            "Классическое контекстное меню включено в настройках, но регистрация отсутствует или повреждена.\n\n"
            + "\n".join(report["issues"])
            + "\n\nВосстановить пункт меню для PNG, JPG, JPEG и BMP?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        if not os.path.isfile(EXPECTED_EXECUTABLE):
            QMessageBox.warning(self.parent, "Восстановление контекстного меню",
                                f"Файл не найден: {EXPECTED_EXECUTABLE}\nРеестр не изменён.")
            return
        if not set_context_menu_enabled(True):
            QMessageBox.warning(self.parent, "Восстановление контекстного меню",
                                "Не удалось восстановить регистрацию. Возможна ошибка доступа или конфликт записей.")
            return
        QMessageBox.information(self.parent, "Контекстное меню", "Классическая интеграция восстановлена.")

    def _audit_modern(self):
        report = get_modern_menu_status()
        if report["status"] == STATUS_INSTALLED:
            return
        if report["status"] == STATUS_UNAVAILABLE:
            QMessageBox.warning(
                self.parent, "Проверка современного меню",
                "Не удалось достоверно проверить регистрацию современного меню. Никаких изменений не выполнено.\n\n"
                + "\n".join(report["issues"]),
            )
            return
        if report["status"] == STATUS_NOT_INSTALLED:
            message = "Современное меню включено в настройках, но MSIX не зарегистрирован для текущего пользователя."
        else:
            message = "Современный пакет обнаружен, но его манифест или файлы не соответствуют ожидаемой установке."
        QMessageBox.information(
            self.parent, "Современное контекстное меню",
            message + "\n\nДля восстановления запустите windows_context_menu\\Install-ModernMenu.ps1 "
            "с подписанным MSIX и DLL из комплекта сборки. Установка потребует отдельного подтверждения. "
            "Screenshooter.exe не копируется и не заменяется.",
        )
