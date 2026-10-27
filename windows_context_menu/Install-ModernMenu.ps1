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
if (-not $signature.SignerCertificate -or $signature.SignerCertificate.Subject -ne 'CN=Screenshooter Developer') {
    throw "The MSIX signer does not match the expected publisher CN=Screenshooter Developer. No changes were made."
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($MsixPath)
try {
    $manifestEntry = $archive.GetEntry('AppxManifest.xml')
    if (-not $manifestEntry) { throw 'MSIX has no AppxManifest.xml. No changes were made.' }
    $reader = [System.IO.StreamReader]::new($manifestEntry.Open())
    try { [xml]$packageManifest = $reader.ReadToEnd() } finally { $reader.Dispose() }
    if ($packageManifest.Package.Identity.Name -ne $packageName -or
        $packageManifest.Package.Identity.Publisher -ne 'CN=Screenshooter Developer') {
        throw 'MSIX package identity or publisher does not match the expected values. No changes were made.'
    }
} finally {
    $archive.Dispose()
}

if ($PSCmdlet.ShouldProcess("$packageName for current user", "Register sparse MSIX with external location '$ExternalLocation'")) {
    Add-AppxPackage -Path $MsixPath -ExternalLocation $ExternalLocation -ErrorAction Stop
    Write-Host "Modern menu package registered for the current user."
    Write-Host "The legacy registry-based menu was not modified. Verify the modern item first, then disable the legacy entry in Screenshooter settings if it creates a duplicate."
}
