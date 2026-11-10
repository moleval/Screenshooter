[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$MsixPath,

    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string]$PayloadDirectory,

)

$ErrorActionPreference = 'Stop'
$packageName = 'Moleval.Screenshooter.ContextMenu'
$expectedPublisher = 'CN=Screenshooter Developer'
$clsid = '2E50E830-88F2-4A3A-9A6C-6A318C724410'
$ApplicationRoot = 'D:\Screenshooter'
$applicationExe = Join-Path $ApplicationRoot 'Screenshooter.exe'
$targetDirectory = Join-Path $ApplicationRoot 'ContextMenu'
$managedFiles = @(
    'ScreenshooterContextMenu.dll',
    'Assets\Square150x150Logo.png',
    'Assets\Square44x44Logo.png'
)

$os = Get-CimInstance Win32_OperatingSystem
if ([int]$os.BuildNumber -lt 22000) { throw 'Modern context menu requires Windows 11 build 22000+.' }
if (-not (Test-Path -LiteralPath $applicationExe -PathType Leaf)) { throw "Application EXE missing: $applicationExe" }

$MsixPath = (Resolve-Path -LiteralPath $MsixPath).Path
$PayloadDirectory = (Resolve-Path -LiteralPath $PayloadDirectory).Path
foreach ($relative in $managedFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $PayloadDirectory $relative) -PathType Leaf)) {
        throw "Required deployment payload file missing: $relative"
    }
}

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
    $application = $manifest.Package.Applications.Application
    if ($application.Executable -ne 'Screenshooter.exe') {
        throw 'MSIX application executable must be Screenshooter.exe at ExternalLocation root.'
    }
    $class = $application.Extensions.Extension |
        Where-Object { $_.ComServer } | ForEach-Object { $_.ComServer.SurrogateServer.Class } |
        Where-Object { $_.Id -eq $clsid } | Select-Object -First 1
    if (-not $class -or $class.Path -ne 'ContextMenu\ScreenshooterContextMenu.dll') {
        throw 'MSIX COM server path does not match the fixed ExternalLocation layout.'
    }
    $visualElements = $application.SelectSingleNode("*[local-name()='VisualElements']")
    if (-not $visualElements -or
        $visualElements.Square150x150Logo -ne 'ContextMenu\Assets\Square150x150Logo.png' -or
        $visualElements.Square44x44Logo -ne 'ContextMenu\Assets\Square44x44Logo.png') {
        throw 'MSIX visual asset paths do not match the ExternalLocation payload.'
    }
    if ([version]$manifest.Package.Dependencies.TargetDeviceFamily.MinVersion -lt [version]'10.0.22000.0') {
        throw 'MSIX manifest minimum version must be Windows 11 build 22000 or newer.'
    }
} finally { $archive.Dispose() }

$registrationAlreadyCurrent = $false
$existingPackages = @(Get-AppxPackage -Name $packageName -ErrorAction Stop)
if ($existingPackages.Count -gt 0) {
    [xml]$existingManifest = Get-AppxPackageManifest -Package $existingPackages[0]
    $existingApplication = $existingManifest.Package.Applications.Application
    $existingClass = $existingApplication.Extensions.Extension |
        Where-Object { $_.ComServer } | ForEach-Object { $_.ComServer.SurrogateServer.Class } |
        Where-Object { $_.Id -eq $clsid } | Select-Object -First 1
    $existingVisual = $existingApplication.SelectSingleNode("*[local-name()='VisualElements']")
    $registrationAlreadyCurrent = (
        $existingManifest.Package.Identity.Name -eq $packageName -and
        $existingManifest.Package.Identity.Publisher -eq $expectedPublisher -and
        $existingApplication.Executable -eq 'Screenshooter.exe' -and
        $existingClass -and $existingClass.Path -eq 'ContextMenu\ScreenshooterContextMenu.dll' -and
        $existingVisual -and
        $existingVisual.Square150x150Logo -eq 'ContextMenu\Assets\Square150x150Logo.png' -and
        $existingVisual.Square44x44Logo -eq 'ContextMenu\Assets\Square44x44Logo.png'
    )
}

if (-not $PSCmdlet.ShouldProcess("$ApplicationRoot (EXE remains untouched)", "Deploy COM DLL/assets and register sparse MSIX")) {
    return
}

$null = New-Item -ItemType Directory -Path $targetDirectory -Force
$backupRoot = Join-Path $targetDirectory ('.screenshooter-backup-' + [guid]::NewGuid().ToString('N'))
$existingFiles = @{}
$copiedFiles = @()
try {
    foreach ($relative in $managedFiles) {
        $destination = Join-Path $targetDirectory $relative
        $destinationParent = Split-Path -Parent $destination
        $null = New-Item -ItemType Directory -Path $destinationParent -Force
        $existingFiles[$relative] = Test-Path -LiteralPath $destination -PathType Leaf
        if ($existingFiles[$relative]) {
            $backup = Join-Path $backupRoot $relative
            $null = New-Item -ItemType Directory -Path (Split-Path -Parent $backup) -Force
            Copy-Item -LiteralPath $destination -Destination $backup
        }
    }
    foreach ($relative in $managedFiles) {
        Copy-Item -LiteralPath (Join-Path $PayloadDirectory $relative) -Destination (Join-Path $targetDirectory $relative) -Force
        $copiedFiles += $relative
    }

    if (-not $registrationAlreadyCurrent) {
        Add-AppxPackage -Path $MsixPath -ExternalLocation $ApplicationRoot -Confirm:$false -ErrorAction Stop
    }
    $registered = @(Get-AppxPackage -Name $packageName -ErrorAction Stop)
    if ($registered.Count -eq 0) {
        throw 'Add-AppxPackage returned without an error, but the package is not registered for the current user.'
    }
    if (Test-Path -LiteralPath $backupRoot) {
        Remove-Item -LiteralPath $backupRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host 'Modern context menu registered for current user.'
    Write-Host "ExternalLocation: $ApplicationRoot"
    Write-Host "Application executable was not copied or modified: $applicationExe"
} catch {
    foreach ($relative in $copiedFiles) {
        $destination = Join-Path $targetDirectory $relative
        $backup = Join-Path $backupRoot $relative
        if ($existingFiles[$relative] -and (Test-Path -LiteralPath $backup -PathType Leaf)) {
            Copy-Item -LiteralPath $backup -Destination $destination -Force
        } elseif (-not $existingFiles[$relative] -and (Test-Path -LiteralPath $destination -PathType Leaf)) {
            Remove-Item -LiteralPath $destination -Force
        }
    }
    if (Test-Path -LiteralPath $backupRoot) {
        Remove-Item -LiteralPath $backupRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    throw
}
