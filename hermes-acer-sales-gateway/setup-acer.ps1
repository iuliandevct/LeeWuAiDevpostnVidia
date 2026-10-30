param(
  [string]$Distro = "Ubuntu"
)

$ErrorActionPreference = "Stop"
$PackageWindowsPath = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
  Write-Host "WSL is not installed. Run this in an Administrator PowerShell:"
  Write-Host "  wsl --install -d $Distro"
  Write-Host "Restart Windows, open Ubuntu once, then run this script again."
  exit 1
}

$Installed = (& wsl.exe --list --quiet) -replace "`0", ""
if ($Installed -notcontains $Distro) {
  Write-Host "Installing $Distro. Windows may request a restart."
  & wsl.exe --install -d $Distro
  exit 0
}

$PackageWslPath = (& wsl.exe -d $Distro -- wslpath -a $PackageWindowsPath).Trim()
if (-not $PackageWslPath) { throw "Could not translate the package path into WSL." }

& wsl.exe -d $Distro -- bash "$PackageWslPath/setup-hermes-wsl.sh"
if ($LASTEXITCODE -ne 0) { throw "Hermes setup failed with exit code $LASTEXITCODE." }

Write-Host "Next: open $Distro, edit ~/.hermes/.env, run 'hermes gateway setup', then use start-gateway.ps1."
