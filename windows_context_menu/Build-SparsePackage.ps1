[CmdletBinding()]
param(
    [string]$AppExe = (Join-Path (Split-Path -Parent $PSScriptRoot) 'dist\Screenshooter.exe'),
    [string]$BuildDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) 'build\windows-context-menu'),
    [string]$ExternalLocation = (Join-Path (Split-Path -Parent $PSScriptRoot) 'dist\ScreenshooterModernMenu'),
    [string]$OutputMsix = (Join-Path (Split-Path -Parent $PSScriptRoot) 'dist\ScreenshooterModernMenu.msix'),
    [string]$CertificateThumbprint
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path -LiteralPath $AppExe -PathType Leaf)) {
    throw "Application executable not found: $AppExe. Build Screenshooter first. Nothing was installed or registered."
}

$cmake = Get-Command cmake -ErrorAction Stop
$makeAppx = Get-ChildItem "\${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Filter MakeAppx.exe -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\x64\\MakeAppx\.exe$' } |
    Sort-Object FullName -Descending |
    Select-Object -First 1
if (-not $makeAppx) {
    throw "MakeAppx.exe was not found. Install the Windows 10/11 SDK. Nothing was installed or registered."
}

$null = New-Item -ItemType Directory -Path $ExternalLocation -Force
$null = New-Item -ItemType Directory -Path (Split-Path -Parent $OutputMsix) -Force

$buildPath = (Resolve-Path -LiteralPath $BuildDirectory -ErrorAction SilentlyContinue).Path
if (-not $buildPath) {
    & $cmake.Source -S (Join-Path $PSScriptRoot '.') -B $BuildDirectory -A x64
    if ($LASTEXITCODE -ne 0) { throw "CMake configure failed with exit code $LASTEXITCODE." }
    $buildPath = $BuildDirectory
}
& $cmake.Source --build $buildPath --config Release
if ($LASTEXITCODE -ne 0) { throw "Native extension build failed with exit code $LASTEXITCODE." }

$dllCandidates = @(
    (Join-Path $buildPath 'Release\ScreenshooterContextMenu.dll'),
    (Join-Path $buildPath 'ScreenshooterContextMenu.dll')
)
$dll = $dllCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $dll) { throw "Native extension DLL was not produced. Nothing was registered." }

Copy-Item -LiteralPath $AppExe -Destination (Join-Path $ExternalLocation 'Screenshooter.exe') -Force
Copy-Item -LiteralPath $dll -Destination (Join-Path $ExternalLocation 'ScreenshooterContextMenu.dll') -Force

$python = Get-Command python -ErrorAction Stop
& $python.Source (Join-Path $PSScriptRoot 'prepare_package_assets.py')
if ($LASTEXITCODE -ne 0) { throw "Manifest asset generation failed with exit code $LASTEXITCODE." }

$packageStage = Join-Path $BuildDirectory 'sparse-package'
if (Test-Path -LiteralPath $packageStage) { Remove-Item -LiteralPath $packageStage -Recurse -Force }
$assetsSource = Join-Path $PSScriptRoot 'package_assets\Assets'
if (-not (Test-Path -LiteralPath $assetsSource -PathType Container)) {
    throw "Generated manifest assets were not found: $assetsSource"
}
$null = New-Item -ItemType Directory -Path (Join-Path $packageStage 'Assets') -Force
Copy-Item -Path (Join-Path $assetsSource '*') -Destination (Join-Path $packageStage 'Assets') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Package.appxmanifest') -Destination (Join-Path $packageStage 'AppxManifest.xml') -Force

if (Test-Path -LiteralPath $OutputMsix) { Remove-Item -LiteralPath $OutputMsix -Force }
& $makeAppx.FullName pack /d $packageStage /p $OutputMsix /o
if ($LASTEXITCODE -ne 0) { throw "MakeAppx failed with exit code $LASTEXITCODE." }

if ($CertificateThumbprint) {
    $signTool = Get-ChildItem "\${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Filter SignTool.exe -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\SignTool\.exe$' } |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if (-not $signTool) { throw "SignTool.exe was not found. The package was built but not signed." }

    $cert = Get-ChildItem "Cert:\CurrentUser\My\$CertificateThumbprint" -ErrorAction SilentlyContinue
    if (-not $cert) { throw "Certificate thumbprint not found in CurrentUser\My. Package was built but not signed." }
    if ($cert.Subject -ne 'CN=Screenshooter Developer') {
        throw "Certificate subject '$($cert.Subject)' does not match the manifest publisher 'CN=Screenshooter Developer'. Package was built but not signed."
    }

    & $signTool.FullName sign /fd SHA256 /sha1 $CertificateThumbprint $OutputMsix
    if ($LASTEXITCODE -ne 0) { throw "MSIX signing failed with exit code $LASTEXITCODE." }
}

Write-Host "External app location: $ExternalLocation"
Write-Host "MSIX package: $OutputMsix"
if (-not $CertificateThumbprint) {
    Write-Warning "Package is unsigned. It cannot be installed until signed by a certificate whose publisher matches the manifest and that Windows trusts."
} else {
    Write-Host "Package was signed. The signing certificate must also be trusted by Windows before installation."
}
Write-Host "No Windows registration or system settings were changed."
