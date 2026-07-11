# run_api.ps1 - Run the PlaySight FastAPI server locally (no Docker needed).
# Thin wrapper around `playsight serve api`.
#
# Usage:
#   .\scripts\run_api.ps1                       # http://127.0.0.1:8000
#   .\scripts\run_api.ps1 -BindHost 0.0.0.0 -Port 8080 -Reload
#
# Requires the package installed in the active environment: pip install -e ".[dev]"

param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$cliArgs = @("serve", "api", "--host", $BindHost, "--port", $Port)
if ($Reload) { $cliArgs += "--reload" }

& playsight @cliArgs
exit $LASTEXITCODE
