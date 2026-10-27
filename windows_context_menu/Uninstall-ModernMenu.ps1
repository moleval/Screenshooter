[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param()

$ErrorActionPreference = 'Stop'
$packageName = 'Moleval.Screenshooter.ContextMenu'

$packages = @(Get-AppxPackage -Name $packageName -ErrorAction SilentlyContinue)
if ($packages.Count -eq 0) {
    Write-Host "The modern context-menu package is not installed for the current user."
    exit 0
}

foreach ($package in $packages) {
    if ($PSCmdlet.ShouldProcess("$($package.Name) version $($package.Version)", "Unregister modern context-menu package for current user")) {
        Remove-AppxPackage -Package $package.PackageFullName -ErrorAction Stop
    }
}

Write-Host "Only the modern context-menu package was removed. The Screenshooter application and legacy menu registration were not modified."
