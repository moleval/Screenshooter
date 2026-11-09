[CmdletBinding()]
param(
    [string]$BuildDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) 'build\windows-context-menu'),
    [string]$OutputDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) 'dist\ScreenshooterModernMenu'),
    [string]$ApplicationRoot = 'D:\Screenshooter',
    [string]$CertificateThumbprint
)

$ErrorActionPreference = 'Stop'
$ApplicationRoot = [System.IO.Path]::GetFullPath($ApplicationRoot)
$applicationExe = Join-Path $ApplicationRoot 'Screenshooter.exe'
if (-not (Test-Path -LiteralPath $applicationExe -PathType Leaf)) {
    throw "Installed application not found: $applicationExe. Build/deploy Screenshooter first. No application files were changed."
}

$cmake = Get-Command cmake -ErrorAction Stop
$sdkBin = Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Windows Kits\10\bin'
$makeAppx = Get-ChildItem $sdkBin -Filter MakeAppx.exe -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\x64\\MakeAppx\.exe$' } |
    Sort-Object FullName -Descending | Select-Object -First 1
if (-not $makeAppx) { throw 'MakeAppx.exe not found. Install Windows 10/11 SDK.' }

$null = New-Item -ItemType Directory -Path $BuildDirectory -Force
$null = New-Item -ItemType Directory -Path $OutputDirectory -Force
& $cmake.Source -S $PSScriptRoot -B $BuildDirectory -A x64
if ($LASTEXITCODE -ne 0) { throw "CMake configure failed: $LASTEXITCODE" }
& $cmake.Source --build $BuildDirectory --config Release
if ($LASTEXITCODE -ne 0) { throw "Native extension build failed: $LASTEXITCODE" }

$dllCandidates = @(
    (Join-Path $BuildDirectory 'Release\ScreenshooterContextMenu.dll'),
    (Join-Path $BuildDirectory 'ScreenshooterContextMenu.dll')
)
$dll = $dllCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $dll) { throw 'Native extension DLL was not produced.' }

$python = Get-Command python -ErrorAction Stop
& $python.Source (Join-Path $PSScriptRoot 'prepare_package_assets.py')
if ($LASTEXITCODE -ne 0) { throw "Manifest asset generation failed: $LASTEXITCODE" }

$payloadContextMenu = Join-Path $OutputDirectory 'Payload\ContextMenu'
$null = New-Item -ItemType Directory -Path $payloadContextMenu -Force
Copy-Item -LiteralPath $dll -Destination (Join-Path $payloadContextMenu 'ScreenshooterContextMenu.dll') -Force
$payloadAssets = Join-Path $payloadContextMenu 'Assets'
$null = New-Item -ItemType Directory -Path $payloadAssets -Force
Copy-Item -Path (Join-Path $PSScriptRoot 'package_assets\Assets\*') -Destination $payloadAssets -Force

$packageStage = Join-Path $BuildDirectory 'sparse-package'
if (Test-Path -LiteralPath $packageStage) { Remove-Item -LiteralPath $packageStage -Recurse -Force }
$assetsSource = Join-Path $PSScriptRoot 'package_assets\Assets'
if (-not (Test-Path -LiteralPath $assetsSource -PathType Container)) { throw "Assets not found: $assetsSource" }
$null = New-Item -ItemType Directory -Path (Join-Path $packageStage 'Assets') -Force
Copy-Item -Path (Join-Path $assetsSource '*') -Destination (Join-Path $packageStage 'Assets') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Package.appxmanifest') -Destination (Join-Path $packageStage 'AppxManifest.xml') -Force

$outputMsix = Join-Path $OutputDirectory 'ScreenshooterModernMenu.msix'
if (Test-Path -LiteralPath $outputMsix) { Remove-Item -LiteralPath $outputMsix -Force }
& $makeAppx.FullName pack /d $packageStage /p $outputMsix /o
if ($LASTEXITCODE -ne 0) { throw "MakeAppx failed: $LASTEXITCODE" }

if ($CertificateThumbprint) {
    $signTool = Get-ChildItem $sdkBin -Filter SignTool.exe -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\SignTool\.exe$' } |
        Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $signTool) { throw 'SignTool.exe not found. MSIX was built but not signed.' }
    $cert = Get-ChildItem "Cert:\CurrentUser\My\$CertificateThumbprint" -ErrorAction SilentlyContinue
    if (-not $cert) { throw 'Signing certificate not found in CurrentUser\My.' }
    if ($cert.Subject -ne 'CN=Screenshooter Developer') { throw "Unexpected certificate subject: $($cert.Subject)" }
    & $signTool.FullName sign /fd SHA256 /sha1 $CertificateThumbprint $outputMsix
    if ($LASTEXITCODE -ne 0) { throw "MSIX signing failed: $LASTEXITCODE" }
}

Write-Host "Application root (ExternalLocation): $ApplicationRoot"
Write-Host "DLL deployment source: $payloadContextMenu\ScreenshooterContextMenu.dll"
Write-Host "MSIX package: $outputMsix"
Write-Host 'The build did not copy files to D:\Screenshooter and did not register the package.'
if (-not $CertificateThumbprint) { Write-Warning 'MSIX is unsigned and cannot be installed.' }
