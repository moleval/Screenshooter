[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$MsixPath,

    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string]$ExternalLocation
)

$ErrorActionPreference = 'Stop'
$packageName = 'Moleval.Screenshooter.ContextMenu'

$os = Get-CimInstance Win32_OperatingSystem
$build = [int]([version]$os.Version).BuildNumber
if ($build -lt 22000) {
    throw "Modern context menu registration requires Windows 11 (build 22000+). No changes were made."
}

$MsixPath = (Resolve-Path -LiteralPath $MsixPath).Path
$ExternalLocation = (Resolve-Path -LiteralPath $ExternalLocation).Path

if (-not (Test-Path -LiteralPath (Join-Path $ExternalLocation 'Screenshooter.exe') -PathType Leaf)) {
    throw "Screenshooter.exe was not found in ExternalLocation. No changes were made."
}
if (-not (Test-Path -LiteralPath (Join-Path $ExternalLocation 'ScreenshooterContextMenu.dll') -PathType Leaf)) {
    throw "ScreenshooterContextMenu.dll was not found in ExternalLocation. No changes were made."
}

$signature = Get-AuthenticodeSignature -LiteralPath $MsixPath
if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    throw "The MSIX signature is not valid ($($signature.Status)). Sign and trust the package before installing it. No changes were made."
}

$manifestText = Get-Content -LiteralPath (Join-Path (Split-Path -Parent $MsixPath) 'AppxManifest.xml') -Raw -ErrorAction SilentlyContinue
if ($manifestText -and $manifestText -notmatch [regex]::Escape($packageName)) {
    throw "Package manifest identity does not match the expected package name. No changes were made."
}

if ($PSCmdlet.ShouldProcess("$packageName for current user", "Register sparse MSIX with external location '$ExternalLocation'")) {
    Add-AppxPackage -Path $MsixPath -ExternalLocation $ExternalLocation -ErrorAction Stop
    Write-Host "Modern menu package registered for the current user."
    Write-Host "The legacy registry-based menu was not modified. Verify the modern item first, then disable the legacy entry in Screenshooter settings if it creates a duplicate."
}
