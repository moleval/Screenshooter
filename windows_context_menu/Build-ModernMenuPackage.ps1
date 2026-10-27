[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$AppExe,

    [string]$OutputDirectory = (Join-Path $PSScriptRoot 'output'),

    [string]$CertificateThumbprint
)

$ErrorActionPreference = 'Stop'
$kitRoot = $PSScriptRoot
$AppExe = (Resolve-Path -LiteralPath $AppExe).Path
$dllSource = Join-Path $kitRoot 'ScreenshooterContextMenu.dll'
$manifestSource = Join-Path $kitRoot 'Package.appxmanifest'
$assetsSource = Join-Path $kitRoot 'Assets'

foreach ($required in @($dllSource, $manifestSource, (Join-Path $assetsSource 'StoreLogo.png'),
        (Join-Path $assetsSource 'Square150x150Logo.png'), (Join-Path $assetsSource 'Square44x44Logo.png'))) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required kit file not found: $required"
    }
}

$sdkBin = Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Windows Kits\10\bin'
$makeAppx = Get-ChildItem $sdkBin -Filter MakeAppx.exe -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\x64\\MakeAppx\.exe$' } |
    Sort-Object FullName -Descending |
    Select-Object -First 1
if (-not $makeAppx) {
    throw "MakeAppx.exe was not found. Install the Windows 10/11 SDK. No package was installed or registered."
}

$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$externalLocation = Join-Path $OutputDirectory 'ScreenshooterModernMenu'
$packageStage = Join-Path $OutputDirectory 'sparse-package'
$outputMsix = Join-Path $OutputDirectory 'ScreenshooterModernMenu.msix'
$null = New-Item -ItemType Directory -Path $externalLocation -Force
Copy-Item -LiteralPath $AppExe -Destination (Join-Path $externalLocation 'Screenshooter.exe') -Force
Copy-Item -LiteralPath $dllSource -Destination (Join-Path $externalLocation 'ScreenshooterContextMenu.dll') -Force

if (Test-Path -LiteralPath $packageStage) { Remove-Item -LiteralPath $packageStage -Recurse -Force }
$null = New-Item -ItemType Directory -Path (Join-Path $packageStage 'Assets') -Force
Copy-Item -Path (Join-Path $assetsSource '*') -Destination (Join-Path $packageStage 'Assets') -Force
Copy-Item -LiteralPath $manifestSource -Destination (Join-Path $packageStage 'AppxManifest.xml') -Force

if (Test-Path -LiteralPath $outputMsix) { Remove-Item -LiteralPath $outputMsix -Force }
& $makeAppx.FullName pack /d $packageStage /p $outputMsix /o
if ($LASTEXITCODE -ne 0) { throw "MakeAppx failed with exit code $LASTEXITCODE." }

if ($CertificateThumbprint) {
    $signTool = Get-ChildItem $sdkBin -Filter SignTool.exe -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\SignTool\.exe$' } |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if (-not $signTool) { throw "SignTool.exe was not found. The package was built but not signed." }

    $cert = Get-ChildItem "Cert:\CurrentUser\My\$CertificateThumbprint" -ErrorAction SilentlyContinue
    if (-not $cert) { throw "Certificate thumbprint not found in CurrentUser\My. Package was built but not signed." }
    if ($cert.Subject -ne 'CN=Screenshooter Developer') {
        throw "Certificate subject '$($cert.Subject)' does not match the manifest publisher 'CN=Screenshooter Developer'. Package was built but not signed."
    }

    & $signTool.FullName sign /fd SHA256 /sha1 $CertificateThumbprint $outputMsix
    if ($LASTEXITCODE -ne 0) { throw "MSIX signing failed with exit code $LASTEXITCODE." }
}

Write-Host "External app location: $externalLocation"
Write-Host "MSIX package: $outputMsix"
if (-not $CertificateThumbprint) {
    Write-Warning "Package is unsigned. Install-ModernMenu.ps1 will reject it until signed by a matching trusted certificate."
} else {
    Write-Host "Package was signed. Windows must trust the signing certificate before installation."
}
Write-Host "No Windows registration or system settings were changed."
