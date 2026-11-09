# Современное контекстное меню Windows 11

Компонент добавляет Screenshooter в современное контекстное меню Проводника Windows 11 через packaged COM extension (`IExplorerCommand`) и sparse MSIX.

## Фиксированная архитектура

Единственный исполняемый файл приложения остаётся в `D:\Screenshooter\Screenshooter.exe`.

Структура после установки:

```text
D:\Screenshooter\
  Screenshooter.exe
  ContextMenu\
    ScreenshooterContextMenu.dll
```

- `D:\Screenshooter` используется как ExternalLocation sparse MSIX.
- Манифест указывает `Screenshooter.exe` в корне ExternalLocation.
- COM-сервер находится по относительному пути `ContextMenu\ScreenshooterContextMenu.dll`.
- DLL запускает строго `D:\Screenshooter\Screenshooter.exe`.
- Сборка не копирует и не заменяет EXE приложения.
- Установщик развёртывает только DLL после явного подтверждения и регистрирует MSIX для текущего пользователя.
- Удаление пакета не удаляет Screenshooter.exe, DLL или классическую регистрацию Windows.

Современное меню поддерживается на Windows 11 build 22000+ x64. Классическая интеграция остаётся независимой.

## Сборка из репозитория

Требуются Visual Studio Build Tools с C++ workload, CMake, Windows 10/11 SDK и Python с Pillow. Перед сборкой должен существовать установленный `D:\Screenshooter\Screenshooter.exe`.

Создайте сертификат с Subject ровно `CN=Screenshooter Developer` в `Cert:\CurrentUser\My`, затем из корня репозитория выполните:

```powershell
$cert = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object Subject -eq 'CN=Screenshooter Developer' |
    Select-Object -First 1
if (-not $cert) { throw 'Сертификат подписи не найден.' }

.\windows_context_menu\Build-SparsePackage.ps1 -CertificateThumbprint $cert.Thumbprint
```

Скрипт создаёт MSIX и DLL payload в `dist\ScreenshooterModernMenu`. Он не меняет `D:\Screenshooter` и не регистрирует пакет.

## Установка

Убедитесь, что Windows доверяет сертификату. Сначала выполните проверку без изменений:

```powershell
.\windows_context_menu\Install-ModernMenu.ps1 -MsixPath .\dist\ScreenshooterModernMenu\ScreenshooterModernMenu.msix -DllPath .\dist\ScreenshooterModernMenu\Payload\ContextMenu\ScreenshooterContextMenu.dll -WhatIf
```

После проверки выполните ту же команду без `-WhatIf`. Установщик проверяет Windows, EXE, подпись, издателя, Identity и пути манифеста; сохраняет резервную копию DLL; развёртывает DLL; регистрирует MSIX с ExternalLocation `D:\Screenshooter`. При ошибке регистрации прежняя DLL восстанавливается.

`Screenshooter.exe` не копируется и не заменяется.

## Удаление

```powershell
.\windows_context_menu\Uninstall-ModernMenu.ps1 -WhatIf
.\windows_context_menu\Uninstall-ModernMenu.ps1
```

Удаляется только MSIX-регистрация текущего пользователя. DLL остаётся в каталоге приложения и может быть удалена отдельно после удаления пакета.

## Диагностика

Read-only аудит проверяет Windows build, регистрацию пакета, Publisher, архитектуру, Identity, COM CLSID, относительный путь DLL, File Explorer Verb и наличие EXE/DLL по фиксированным путям.

Аудит не активирует COM-сервер и не проверяет визуальное отображение пункта в Проводнике. Функциональная проверка на целевой Windows 11 машине обязательна. Установка и восстановление автоматически не выполняются.

## CI

GitHub Actions собирает DLL, формирует и подписывает тестовый MSIX, проверяет структуру пакета и выполняет установочный preflight через `-WhatIf`. Это не заменяет реальную регистрацию и проверку COM-активации в интерактивном Проводнике.
