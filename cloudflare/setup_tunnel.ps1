# ==============================================================================
# Cloudflare Tunnel Setup & Runner for Windows (leewuai.ro)
# ==============================================================================
param(
    [string]$TunnelToken = ""
)

Write-Host "=== LeeWu AI - Cloudflare Tunnel Windows Setup ===" -ForegroundColor Cyan

$cloudflaredPath = "$PSScriptRoot\cloudflared.exe"

if (!(Test-Path $cloudflaredPath) -and !(Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "Downloading cloudflared for Windows..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile $cloudflaredPath
    Write-Host "Downloaded cloudflared.exe" -ForegroundColor Green
}

if ($TunnelToken -ne "") {
    Write-Host "Running Cloudflare Tunnel with Token..." -ForegroundColor Green
    if (Test-Path $cloudflaredPath) {
        & $cloudflaredPath tunnel run --token $TunnelToken
    } else {
        cloudflared tunnel run --token $TunnelToken
    }
} else {
    Write-Host "To run your tunnel for leewuai.ro, execute:" -ForegroundColor Yellow
    Write-Host "  .\setup_tunnel.ps1 -TunnelToken <YOUR_CLOUDFLARE_TUNNEL_TOKEN>" -ForegroundColor White
}
