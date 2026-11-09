[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$MsixPath,

    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$DllPath,

    [string]$ApplicationRoot = 'D:\Screenshooter'
)

$ErrorActionPreference = 'Stop'
$packageName = 'Moleval.Screenshooter.ContextMenu'
$expectedPublisher = 'CN=Screenshooter Developer'
$clsid = '2E50E830-88F2-4A3A-9A6C-6A318C724410'
$ApplicationRoot = [System.IO.Path]::GetFullPath($ApplicationRoot)
$applicationExe = Join-Path $ApplicationRoot 'Screenshooter.exe'
$targetDirectory = Join-Path $ApplicationRoot 'ContextMenu'
$targetDll = Join-Path $targetDirectory 'ScreenshooterContextMenu.dll'

$os = Get-CimInstance Win32_OperatingSystem
if ([int]$os.BuildNumber -lt 22000) { throw 'Modern context menu requires Windows 11 build 22000+.' }
if (-not (Test-Path -LiteralPath $applicationExe -PathType Leaf)) { throw "Application EXE missing: $applicationExe" }

$MsixPath = (Resolve-Path -LiteralPath $MsixPath).Path
$DllPath = (Resolve-Path -LiteralPath $DllPath).Path
$signature = Get-AuthenticodeSignature -LiteralPath $MsixPath
if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    throw "MSIX signature is not valid ($($signature.Status)). No files or registration were changed."
}
if (-not $signature.SignerCertificate -or $signature.SignerCertificate.Subject -ne $expectedPublisher) {
    throw "MSIX signer must be $expectedPublisher. No files or registration were changed."
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($MsixPath)
try {
    $manifestEntry = $archive.GetEntry('AppxManifest.xml')
    if (-not $manifestEntry) { throw 'MSIX has no AppxManifest.xml.' }
    $reader = [System.IO.StreamReader]::new($manifestEntry.Open())
    try { [xml]$manifest = $reader.ReadToEnd() } finally { $reader.Dispose() }
    if ($manifest.Package.Identity.Name -ne $packageName -or
        $manifest.Package.Identity.Publisher -ne $expectedPublisher) {
        throw 'MSIX identity or publisher does not match expected values.'
    }
    $class = $manifest.Package.Applications.Application.Extensions.Extension |
        Where-Object { $_.ComServer } | ForEach-Object { $_.ComServer.SurrogateServer.Class } |
        Where-Object { $_.Id -eq $clsid } | Select-Object -First 1
    if (-not $class -or $class.Path -ne 'ContextMenu\ScreenshooterContextMenu.dll') {
        throw 'MSIX COM server path does not match the fixed ExternalLocation layout.'
    }
    if ($manifest.Package.Applications.Application.Executable -ne 'Screenshooter.exe') {
        throw 'MSIX application executable must be Screenshooter.exe at ExternalLocation root.'
    }
} finally { $archive.Dispose() }

if (-not $PSCmdlet.ShouldProcess("$ApplicationRoot (EXE remains untouched)", "Deploy context-menu DLL and register sparse MSIX")) {
    return
}
$null = New-Item -ItemType Directory -Path $targetDirectory -Force

$backupDll = $null
$hadExistingDll = Test-Path -LiteralPath $targetDll -PathType Leaf
if ($hadExistingDll) {
    $backupDll = Join-Path $targetDirectory ("ScreenshooterContextMenu.dll.backup-" + [guid]::NewGuid().ToString('N'))
    Copy-Item -LiteralPath $targetDll -Destination $backupDll
}
try {
    Copy-Item -LiteralPath $DllPath -Destination $targetDll -Force
    Add-AppxPackage -Path $MsixPath -ExternalLocation $ApplicationRoot -ErrorAction Stop
    if ($backupDll) { Remove-Item -LiteralPath $backupDll -Force }
    Write-Host "Modern context menu registered for current user."
    Write-Host "Application executable was not copied or modified: $applicationExe"
} catch {
    if ($hadExistingDll -and $backupDll -and (Test-Path -LiteralPath $backupDll)) {
        Copy-Item -LiteralPath $backupDll -Destination $targetDll -Force
        Remove-Item -LiteralPath $backupDll -Force
    } elseif (-not $hadExistingDll -and (Test-Path -LiteralPath $targetDll)) {
        Remove-Item -LiteralPath $targetDll -Force
    }
    throw
}
