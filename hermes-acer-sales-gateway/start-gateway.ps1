param(
  [string]$Distro = "Ubuntu"
)

$ErrorActionPreference = "Stop"
& wsl.exe -d $Distro -- bash -lc "export PATH=\"`$HOME/.local/bin:`$PATH\"; exec hermes gateway run"
exit $LASTEXITCODE
