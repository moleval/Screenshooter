# Современное контекстное меню Windows 11

Компонент добавляет Screenshooter в современное контекстное меню Проводника Windows 11 через packaged COM extension (`IExplorerCommand`) и sparse MSIX.

## Фиксированная архитектура

Единственный EXE приложения: `D:\Screenshooter\Screenshooter.exe`. Он не входит в MSIX и не копируется сборщиком.

Структура внешнего каталога после установки:

```text
D:\Screenshooter\
  Screenshooter.exe
  ContextMenu\
    ScreenshooterContextMenu.dll
    Assets\
      Square150x150Logo.png
      Square44x44Logo.png
```

- `D:\Screenshooter` используется как ExternalLocation sparse MSIX.
- Манифест указывает `Screenshooter.exe` в корне ExternalLocation.
- COM-сервер расположен по относительному пути `ContextMenu\ScreenshooterContextMenu.dll`.
- Визуальные ресурсы `VisualElements` также должны быть во внешнем каталоге: `ContextMenu\Assets`. `StoreLogo.png` остаётся ресурсом самого MSIX.
- DLL запускает строго `D:\Screenshooter\Screenshooter.exe`.
- Сборка не копирует и не заменяет EXE приложения.
- Установщик развёртывает только DLL и управляемые PNG-файлы после явного подтверждения.
- Удаление пакета не удаляет приложение, DLL, PNG или классическую регистрацию Windows.

Современное меню поддерживается на Windows 11 build 22000+ x64. Классическая интеграция остаётся независимой.

## Сборка из репозитория

Требуются Visual Studio Build Tools с C++ workload, CMake, Windows 10/11 SDK и Python с Pillow. Перед сборкой должен существовать `D:\Screenshooter\Screenshooter.exe`.

Создайте сертификат с Subject ровно `CN=Screenshooter Developer` в `Cert:\CurrentUser\My`, затем из корня репозитория выполните:

```powershell
$cert = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object Subject -eq 'CN=Screenshooter Developer' |
    Select-Object -First 1
if (-not $cert) { throw 'Сертификат подписи не найден.' }

.\windows_context_menu\Build-SparsePackage.ps1 -CertificateThumbprint $cert.Thumbprint
```

Скрипт создаёт MSIX и внешний payload в `dist\ScreenshooterModernMenu`. Он не меняет `D:\Screenshooter` и не регистрирует пакет.

## Установка

Убедитесь, что Windows доверяет сертификату. Сначала выполните проверку без изменений:

```powershell
.\windows_context_menu\Install-ModernMenu.ps1 -MsixPath .\dist\ScreenshooterModernMenu\ScreenshooterModernMenu.msix -PayloadDirectory .\dist\ScreenshooterModernMenu\Payload\ContextMenu -WhatIf
```

После проверки выполните ту же команду без `-WhatIf`. Установщик:
- проверяет Windows 11 build 22000+, наличие EXE, подпись, Publisher, Identity и пути манифеста;
- проверяет наличие DLL и двух внешних PNG-ресурсов;
- сохраняет резервные копии заменяемых файлов;
- копирует DLL и PNG-ресурсы в `D:\Screenshooter\ContextMenu`;
- регистрирует MSIX с ExternalLocation `D:\Screenshooter`;
- при ошибке развёртывания или регистрации восстанавливает прежние файлы.

`Screenshooter.exe` не копируется и не заменяется.

## Удаление

```powershell
.\windows_context_menu\Uninstall-ModernMenu.ps1 -WhatIf
.\windows_context_menu\Uninstall-ModernMenu.ps1
```

Удаляется только MSIX-регистрация текущего пользователя. DLL и PNG остаются в каталоге приложения; они не удаляются автоматически.

## Диагностика

Read-only аудит проверяет Windows build, регистрацию пакета, Publisher, архитектуру, Identity, COM CLSID, путь DLL, File Explorer Verb, пути `VisualElements` и наличие EXE/DLL/PNG по фиксированным путям.

Аудит не активирует COM-сервер и не проверяет фактическое отображение пункта в интерактивном Проводнике. Поэтому функциональная проверка на целевой Windows 11 машине обязательна. Установка и восстановление автоматически не выполняются.

## CI

GitHub Actions собирает DLL, формирует и подписывает тестовый MSIX, проверяет структуру пакета, запускает установочный preflight через `-WhatIf`, затем выполняет реальную регистрацию и удаление пакета на временной Windows-машине. Проверка не запускает интерактивный Проводник и не подтверждает визуальное отображение пункта или COM-активацию в реальном пользовательском сеансе.
