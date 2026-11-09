[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot 'output'),
    [string]$ApplicationRoot = 'D:\Screenshooter',
    [string]$CertificateThumbprint
)

$ErrorActionPreference = 'Stop'
$kitRoot = $PSScriptRoot
$dllSource = Join-Path $kitRoot 'ScreenshooterContextMenu.dll'
$manifestSource = Join-Path $kitRoot 'Package.appxmanifest'
$assetsSource = Join-Path $kitRoot 'Assets'
foreach ($required in @($dllSource, $manifestSource,
        (Join-Path $assetsSource 'StoreLogo.png'),
        (Join-Path $assetsSource 'Square150x150Logo.png'),
        (Join-Path $assetsSource 'Square44x44Logo.png'))) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required package input not found: $required"
    }
}

$sdkBin = Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Windows Kits\10\bin'
$makeAppx = Get-ChildItem $sdkBin -Filter MakeAppx.exe -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\x64\\MakeAppx\.exe$' } |
    Sort-Object FullName -Descending | Select-Object -First 1
if (-not $makeAppx) { throw 'MakeAppx.exe not found. Install Windows 10/11 SDK.' }

$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$payloadContextMenu = Join-Path $OutputDirectory 'Payload\ContextMenu'
$packageStage = Join-Path $OutputDirectory 'sparse-package'
$outputMsix = Join-Path $OutputDirectory 'ScreenshooterModernMenu.msix'
$null = New-Item -ItemType Directory -Path $payloadContextMenu -Force
Copy-Item -LiteralPath $dllSource -Destination (Join-Path $payloadContextMenu 'ScreenshooterContextMenu.dll') -Force
$payloadAssets = Join-Path $payloadContextMenu 'Assets'
$null = New-Item -ItemType Directory -Path $payloadAssets -Force
Copy-Item -LiteralPath (Join-Path $assetsSource 'Square150x150Logo.png') -Destination $payloadAssets -Force
Copy-Item -LiteralPath (Join-Path $assetsSource 'Square44x44Logo.png') -Destination $payloadAssets -Force

if (Test-Path -LiteralPath $packageStage) { Remove-Item -LiteralPath $packageStage -Recurse -Force }
$null = New-Item -ItemType Directory -Path (Join-Path $packageStage 'Assets') -Force
Copy-Item -LiteralPath (Join-Path $assetsSource 'StoreLogo.png') -Destination (Join-Path $packageStage 'Assets') -Force
Copy-Item -LiteralPath $manifestSource -Destination (Join-Path $packageStage 'AppxManifest.xml') -Force
if (Test-Path -LiteralPath $outputMsix) { Remove-Item -LiteralPath $outputMsix -Force }
& $makeAppx.FullName pack /d $packageStage /p $outputMsix /o /nv
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
Write-Host "DLL deployment payload: $payloadContextMenu\ScreenshooterContextMenu.dll"
Write-Host "MSIX package: $outputMsix"
Write-Host 'No files were copied to the application root and no package was registered.'
if (-not $CertificateThumbprint) { Write-Warning 'MSIX is unsigned and cannot be installed until signed.' }
