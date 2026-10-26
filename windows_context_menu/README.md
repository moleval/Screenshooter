# Современное контекстное меню Windows 11

Этот компонент — отдельная native COM shell extension. Текущая регистрация через
`HKCU\Software\Classes\SystemFileAssociations` остаётся резервной для Windows 10 и классического меню Windows 11.

## Архитектура

- `ContextMenuCommand.cpp` реализует `IExplorerCommand` и показывает команду только для PNG, JPG, JPEG и BMP.
- Команда запускает `Screenshooter.exe` из той же папки и передаёт полный путь к выделенному изображению.
- `CMakeLists.txt` собирает native DLL компилятором MSVC.
- Современное меню Windows 11 требует регистрации COM-класса через пакет с app identity (обычно sparse MSIX). Одна DLL или запись реестра сама по себе не активирует пункт в современном меню.

## Сборка DLL

Из Developer PowerShell for Visual Studio с установленным CMake:

```powershell
cmake -S windows_context_menu -B build/windows-context-menu -A x64
cmake --build build/windows-context-menu --config Release
```

DLL рассчитана на размещение рядом с `Screenshooter.exe` и `icon.ico`.

## Регистрация и тестирование

Для показа пункта в первом уровне меню необходимо упаковать DLL и приложение в sparse MSIX,
добавить в манифест `windows.comServer` и
`windows.fileExplorerContextMenus`, подписать пакет доверенным сертификатом
и установить его. После обновления пакета может потребоваться перезапустить Проводник.

Пока пакет не собран, подписан и установлен, современный пункт меню не считается включённым.
Не удаляйте существующую регистрацию классического пункта: она обеспечивает совместимость
с Windows 10. Также не следует включать одновременно оба пункта на Windows 11, иначе появятся дубликаты.
